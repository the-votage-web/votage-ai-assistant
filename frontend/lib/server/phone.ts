import { CountryCode, parsePhoneNumberFromString } from "libphonenumber-js";
import { prisma } from "./prisma";

const memberLookupSelect = {
  id: true,
  firstName: true,
  lastName: true,
  phoneNumber: true,
  email: true,
  firstTimer: true,
  isWorker: true,
  department: true,
  departmentId: true,
  connectName: true,
} as const;

function digitsOnly(value: string) {
  return value.replace(/\D/g, "");
}

function getDefaultPhoneRegion(): CountryCode {
  const region = process.env.DEFAULT_PHONE_REGION?.trim().toUpperCase();
  if (region && /^[A-Z]{2}$/.test(region)) {
    return region as CountryCode;
  }
  return "NG";
}

export function normalizePhone(phone: string) {
  const raw = phone.trim();
  if (!raw) {
    return { e164: null, last10: null };
  }

  const candidate = raw.startsWith("00") ? `+${raw.slice(2)}` : raw;
  const parsed =
    parsePhoneNumberFromString(candidate) ||
    parsePhoneNumberFromString(candidate, getDefaultPhoneRegion());

  if (parsed?.isValid()) {
    const e164 = parsed.number;
    return { e164, last10: digitsOnly(e164).slice(-10) || null };
  }

  const digits = digitsOnly(candidate);
  return { e164: null, last10: digits.slice(-10) || null };
}

export function normalizePhoneForStorage(phone: string) {
  const { e164 } = normalizePhone(phone);
  return e164 ?? phone.trim();
}

export async function findMemberByPhone(phone: string) {
  const raw = phone.trim();
  if (!raw) {
    return null;
  }

  const exact = await prisma.member.findFirst({
    where: { phoneNumber: raw },
    select: memberLookupSelect,
  });
  if (exact) {
    return exact;
  }

  const { e164, last10 } = normalizePhone(raw);
  if (!e164 && !last10) {
    return null;
  }

  const candidates = last10
    ? await prisma.member.findMany({
        where: {
          phoneNumber: {
            endsWith: last10,
          },
        },
        select: memberLookupSelect,
      })
    : [];

  return (
    candidates.find((member: { phoneNumber: string }) => {
      const normalized = normalizePhone(member.phoneNumber);
      if (e164 && normalized.e164 && normalized.e164 === e164) {
        return true;
      }
      return Boolean(last10 && normalized.last10 === last10);
    }) ?? null
  );
}
