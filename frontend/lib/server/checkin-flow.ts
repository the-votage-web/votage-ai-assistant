import { randomUUID } from "crypto";
import { buildCheckinCode } from "./checkin-code";
import {
  DEFAULT_CONNECT_OPTIONS,
  DEFAULT_DEPARTMENT_OPTIONS,
  DEFAULT_SERVICE_OPTIONS,
  ServiceType,
  isConnectCheckinDay,
  normalizeConnectName,
  normalizeDepartmentName,
} from "./constants";
import { logCheckinFailure } from "./intake";
import { findMemberByPhone } from "./phone";
import { prisma, type PrismaTransactionClient } from "./prisma";

type TxClient = PrismaTransactionClient;

type FlowStep =
  | "awaiting_connect"
  | "existing_worker_status"
  | "department"
  | "custom_department"
  | "new_email"
  | "new_gender"
  | "new_first_name"
  | "new_last_name"
  | "new_marital_status";

type FlowData = {
  phoneNumber: string;
  memberId?: string;
  memberName?: string;
  isNewMember?: boolean;
  isWorker?: boolean;
  department?: string | null;
  connectName?: string | null;
  email?: string;
  gender?: string;
  firstName?: string;
  lastName?: string;
  maritalStatus?: string;
};

type SessionState = {
  pending_checkin_phone?: string;
  pending_service_type?: ServiceType | null;
  step?: FlowStep;
  flow?: FlowData | null;
};

function hasPrismaErrorCode(error: unknown, code: string) {
  return (
    typeof error === "object" &&
    error !== null &&
    "code" in error &&
    (error as { code?: unknown }).code === code
  );
}

function currentServiceDate() {
  const now = new Date();
  return new Date(now.getFullYear(), now.getMonth(), now.getDate());
}

function formatServiceDate(date: Date) {
  return new Intl.DateTimeFormat("en-US", {
    weekday: "long",
    month: "long",
    day: "numeric",
    year: "numeric",
  }).format(date);
}

function defaultServiceTypeForToday(): ServiceType {
  return isConnectCheckinDay() ? "connect" : "sunday_service";
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
  const merged = [
    ...dbGroups.map((group: { name: string }) => normalizeConnectName(group.name) ?? group.name.trim()),
    ...DEFAULT_CONNECT_OPTIONS,
  ];
  return Array.from(new Set(merged.filter(Boolean)));
}

async function connectGroupPrompt() {
  const options = await getConnectOptions();
  return `Choose your Connect group: ${options.join(", ")}.`;
}

function departmentPrompt() {
  return `Choose your department: ${DEFAULT_DEPARTMENT_OPTIONS.join(", ")}.`;
}

function workerPrompt() {
  return "Are you a worker? Reply yes or no.";
}

function genderPrompt() {
  return "What is your gender? Reply male or female.";
}

function maritalStatusPrompt() {
  return "What is your marital status? Reply single, married, divorced, or widowed.";
}

async function extractConnectName(message: string) {
  const direct = normalizeConnectName(message);
  if (direct) {
    return direct;
  }

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

function extractYesNo(message: string) {
  const normalized = message.trim().toLowerCase();
  if (["yes", "y", "worker", "i am", "i'm", "true"].includes(normalized)) return true;
  if (["no", "n", "not", "false"].includes(normalized)) return false;
  return null;
}

function extractGender(message: string) {
  const normalized = message.trim().toLowerCase();
  if (["male", "m"].includes(normalized)) return "male";
  if (["female", "f"].includes(normalized)) return "female";
  return null;
}

function extractMaritalStatus(message: string) {
  const normalized = message.trim().toLowerCase();
  if (["single", "married", "divorced", "widowed"].includes(normalized)) {
    return normalized;
  }
  return null;
}

function extractDepartment(message: string) {
  const direct = normalizeDepartmentName(message);
  if (direct) {
    return direct;
  }

  const normalized = message.toLowerCase();
  return (
    DEFAULT_DEPARTMENT_OPTIONS.find((option) => {
      const lowered = option.toLowerCase().replace(/_/g, " ");
      return normalized === lowered || normalized.includes(lowered);
    }) ?? null
  );
}

function validateEmail(value: string) {
  const normalized = value.trim().toLowerCase();
  if (!normalized.includes("@") || !normalized.split("@")[1]?.includes(".")) {
    return null;
  }
  return normalized;
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

async function getOrCreateDepartment(tx: TxClient, departmentName: string) {
  const existing = await tx.department.findFirst({
    where: {
      name: {
        equals: departmentName,
        mode: "insensitive",
      },
    },
  });

  if (existing) {
    return existing;
  }

  return tx.department.create({
    data: {
      name: departmentName,
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
    if (!hasPrismaErrorCode(error, "P2002")) {
      throw error;
    }
  }
}

async function recordStandardCheckin(sessionId: string, phone: string, serviceType: ServiceType) {
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
    });
    return message;
  }

  const serviceDate = currentServiceDate();
  const serviceDateLabel = formatServiceDate(serviceDate);
  const existing = await prisma.attendance.findFirst({
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
    return `You’re already checked in for ${serviceType.replace(/_/g, " ")} on ${serviceDateLabel}, ${member.firstName}. Your check-in code is ${code}.`;
  }

  const attendance = await prisma.$transaction(async (tx: TxClient) => {
    const service = await getOrCreateService(tx, serviceType);
    const attendanceId = randomUUID();
    const checkinCode = buildCheckinCode(serviceType, attendanceId);

    return tx.attendance.create({
      data: {
        id: attendanceId,
        memberId: member.id,
        serviceId: service.id,
        serviceType,
        connectName: "",
        checkinCode,
        serviceDate,
      },
    });
  });

  if (member.firstTimer) {
    await markFirstTimerEvent(member.id, attendance.serviceId ?? null, serviceType);
  }

  return `Attendance recorded for ${serviceType.replace(/_/g, " ")} on ${serviceDateLabel}. Welcome, ${member.firstName}. Your check-in code is ${attendance.checkinCode}.`;
}

async function completeConnectCheckin(flow: FlowData) {
  if (!isConnectCheckinDay()) {
    return { reply: "Connect check-in is available from Tuesday to Saturday.", reset: true };
  }

  if (!flow.connectName) {
    return { reply: await connectGroupPrompt(), reset: false };
  }

  try {
    const serviceDate = currentServiceDate();
    const serviceDateLabel = formatServiceDate(serviceDate);
    const result = await prisma.$transaction(async (tx: TxClient) => {
      const service = await getOrCreateService(tx, "connect");
      await getOrCreateConnectGroup(tx, service.id, flow.connectName!);

      if (flow.memberId) {
        const member = await tx.member.findUnique({
          where: { id: flow.memberId },
          select: {
            id: true,
            firstName: true,
            lastName: true,
            firstTimer: true,
            isWorker: true,
            department: true,
            departmentId: true,
            connectName: true,
          },
        });

        if (!member) {
          return { kind: "missing_member" as const };
        }

        const departmentRecord =
          flow.isWorker && flow.department
            ? await getOrCreateDepartment(tx, flow.department)
            : null;

        const updates: {
          isWorker?: boolean;
          department?: string | null;
          departmentId?: string | null;
          connectName?: string;
        } = {};

        if (typeof flow.isWorker === "boolean" && member.isWorker !== flow.isWorker) {
          updates.isWorker = flow.isWorker;
        }
        if (typeof flow.department !== "undefined" && member.department !== flow.department) {
          updates.department = flow.department ?? null;
        }
        if ((member.departmentId ?? null) !== (departmentRecord?.id ?? null)) {
          updates.departmentId = departmentRecord?.id ?? null;
        }
        if (flow.connectName && normalizeConnectName(member.connectName ?? "") !== flow.connectName) {
          updates.connectName = flow.connectName;
        }

        const effectiveMember =
          Object.keys(updates).length > 0
            ? await tx.member.update({
                where: { id: member.id },
                data: updates,
                select: {
                  id: true,
                  firstName: true,
                  lastName: true,
                  firstTimer: true,
                  connectName: true,
                },
              })
            : member;

        const existingAttendance = await tx.attendance.findFirst({
          where: {
            memberId: effectiveMember.id,
            serviceDate,
            serviceType: "connect",
          },
        });

        if (existingAttendance) {
          const code =
            existingAttendance.checkinCode ||
            (
              await tx.attendance.update({
                where: { id: existingAttendance.id },
                data: {
                  checkinCode: buildCheckinCode(existingAttendance.serviceType, existingAttendance.id),
                },
              })
            ).checkinCode;
          return {
            kind: "existing" as const,
            member: effectiveMember,
            attendance: { ...existingAttendance, checkinCode: code },
          };
        }

        const attendanceId = randomUUID();
        const attendance = await tx.attendance.create({
          data: {
            id: attendanceId,
            memberId: effectiveMember.id,
            serviceId: service.id,
            serviceType: "connect",
            connectName: flow.connectName,
            checkinCode: buildCheckinCode("connect", attendanceId),
            serviceDate,
          },
        });

        return {
          kind: "created" as const,
          member: effectiveMember,
          attendance,
        };
      }

      const departmentRecord =
        flow.isWorker && flow.department
          ? await getOrCreateDepartment(tx, flow.department)
          : null;

      const member = await tx.member.create({
        data: {
          firstName: flow.firstName!,
          lastName: flow.lastName!,
          email: flow.email!,
          phoneNumber: flow.phoneNumber,
          gender: flow.gender!,
          maritalStatus: flow.maritalStatus!,
          isWorker: flow.isWorker === true,
          department: flow.isWorker ? flow.department ?? null : null,
          departmentId: departmentRecord?.id ?? null,
          firstTimer: true,
          connectName: flow.connectName,
        },
        select: {
          id: true,
          firstName: true,
          lastName: true,
          firstTimer: true,
          connectName: true,
        },
      });

      const attendanceId = randomUUID();
      const attendance = await tx.attendance.create({
        data: {
          id: attendanceId,
          memberId: member.id,
          serviceId: service.id,
          serviceType: "connect",
          connectName: flow.connectName,
          checkinCode: buildCheckinCode("connect", attendanceId),
          serviceDate,
        },
      });

      await tx.firstTimerEvent.create({
        data: {
          memberId: member.id,
          serviceId: service.id,
          serviceType: "connect",
          serviceName: `connect (${flow.connectName})`,
          serviceDate,
        },
      });

      return {
        kind: "created" as const,
        member,
        attendance,
      };
    });

    if (result.kind === "missing_member") {
      return {
        reply: "I couldn’t find your member record anymore. Please restart this Connect check-in.",
        reset: true,
      };
    }

    const memberName = `${result.member.firstName} ${result.member.lastName}`.trim();
    if (result.kind === "existing") {
      return {
        reply: `You have already checked in for Connect on ${serviceDateLabel}, ${memberName}. Your check-in code is ${result.attendance.checkinCode}.`,
        reset: true,
      };
    }

    if (result.member.firstTimer && flow.memberId) {
      await markFirstTimerEvent(result.member.id, result.attendance.serviceId ?? null, "connect", flow.connectName);
    }

    return {
      reply: `Connect attendance recorded for ${flow.connectName} on ${serviceDateLabel}. Welcome, ${memberName}. Your check-in code is ${result.attendance.checkinCode}.`,
      reset: true,
    };
  } catch (error) {
    if (hasPrismaErrorCode(error, "P2002")) {
      const member = flow.memberId ? await prisma.member.findUnique({ where: { id: flow.memberId } }) : null;
      const serviceDateLabel = formatServiceDate(currentServiceDate());
      return {
        reply: `You have already checked in for Connect on ${serviceDateLabel}${member ? `, ${member.firstName}` : ""}.`,
        reset: true,
      };
    }
    throw error;
  }
}

async function startConnectFlow(sessionId: string, phone: string) {
  if (!isConnectCheckinDay()) {
    await saveState(sessionId, {});
    return "Connect check-in is available from Tuesday to Saturday.";
  }

  const member = await findMemberByPhone(phone);
  if (!member) {
    await saveState(sessionId, {
      pending_checkin_phone: phone,
      pending_service_type: "connect",
      step: "existing_worker_status",
      flow: {
        phoneNumber: phone,
        isNewMember: true,
      },
    });
    return `I couldn’t find your member record, so let’s register you for Connect check-in.\n\n${workerPrompt()}`;
  }

  if (member.isWorker) {
    if (member.department) {
      const storedConnect = normalizeConnectName(member.connectName ?? "");
      if (storedConnect) {
        const result = await completeConnectCheckin({
          phoneNumber: phone,
          memberId: member.id,
          memberName: `${member.firstName} ${member.lastName}`.trim(),
          isWorker: true,
          department: member.department,
          connectName: storedConnect,
        });
        await saveState(sessionId, result.reset ? {} : { pending_checkin_phone: phone, pending_service_type: "connect" });
        return result.reply;
      }

      await saveState(sessionId, {
        pending_checkin_phone: phone,
        pending_service_type: "connect",
        step: "awaiting_connect",
        flow: {
          phoneNumber: phone,
          memberId: member.id,
          memberName: `${member.firstName} ${member.lastName}`.trim(),
          isWorker: true,
          department: member.department,
        },
      });
      return `Welcome back, ${member.firstName}. ${await connectGroupPrompt()}`;
    }

    await saveState(sessionId, {
      pending_checkin_phone: phone,
      pending_service_type: "connect",
      step: "department",
      flow: {
        phoneNumber: phone,
        memberId: member.id,
        memberName: `${member.firstName} ${member.lastName}`.trim(),
        isWorker: true,
      },
    });
    return `Welcome back, ${member.firstName}. ${departmentPrompt()}`;
  }

  await saveState(sessionId, {
    pending_checkin_phone: phone,
    pending_service_type: "connect",
    step: "existing_worker_status",
    flow: {
      phoneNumber: phone,
      memberId: member.id,
      memberName: `${member.firstName} ${member.lastName}`.trim(),
      isNewMember: false,
      isWorker: false,
    },
  });
  return `Welcome back, ${member.firstName}. ${workerPrompt()}`;
}

async function continueConnectFlow(sessionId: string, message: string, state: SessionState) {
  const flow = state.flow;
  if (!flow) {
    await saveState(sessionId, {});
    return "Please send your phone number again to restart Connect check-in.";
  }

  switch (state.step) {
    case "existing_worker_status": {
      const answer = extractYesNo(message);
      if (answer === null) {
        return workerPrompt();
      }

      if (flow.isNewMember) {
        if (answer) {
          await saveState(sessionId, {
            ...state,
            step: "department",
            flow: { ...flow, isWorker: true },
          });
          return departmentPrompt();
        }

        await saveState(sessionId, {
          ...state,
          step: "awaiting_connect",
          flow: { ...flow, isWorker: false, department: null },
        });
        return connectGroupPrompt();
      }

      if (!answer) {
        const member = flow.memberId ? await prisma.member.findUnique({ where: { id: flow.memberId } }) : null;
        const storedConnect = normalizeConnectName(member?.connectName ?? "");
        if (storedConnect) {
          const result = await completeConnectCheckin({
            ...flow,
            isWorker: false,
            department: null,
            connectName: storedConnect,
          });
          await saveState(sessionId, result.reset ? {} : state);
          return result.reply;
        }

        await saveState(sessionId, {
          ...state,
          step: "awaiting_connect",
          flow: { ...flow, isWorker: false, department: null },
        });
        return connectGroupPrompt();
      }

      await saveState(sessionId, {
        ...state,
        step: "department",
        flow: { ...flow, isWorker: true },
      });
      return departmentPrompt();
    }

    case "department": {
      const department = extractDepartment(message);
      if (!department) {
        return departmentPrompt();
      }
      if (department === "Others") {
        await saveState(sessionId, {
          ...state,
          step: "custom_department",
          flow,
        });
        return "Enter your department name.";
      }

      await saveState(sessionId, {
        ...state,
        step: "awaiting_connect",
        flow: { ...flow, department },
      });
      return connectGroupPrompt();
    }

    case "custom_department": {
      const department = message.trim();
      if (!department) {
        return "Enter a valid department name.";
      }

      await saveState(sessionId, {
        ...state,
        step: "awaiting_connect",
        flow: { ...flow, department },
      });
      return connectGroupPrompt();
    }

    case "awaiting_connect": {
      const connectName = await extractConnectName(message);
      if (!connectName) {
        return connectGroupPrompt();
      }

      if (!flow.isNewMember) {
        const result = await completeConnectCheckin({
          ...flow,
          connectName,
        });
        await saveState(sessionId, result.reset ? {} : state);
        return result.reply;
      }

      await saveState(sessionId, {
        ...state,
        step: "new_email",
        flow: { ...flow, connectName },
      });
      return "What is your email address?";
    }

    case "new_email": {
      const email = validateEmail(message);
      if (!email) {
        return "Please enter a valid email address.";
      }
      await saveState(sessionId, {
        ...state,
        step: "new_gender",
        flow: { ...flow, email },
      });
      return genderPrompt();
    }

    case "new_gender": {
      const gender = extractGender(message);
      if (!gender) {
        return genderPrompt();
      }
      await saveState(sessionId, {
        ...state,
        step: "new_first_name",
        flow: { ...flow, gender },
      });
      return "What is your first name?";
    }

    case "new_first_name": {
      const firstName = message.trim();
      if (!firstName) {
        return "Enter your first name.";
      }
      await saveState(sessionId, {
        ...state,
        step: "new_last_name",
        flow: { ...flow, firstName },
      });
      return "What is your last name?";
    }

    case "new_last_name": {
      const lastName = message.trim();
      if (!lastName) {
        return "Enter your last name.";
      }
      await saveState(sessionId, {
        ...state,
        step: "new_marital_status",
        flow: { ...flow, lastName },
      });
      return maritalStatusPrompt();
    }

    case "new_marital_status": {
      const maritalStatus = extractMaritalStatus(message);
      if (!maritalStatus) {
        return maritalStatusPrompt();
      }

      const result = await completeConnectCheckin({
        ...flow,
        maritalStatus,
      });
      await saveState(sessionId, result.reset ? {} : state);
      return result.reply;
    }

    default:
      await saveState(sessionId, {});
      return "Please send your phone number again to restart Connect check-in.";
  }
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

  if (state.pending_service_type === "connect" && state.step) {
    return continueConnectFlow(sessionId, message, state);
  }

  const phone = extractPhone(message);
  const serviceType = normalizeServiceType(message);
  const pendingPhone = state.pending_checkin_phone;

  if (pendingPhone && state.pending_service_type !== "connect") {
    const nextPhone = phone ?? pendingPhone;

    if (!serviceType) {
      const fallbackServiceType = defaultServiceTypeForToday();
      if (fallbackServiceType === "connect") {
        return startConnectFlow(sessionId, nextPhone);
      }
      const reply = await recordStandardCheckin(sessionId, nextPhone, fallbackServiceType);
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
      return startConnectFlow(sessionId, nextPhone);
    }

    const reply = await recordStandardCheckin(sessionId, nextPhone, serviceType);
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
    const fallbackServiceType = defaultServiceTypeForToday();
    if (fallbackServiceType === "connect") {
      return startConnectFlow(sessionId, phone);
    }
    const reply = await recordStandardCheckin(sessionId, phone, fallbackServiceType);
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
    return startConnectFlow(sessionId, phone);
  }

  const reply = await recordStandardCheckin(sessionId, phone, serviceType);
  if (reply.toLowerCase().includes("attendance recorded") || reply.toLowerCase().includes("already checked in")) {
    await saveState(sessionId, {});
  } else {
    await saveState(sessionId, {
      pending_checkin_phone: phone,
    });
  }
  return reply;
}
