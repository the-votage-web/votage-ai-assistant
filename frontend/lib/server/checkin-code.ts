const PREFIX_BY_SERVICE: Record<string, string> = {
  sunday_service: "SUN",
  connect: "CON",
  special_service: "SPC",
};

export function buildCheckinCode(serviceType: string, attendanceId: string) {
  const prefix = PREFIX_BY_SERVICE[serviceType] || "CHK";
  const suffix = attendanceId.replace(/-/g, "").slice(-6).toUpperCase();
  return `${prefix}-${suffix}`;
}
