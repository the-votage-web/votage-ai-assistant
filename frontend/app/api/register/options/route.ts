import { NextResponse } from "next/server";
import { prisma } from "@/lib/server/prisma";
import { DEFAULT_CONNECT_OPTIONS, DEFAULT_SERVICE_OPTIONS } from "@/lib/server/constants";

export async function GET() {
  const [services, connectGroups] = await Promise.all([
    prisma.service.findMany({
      select: { name: true },
      distinct: ["name"],
      orderBy: { name: "asc" },
    }),
    prisma.connectGroup.findMany({
      select: { name: true },
      distinct: ["name"],
      orderBy: { name: "asc" },
    }),
  ]);

  const allowed = new Set(DEFAULT_SERVICE_OPTIONS);
  const serviceTypes = services
    .map((service) => service.name.trim().toLowerCase())
    .filter((service) => allowed.has(service as (typeof DEFAULT_SERVICE_OPTIONS)[number]));

  return NextResponse.json({
    service_types: serviceTypes.length > 0 ? Array.from(new Set(serviceTypes)) : [...DEFAULT_SERVICE_OPTIONS],
    connect_groups:
      connectGroups.length > 0
        ? Array.from(new Set(connectGroups.map((group) => group.name.trim()).filter(Boolean)))
        : [...DEFAULT_CONNECT_OPTIONS],
  });
}
