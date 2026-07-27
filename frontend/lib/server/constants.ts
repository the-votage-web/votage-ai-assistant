export const DEFAULT_CONNECT_OPTIONS = [
  "KABOD CONNECT",
  "NEWNESS CONNECT",
  "UGBOWO CONNECT",
  "FLOURISH CONNECT",
  "GATEKEEPERS CONNECT",
  "KOINONIA CONNECT",
  "EKEHUAN CONNECT",
] as const;

export const DEFAULT_SERVICE_OPTIONS = [
  "sunday_service",
  "connect",
  "special_service",
] as const;

export type ServiceType = (typeof DEFAULT_SERVICE_OPTIONS)[number];
