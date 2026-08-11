import { randomUUID } from "crypto";
import { NextResponse } from "next/server";
import { buildCheckinCode } from "@/lib/server/checkin-code";
import { findMemberByPhone, normalizePhoneForStorage } from "@/lib/server/phone";
import { prisma, type PrismaTransactionClient } from "@/lib/server/prisma";
import { Prisma } from "@prisma/client";
import { rateLimit } from "@/lib/server/security";

const VALID_GENDERS = new Set(["male", "female"]);
const VALID_RELATIONSHIP_STATUSES = new Set(["single", "married"]);
const VALID_EMPLOYMENT_STATUSES = new Set(["employed", "unemployed", "student"]);
const VALID_HEARD_ABOUT = new Set(["social_media", "evangelism", "refresh", "friend", "others"]);
const VALID_MEMBER_INTEREST = new Set(["no", "maybe", "yes"]);

type FirstTimerSubmissionPayload = {
  phone_number?: string;
  name?: string;
  address?: string;
  email?: string;
  gender?: string;
  date_of_birth?: string;
  relationship_status?: string;
  employment_status?: string;
  heard_about_church?: string;
  heard_about_church_other?: string | null;
  purpose_of_attending?: string;
  would_like_to_be_member?: string;
};

function latestSunday(from = new Date()) {
  const date = new Date(from.getFullYear(), from.getMonth(), from.getDate());
  const daysSinceSunday = (date.getDay() + 7) % 7;
  date.setDate(date.getDate() - daysSinceSunday);
  return date;
}

type TxClient = PrismaTransactionClient;

async function getOrCreateSundayService(tx: TxClient) {
  const existing = await tx.service.findFirst({
    where: {
      name: {
        equals: "sunday_service",
        mode: "insensitive",
      },
    },
  });

  if (existing) {
    return existing;
  }

  return tx.service.create({
    data: {
      name: "sunday_service",
    },
  });
}

function trimRequired(value: unknown, field: string) {
  if (typeof value !== "string" || !value.trim()) {
    throw new Error(`${field} is required`);
  }
  return value.trim();
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

function validateDate(value: string) {
  const parsed = new Date(`${value}T00:00:00`);
  if (Number.isNaN(parsed.getTime())) {
    throw new Error("date_of_birth must be a valid date in YYYY-MM-DD format");
  }
  return parsed;
}

function splitName(value: string) {
  const parts = value.trim().split(/\s+/).filter(Boolean);
  if (parts.length < 2) {
    throw new Error("name must include at least first and last name");
  }
  return {
    firstName: parts[0],
    lastName: parts.slice(1).join(" "),
  };
}

function validatePayload(payload: FirstTimerSubmissionPayload) {
  const phoneNumber = validatePhone(trimRequired(payload.phone_number, "phone_number"));
  const { firstName, lastName } = splitName(trimRequired(payload.name, "name"));
  const address = trimRequired(payload.address, "address");
  const email = validateEmail(trimRequired(payload.email, "email"));
  const gender = trimRequired(payload.gender, "gender").toLowerCase();
  const relationshipStatus = trimRequired(payload.relationship_status, "relationship_status").toLowerCase();
  const employmentStatus = trimRequired(payload.employment_status, "employment_status").toLowerCase();
  const heardAboutChurch = trimRequired(payload.heard_about_church, "heard_about_church").toLowerCase().replace(/\s+/g, "_");
  const heardAboutChurchOther =
    typeof payload.heard_about_church_other === "string" && payload.heard_about_church_other.trim()
      ? payload.heard_about_church_other.trim()
      : null;
  const purposeOfAttending = trimRequired(payload.purpose_of_attending, "purpose_of_attending");
  const wouldLikeToBeMember = trimRequired(payload.would_like_to_be_member, "would_like_to_be_member").toLowerCase();
  const dateOfBirth = validateDate(trimRequired(payload.date_of_birth, "date_of_birth"));

  if (!VALID_GENDERS.has(gender)) {
    throw new Error("gender must be one of: female, male");
  }
  if (!VALID_RELATIONSHIP_STATUSES.has(relationshipStatus)) {
    throw new Error("relationship_status must be one of: married, single");
  }
  if (!VALID_EMPLOYMENT_STATUSES.has(employmentStatus)) {
    throw new Error("employment_status must be one of: employed, student, unemployed");
  }
  if (!VALID_HEARD_ABOUT.has(heardAboutChurch)) {
    throw new Error("heard_about_church must be one of: evangelism, friend, others, refresh, social_media");
  }
  if (heardAboutChurch === "others" && !heardAboutChurchOther) {
    throw new Error("heard_about_church_other is required when heard_about_church is others");
  }
  if (!VALID_MEMBER_INTEREST.has(wouldLikeToBeMember)) {
    throw new Error("would_like_to_be_member must be one of: maybe, no, yes");
  }

  return {
    phoneNumber,
    firstName,
    lastName,
    address,
    email,
    gender,
    dateOfBirth,
    relationshipStatus,
    employmentStatus,
    heardAboutChurch,
    heardAboutChurchOther: heardAboutChurch === "others" ? heardAboutChurchOther : null,
    purposeOfAttending,
    wouldLikeToBeMember,
  };
}

function hasPrismaErrorCode(error: unknown, code: string) {
  return (
    typeof error === "object" &&
    error !== null &&
    "code" in error &&
    (error as { code?: unknown }).code === code
  );
}

async function updateExtendedMemberFields(
  tx: TxClient,
  memberId: string,
  validated: ReturnType<typeof validatePayload>,
) {
  await tx.$executeRaw(
    Prisma.sql`
      UPDATE "members"
      SET
        "address" = ${validated.address},
        "date_of_birth" = ${validated.dateOfBirth},
        "employment_status" = ${validated.employmentStatus},
        "heard_about_church" = ${validated.heardAboutChurch},
        "heard_about_church_other" = ${validated.heardAboutChurchOther},
        "purpose_of_attending" = ${validated.purposeOfAttending},
        "would_like_to_be_member" = ${validated.wouldLikeToBeMember}
      WHERE "id" = ${memberId}::uuid
    `,
  );
}

export async function POST(req: Request) {
  const limited = rateLimit(req, "first-timer", 5, 15 * 60_000);
  if (limited) {
    return limited;
  }

  let payload: FirstTimerSubmissionPayload;
  try {
    payload = (await req.json()) as FirstTimerSubmissionPayload;
  } catch {
    return NextResponse.json({ detail: "Invalid first timer payload." }, { status: 400 });
  }

  let validated;
  try {
    validated = validatePayload(payload);
  } catch (error) {
    return NextResponse.json(
      { detail: error instanceof Error ? error.message : "Invalid first timer payload." },
      { status: 422 },
    );
  }

  const sunday = latestSunday();
  const member = await findMemberByPhone(validated.phoneNumber);
  if (member) {
    if (!member.firstTimer) {
      return NextResponse.json(
        { detail: "This phone number cannot use the first-timer form." },
        { status: 403 },
      );
    }

    const storedPhone = normalizePhoneForStorage(member.phoneNumber);
    if (storedPhone !== validated.phoneNumber) {
      return NextResponse.json(
        { detail: "Phone number does not match the member record." },
        { status: 403 },
      );
    }
  }

  try {
    const updated = await prisma.$transaction(async (tx: TxClient) => {
      const service = await getOrCreateSundayService(tx);
      let autoCheckedIn = false;
      let createdMember = false;

      const savedMember = member
        ? await tx.member.update({
            where: { id: member.id },
            data: {
              firstName: validated.firstName,
              lastName: validated.lastName,
              phoneNumber: validated.phoneNumber,
              email: validated.email,
              gender: validated.gender,
              maritalStatus: validated.relationshipStatus,
              firstTimer: true,
            },
            select: {
              id: true,
            },
          })
        : await tx.member.create({
            data: {
              firstName: validated.firstName,
              lastName: validated.lastName,
              phoneNumber: validated.phoneNumber,
              email: validated.email,
              gender: validated.gender,
              maritalStatus: validated.relationshipStatus,
              firstTimer: true,
            },
            select: {
              id: true,
            },
          });

      if (!member) {
        createdMember = true;
      }

      await updateExtendedMemberFields(tx, savedMember.id, validated);

      const attendance = await tx.attendance.findFirst({
        where: {
          memberId: savedMember.id,
          serviceDate: sunday,
          serviceType: "sunday_service",
          connectName: "",
        },
        select: {
          id: true,
        },
      });

      if (!attendance) {
        const attendanceId = randomUUID();
        autoCheckedIn = true;
        await tx.attendance.create({
          data: {
            id: attendanceId,
            memberId: savedMember.id,
            serviceId: service.id,
            serviceType: "sunday_service",
            connectName: "",
            checkinCode: buildCheckinCode("sunday_service", attendanceId),
            serviceDate: sunday,
          },
        });
      }

      const firstTimerEvent = await tx.firstTimerEvent.findFirst({
        where: {
          memberId: savedMember.id,
          serviceDate: sunday,
          serviceName: "sunday service",
        },
        select: {
          id: true,
        },
      });

      if (!firstTimerEvent) {
        await tx.firstTimerEvent.create({
          data: {
            memberId: savedMember.id,
            serviceId: service.id,
            serviceType: "sunday_service",
            serviceName: "sunday service",
            serviceDate: sunday,
          },
        });
      }

      return { memberId: savedMember.id, autoCheckedIn, createdMember };
    });

    return NextResponse.json({
      ok: true,
      message: updated.autoCheckedIn
        ? "Thank you. Your first-timer information has been submitted successfully, and we checked you in for the latest Sunday service automatically."
        : "Thank you. Your first-timer information has been submitted successfully.",
      member_id: updated.memberId,
      auto_checked_in: updated.autoCheckedIn,
      created_member: updated.createdMember,
    });
  } catch (error) {
    if (hasPrismaErrorCode(error, "P2002")) {
      return NextResponse.json(
        { detail: "Another member already uses this phone number or email address." },
        { status: 409 },
      );
    }

    return NextResponse.json(
      {
        detail: "Failed to submit first timer information. Please try again shortly.",
      },
      { status: 500 },
    );
  }
}
