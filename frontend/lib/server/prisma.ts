import { getDatabaseUrl } from "./database-url";

import * as PrismaModule from "@prisma/client";

const { PrismaClient } = PrismaModule as {
  PrismaClient: new (options: { datasources: { db: { url: string } } }) => unknown;
};

const globalForPrisma = globalThis as typeof globalThis & {
  prisma?: any;
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

export const prisma: any = new Proxy({}, {
  get(_target, prop) {
    const client = getPrisma();
    const value = (client as Record<PropertyKey, unknown>)[prop];
    return typeof value === "function" ? value.bind(client) : value;
  },
});
