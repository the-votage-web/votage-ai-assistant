import * as PrismaModule from "@prisma/client";
import { randomUUID } from "crypto";
import { buildCheckinCode } from "./checkin-code";
import { DEFAULT_CONNECT_OPTIONS, DEFAULT_SERVICE_OPTIONS, ServiceType } from "./constants";
import { logCheckinFailure } from "./intake";
import { findMemberByPhone } from "./phone";
import { prisma } from "./prisma";

const { PrismaClientKnownRequestError } = PrismaModule as {
  PrismaClientKnownRequestError: new (...args: never[]) => { code?: string };
};

type TxClient = typeof prisma;

type SessionState = {
  pending_checkin_phone?: string;
  pending_service_type?: ServiceType | null;
};

function currentServiceDate() {
  const now = new Date();
  return new Date(now.getFullYear(), now.getMonth(), now.getDate());
}

function registrationPageUrl() {
  const base =
    process.env.FRONTEND_URL?.trim() ||
    process.env.NEXT_PUBLIC_SITE_URL?.trim() ||
    "http://localhost:3000";
  return `${base.replace(/\/$/, "")}/register?tab=registration`;
}

function normalizeServiceType(value: string) {
  const normalized = value.trim().toLowerCase().replace(/\s+/g, "_");
  if (normalized === "sundayservice") return "sunday_service";
  if (normalized === "specialservice") return "special_service";
  if ((DEFAULT_SERVICE_OPTIONS as readonly string[]).includes(normalized)) {
    return normalized as ServiceType;
  }
  if (normalized.includes("sunday")) return "sunday_service";
  if (normalized.includes("special")) return "special_service";
  if (normalized.includes("connect")) return "connect";
  return null;
}

function isEndSessionMessage(message: string) {
  const normalized = message.toLowerCase().replace(/\s+/g, " ").trim();
  return ["end", "stop", "cancel", "quit", "end session", "stop session", "cancel session"].includes(normalized);
}

function parseState(rawState: string) {
  try {
    const state = JSON.parse(rawState || "{}");
    return state && typeof state === "object" ? (state as SessionState) : {};
  } catch {
    return {};
  }
}

async function saveState(sessionId: string, state: SessionState) {
  await prisma.chatSession.upsert({
    where: { id: sessionId },
    update: { stateJson: JSON.stringify(state) },
    create: { id: sessionId, stateJson: JSON.stringify(state) },
  });
}

async function getConnectOptions() {
  const dbGroups = await prisma.connectGroup.findMany({
    select: { name: true },
    distinct: ["name"],
    orderBy: { name: "asc" },
  });
  const merged = [...dbGroups.map((group: { name: string }) => group.name), ...DEFAULT_CONNECT_OPTIONS];
  return Array.from(new Set(merged.map((name) => name.trim()).filter(Boolean)));
}

async function connectGroupPrompt() {
  const options = await getConnectOptions();
  return `Choose your connect group: ${options.join(", ")}.`;
}

async function extractConnectName(message: string) {
  const normalized = message.toLowerCase();
  const options = await getConnectOptions();
  return (
    options.find((option) => {
      const lowered = option.toLowerCase();
      return normalized === lowered || normalized.includes(lowered);
    }) ?? null
  );
}

function extractPhone(message: string) {
  const match = message.match(/(?:\+?\d[\d\s()-]{6,}\d)/);
  return match?.[0]?.trim() ?? null;
}

async function getOrCreateService(tx: TxClient, serviceType: ServiceType) {
  const existing = await tx.service.findFirst({
    where: {
      name: {
        equals: serviceType,
        mode: "insensitive",
      },
    },
  });

  if (existing) {
    return existing;
  }

  return tx.service.create({
    data: {
      name: serviceType,
    },
  });
}

async function getOrCreateConnectGroup(tx: TxClient, serviceId: string, connectName: string) {
  const existing = await tx.connectGroup.findFirst({
    where: {
      name: {
        equals: connectName,
        mode: "insensitive",
      },
    },
  });

  if (existing) {
    if (existing.serviceId !== serviceId) {
      return tx.connectGroup.update({
        where: { id: existing.id },
        data: { serviceId },
      });
    }
    return existing;
  }

  return tx.connectGroup.create({
    data: {
      serviceId,
      name: connectName,
      description: "Auto-created from registration/check-in",
      meetingTime: "TBD",
      meetingDay: "TBD",
    },
  });
}

async function markFirstTimerEvent(memberId: string, serviceId: string | null, serviceType: ServiceType, connectName?: string | null) {
  const today = currentServiceDate();
  const serviceName =
    serviceType === "connect" && connectName
      ? `connect (${connectName})`
      : serviceType.replace(/_/g, " ");

  const existing = await prisma.firstTimerEvent.findFirst({
    where: {
      memberId,
      serviceDate: today,
      serviceName,
    },
  });
  if (existing) {
    return;
  }

  try {
    await prisma.firstTimerEvent.create({
      data: {
        memberId,
        serviceId,
        serviceType,
        serviceName,
        serviceDate: today,
      },
    });
  } catch (error) {
    if (!(error instanceof PrismaClientKnownRequestError) || error.code !== "P2002") {
      throw error;
    }
  }
}

async function recordCheckin(sessionId: string, phone: string, serviceType: ServiceType, connectName?: string | null) {
  const member = await findMemberByPhone(phone);
  if (!member) {
    const message =
      "👋 I don’t recognize that phone number yet.\n" +
      `Please register here first: ${registrationPageUrl()}`;
    await logCheckinFailure({
      sessionId,
      reason: "phone_not_registered",
      message,
      phone,
      serviceType,
      connectName,
    });
    return message;
  }

  const memberDisplayName = `${member.firstName} ${member.lastName}`.trim();
  const effectiveConnectName = serviceType === "connect" ? connectName?.trim() || null : null;

  if (serviceType === "connect" && member.connectName) {
    const registered = member.connectName.trim();
    const selected = effectiveConnectName?.trim() || "";
    if (registered && selected && registered.toLowerCase() !== selected.toLowerCase()) {
      const message =
        `Connect check-in failed. Your registration is under ${registered}. ` +
        `You selected ${selected}. Please select your registered connect group or contact an admin to update your profile.\n\n` +
        (await connectGroupPrompt());
      await logCheckinFailure({
        sessionId,
        reason: "connect_mismatch",
        message,
        phone,
        serviceType,
        connectName,
      });
      return message;
    }
  }

  const serviceDate = currentServiceDate();
  const existing =
    serviceType === "connect"
      ? await prisma.attendance.findFirst({
          where: {
            memberId: member.id,
            serviceDate,
            serviceType: "connect",
          },
        })
      : await prisma.attendance.findFirst({
          where: {
            memberId: member.id,
            serviceDate,
            serviceType,
            connectName: "",
          },
        });

  if (existing) {
    const code =
      existing.checkinCode ||
      (
        await prisma.attendance.update({
          where: { id: existing.id },
          data: {
            checkinCode: buildCheckinCode(existing.serviceType, existing.id),
          },
        })
      ).checkinCode;
    const label =
      existing.serviceType === "connect" && existing.connectName
        ? `connect (${existing.connectName})`
        : existing.serviceType.replace(/_/g, " ");
    return `You’re already checked in for ${label} today, ${memberDisplayName}. Your check-in code is ${code}.`;
  }

  const attendance = await prisma.$transaction(async (tx: TxClient) => {
    const service = await getOrCreateService(tx, serviceType);
    if (serviceType === "connect" && effectiveConnectName) {
      await getOrCreateConnectGroup(tx, service.id, effectiveConnectName);
    }

    const attendanceId = randomUUID();
    const checkinCode = buildCheckinCode(serviceType, attendanceId);

    return tx.attendance.create({
      data: {
        id: attendanceId,
        memberId: member.id,
        serviceId: service.id,
        serviceType,
        connectName: effectiveConnectName ?? "",
        checkinCode,
        serviceDate,
      },
    });
  });

  if (member.firstTimer) {
    await markFirstTimerEvent(member.id, attendance.serviceId ?? null, serviceType, effectiveConnectName ?? member.connectName);
  }

  const code = attendance.checkinCode;
  const label = serviceType === "connect" && effectiveConnectName ? `connect (${effectiveConnectName})` : serviceType.replace(/_/g, " ");
  return `Attendance recorded for ${label}. Welcome, ${memberDisplayName}. Your check-in code is ${code}.`;
}

export async function handleCheckin(sessionId: string, message: string) {
  const session = await prisma.chatSession.upsert({
    where: { id: sessionId },
    update: {},
    create: { id: sessionId, stateJson: "{}" },
  });
  const state = parseState(session.stateJson);

  if (isEndSessionMessage(message)) {
    await saveState(sessionId, {});
    return "Check-in session ended.";
  }

  const phone = extractPhone(message);
  const serviceType = normalizeServiceType(message);
  const pendingPhone = state.pending_checkin_phone;
  const pendingServiceType = state.pending_service_type;

  if (pendingPhone) {
    const nextPhone = phone ?? pendingPhone;

    if (pendingServiceType === "connect") {
      const chosenConnectName = await extractConnectName(message);
      if (!chosenConnectName) {
        return connectGroupPrompt();
      }
      const reply = await recordCheckin(sessionId, nextPhone, "connect", chosenConnectName);
      if (reply.toLowerCase().includes("attendance recorded") || reply.toLowerCase().includes("already checked in")) {
        await saveState(sessionId, {});
      } else {
        await saveState(sessionId, {
          pending_checkin_phone: nextPhone,
          pending_service_type: "connect",
        });
      }
      return reply;
    }

    if (!serviceType) {
      const reply = await recordCheckin(sessionId, nextPhone, "sunday_service");
      if (reply.toLowerCase().includes("attendance recorded") || reply.toLowerCase().includes("already checked in")) {
        await saveState(sessionId, {});
      } else {
        await saveState(sessionId, {
          pending_checkin_phone: nextPhone,
        });
      }
      return reply;
    }

    if (serviceType === "connect") {
      await saveState(sessionId, {
        pending_checkin_phone: nextPhone,
        pending_service_type: "connect",
      });
      return connectGroupPrompt();
    }

    const reply = await recordCheckin(sessionId, nextPhone, serviceType);
    if (reply.toLowerCase().includes("attendance recorded") || reply.toLowerCase().includes("already checked in")) {
      await saveState(sessionId, {});
    } else {
      await saveState(sessionId, {
        pending_checkin_phone: nextPhone,
      });
    }
    return reply;
  }

  const looksLikeCheckin = Boolean(phone || serviceType || /\bcheck[\s-]?in\b/i.test(message));
  if (!looksLikeCheckin) {
    return "Hi, I'm the check-in assistant. To get started, please send your phone number (e.g. 08012345678).";
  }

  if (!phone) {
    return "Please send your phone number (e.g. 08012345678) to check in.";
  }

  if (!serviceType) {
    const reply = await recordCheckin(sessionId, phone, "sunday_service");
    if (reply.toLowerCase().includes("attendance recorded") || reply.toLowerCase().includes("already checked in")) {
      await saveState(sessionId, {});
    } else {
      await saveState(sessionId, {
        pending_checkin_phone: phone,
      });
    }
    return reply;
  }

  if (serviceType === "connect") {
    const chosenConnectName = await extractConnectName(message);
    if (!chosenConnectName) {
      await saveState(sessionId, {
        pending_checkin_phone: phone,
        pending_service_type: "connect",
      });
      return connectGroupPrompt();
    }
    const reply = await recordCheckin(sessionId, phone, "connect", chosenConnectName);
    if (reply.toLowerCase().includes("attendance recorded") || reply.toLowerCase().includes("already checked in")) {
      await saveState(sessionId, {});
    } else {
      await saveState(sessionId, {
        pending_checkin_phone: phone,
        pending_service_type: "connect",
      });
    }
    return reply;
  }

  const reply = await recordCheckin(sessionId, phone, serviceType);
  if (reply.toLowerCase().includes("attendance recorded") || reply.toLowerCase().includes("already checked in")) {
    await saveState(sessionId, {});
  } else {
    await saveState(sessionId, {
      pending_checkin_phone: phone,
    });
  }
  return reply;
}
