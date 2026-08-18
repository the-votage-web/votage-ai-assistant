export const DEFAULT_CONNECT_OPTIONS = [
  "KABOD",
  "NEWNESS",
  "EKEHUAN",
  "FLOURISH",
  "GATEKEEPERS",
  "KOINONIA",
  "UGBOWO",
] as const;

export const DEFAULT_DEPARTMENT_OPTIONS = [
  "RMG",
  "Media",
  "Technical",
  "Ushering",
  "Welfare",
  "VIP",
  "Prayer",
  "Votage_Act",
  "Protocol",
  "Sanitation",
  "Pastorate",
  "Digital_Communication",
  "Others",
] as const;

const CONNECT_ALLOWED_WEEKDAYS = new Set([2, 3, 4, 5, 6]);

export const DEFAULT_SERVICE_OPTIONS = [
  "sunday_service",
  "connect",
  "special_service",
] as const;

export type ServiceType = (typeof DEFAULT_SERVICE_OPTIONS)[number];
export type DepartmentOption = (typeof DEFAULT_DEPARTMENT_OPTIONS)[number];

function normalizeKey(value: string) {
  return value.trim().toLowerCase().replace(/\s+/g, "_");
}

export function normalizeConnectName(value: string) {
  const normalized = normalizeKey(value).replace(/_connect$/, "");
  return DEFAULT_CONNECT_OPTIONS.find((option) => normalizeKey(option) === normalized) ?? null;
}

export function normalizeDepartmentName(value: string) {
  const normalized = normalizeKey(value);
  return DEFAULT_DEPARTMENT_OPTIONS.find((option) => normalizeKey(option) === normalized) ?? null;
}

export function isConnectCheckinDay(date = new Date()) {
  return CONNECT_ALLOWED_WEEKDAYS.has(date.getDay());
}
