import { PrismaClient } from "@prisma/client";
import { getDatabaseUrl } from "./database-url";

const globalForPrisma = globalThis as typeof globalThis & {
  prisma?: PrismaClient;
};

function createPrismaClient() {
  return new PrismaClient({
    datasources: {
      db: {
        url: getDatabaseUrl(),
      },
    },
  });
}

export function getPrisma() {
  if (!globalForPrisma.prisma) {
    globalForPrisma.prisma = createPrismaClient();
  }
  return globalForPrisma.prisma;
}

export const prisma = new Proxy({} as PrismaClient, {
  get(_target, prop) {
    const client = getPrisma();
    const value = (client as unknown as Record<PropertyKey, unknown>)[prop];
    return typeof value === "function" ? value.bind(client) : value;
  },
});
