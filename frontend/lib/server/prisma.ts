import { getDatabaseUrl } from "./database-url";

import * as PrismaModule from "@prisma/client";

const { PrismaClient } = PrismaModule as unknown as {
  PrismaClient: new (options?: unknown) => Record<PropertyKey, unknown>;
};

type PrismaClientInstance = ReturnType<typeof createPrismaClient>;

const globalForPrisma = globalThis as typeof globalThis & {
  prisma?: PrismaClientInstance;
};

function createPrismaClient() {
  return new PrismaClient({
    datasources: {
      db: {
        url: getDatabaseUrl(),
      },
    },
  }) as Record<PropertyKey, unknown>;
}

export function getPrisma() {
  if (!globalForPrisma.prisma) {
    globalForPrisma.prisma = createPrismaClient();
  }
  return globalForPrisma.prisma;
}

export const prisma: PrismaClientInstance = new Proxy({} as PrismaClientInstance, {
  get(_target, prop) {
    const client = getPrisma();
    const value = (client as Record<PropertyKey, unknown>)[prop];
    return typeof value === "function" ? value.bind(client) : value;
  },
});
