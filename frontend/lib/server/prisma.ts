import { getDatabaseUrl } from "./database-url";

import * as PrismaModule from "@prisma/client";

type PrismaClientInstance =
  import("../../node_modules/.prisma/client/index").PrismaClient;

export type PrismaTransactionClient = Omit<
  PrismaClientInstance,
  "$connect" | "$disconnect" | "$on" | "$transaction" | "$extends"
>;

const { PrismaClient } = PrismaModule as unknown as {
  PrismaClient: new (options?: unknown) => PrismaClientInstance;
};

const globalForPrisma = globalThis as typeof globalThis & {
  prisma?: PrismaClientInstance;
};

function createPrismaClient(): PrismaClientInstance {
  return new PrismaClient({
    datasources: {
      db: {
        url: getDatabaseUrl(),
      },
    },
  });
}

export function getPrisma(): PrismaClientInstance {
  if (!globalForPrisma.prisma) {
    globalForPrisma.prisma = createPrismaClient();
  }
  return globalForPrisma.prisma;
}

export const prisma: PrismaClientInstance = new Proxy({} as PrismaClientInstance, {
  get(_target, prop) {
    const client = getPrisma();
    const value = client[prop as keyof PrismaClientInstance];
    return typeof value === "function" ? value.bind(client) : value;
  },
});
