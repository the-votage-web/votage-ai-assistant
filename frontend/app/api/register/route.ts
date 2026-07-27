import { randomUUID } from "crypto";
import { NextResponse } from "next/server";
import { buildCheckinCode } from "@/lib/server/checkin-code";
import { DEFAULT_SERVICE_OPTIONS, ServiceType } from "@/lib/server/constants";
import { findMemberByPhone, normalizePhoneForStorage } from "@/lib/server/phone";
import { prisma, type PrismaTransactionClient } from "@/lib/server/prisma";

type TxClient = PrismaTransactionClient;

type RegistrationPayload = {
  first_name?: string;
  last_name?: string;
  email?: string;
  phone_number?: string;
  gender?: string;
  marital_status?: string;
  service_type?: string;
  connect_name?: string | null;
};

const VALID_GENDERS = new Set(["male", "female"]);
const VALID_MARITAL_STATUSES = new Set(["single", "married", "divorced", "widowed"]);

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

function trimRequired(value: unknown, field: string) {
  if (typeof value !== "string" || !value.trim()) {
    throw new Error(`${field} is required`);
  }
  return value.trim();
}

function normalizeServiceType(value: string) {
  const normalized = value.trim().toLowerCase();
  if ((DEFAULT_SERVICE_OPTIONS as readonly string[]).includes(normalized)) {
    return normalized as ServiceType;
  }
  throw new Error(`service_type must be one of: ${DEFAULT_SERVICE_OPTIONS.join(", ")}`);
}

function validateEmail(value: string) {
  const normalized = value.trim().toLowerCase();
  if (!normalized.includes("@") || !normalized.split("@")[1]?.includes(".")) {
    throw new Error("email must be a valid email address");
  }
  return normalized;
}

function validatePhone(value: string) {
  const normalized = normalizePhoneForStorage(value);
  const digits = normalized.startsWith("+") ? normalized.slice(1) : normalized;
  if (!/^\d{7,15}$/.test(digits)) {
    throw new Error("phone_number must be between 7 and 15 digits");
  }
  return normalized;
}

function validatePayload(payload: RegistrationPayload) {
  const firstName = trimRequired(payload.first_name, "first_name");
  const lastName = trimRequired(payload.last_name, "last_name");
  const email = validateEmail(trimRequired(payload.email, "email"));
  const phoneNumber = validatePhone(trimRequired(payload.phone_number, "phone_number"));
  const gender = trimRequired(payload.gender, "gender").toLowerCase();
  const maritalStatus = trimRequired(payload.marital_status, "marital_status").toLowerCase();
  const serviceType = normalizeServiceType(trimRequired(payload.service_type, "service_type"));
  const connectName =
    typeof payload.connect_name === "string" && payload.connect_name.trim() ? payload.connect_name.trim() : null;

  if (!VALID_GENDERS.has(gender)) {
    throw new Error("gender must be one of: female, male");
  }
  if (!VALID_MARITAL_STATUSES.has(maritalStatus)) {
    throw new Error("marital_status must be one of: divorced, married, single, widowed");
  }
  if (serviceType === "connect" && !connectName) {
    throw new Error("connect_name is required when service_type is connect");
  }

  return {
    firstName,
    lastName,
    email,
    phoneNumber,
    gender,
    maritalStatus,
    serviceType,
    connectName: serviceType === "connect" ? connectName : null,
  };
}

async function findExistingMember(phoneNumber: string, email: string) {
  const [byPhone, byEmail] = await Promise.all([
    findMemberByPhone(phoneNumber),
    prisma.member.findFirst({
      where: { email },
    }),
  ]);

  return byPhone ?? byEmail;
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
      description: "Auto-created from registration",
      meetingTime: "TBD",
      meetingDay: "TBD",
    },
  });
}

export async function POST(req: Request) {
  let payload: RegistrationPayload;
  try {
    payload = (await req.json()) as RegistrationPayload;
  } catch {
    return NextResponse.json({ detail: "Invalid registration payload." }, { status: 400 });
  }

  let validated;
  try {
    validated = validatePayload(payload);
  } catch (error) {
    return NextResponse.json(
      { detail: error instanceof Error ? error.message : "Invalid registration payload." },
      { status: 422 },
    );
  }

  const existing = await findExistingMember(validated.phoneNumber, validated.email);
  if (existing) {
    return NextResponse.json(
      {
        error: "duplicate",
        phoneNumber: existing.phoneNumber,
        detail: `A member with these details already exists. Use ${existing.phoneNumber} to check in.`,
      },
      { status: 409 },
    );
  }

  try {
    const serviceDate = currentServiceDate();
    const created = await prisma.$transaction(async (tx: TxClient) => {
      const service = await getOrCreateService(tx, validated.serviceType);
      if (validated.serviceType === "connect" && validated.connectName) {
        await getOrCreateConnectGroup(tx, service.id, validated.connectName);
      }

      const member = await tx.member.create({
        data: {
          firstName: validated.firstName,
          lastName: validated.lastName,
          email: validated.email,
          phoneNumber: validated.phoneNumber,
          gender: validated.gender,
          maritalStatus: validated.maritalStatus,
          firstTimer: true,
          connectName: validated.connectName,
        },
      });

      const attendanceId = randomUUID();
      const checkinCode = buildCheckinCode(validated.serviceType, attendanceId);

      const attendance = await tx.attendance.create({
        data: {
          id: attendanceId,
          memberId: member.id,
          serviceId: service.id,
          serviceType: validated.serviceType,
          connectName: validated.connectName ?? "",
          checkinCode,
          serviceDate,
        },
      });

      await tx.firstTimerEvent.create({
        data: {
          memberId: member.id,
          serviceId: service.id,
          serviceType: validated.serviceType,
          serviceName:
            validated.serviceType === "connect" && validated.connectName
              ? `connect (${validated.connectName})`
              : validated.serviceType.replace(/_/g, " "),
          serviceDate,
        },
      });

      return { attendance };
    });

    return NextResponse.json({
      ok: true,
      message: `Registration completed successfully. Your check-in code is ${created.attendance.checkinCode}.`,
      checkinCode: created.attendance.checkinCode,
    });
  } catch (error) {
    if (hasPrismaErrorCode(error, "P2002")) {
      const duplicate = await findExistingMember(validated.phoneNumber, validated.email);
      return NextResponse.json(
        {
          error: "duplicate",
          phoneNumber: duplicate?.phoneNumber ?? validated.phoneNumber,
          detail: `A member with these details already exists. Use ${duplicate?.phoneNumber ?? validated.phoneNumber} to check in.`,
        },
        { status: 409 },
      );
    }

    return NextResponse.json(
      {
        detail: error instanceof Error ? `Registration failed: ${error.message}` : "Registration failed.",
      },
      { status: 500 },
    );
  }
}
