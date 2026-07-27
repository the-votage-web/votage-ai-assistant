import { prisma } from "./prisma";

const MAX_MESSAGE_LEN = 4000;

function clip(text?: string | null) {
  return text ? text.slice(0, MAX_MESSAGE_LEN) : null;
}

function deriveReason(kind: string, httpStatus?: number | null) {
  if (httpStatus === 409) {
    return kind === "registration" ? "phone_exists" : "duplicate";
  }
  if (httpStatus === 422) {
    return "validation_error";
  }
  if (httpStatus && httpStatus >= 500) {
    return "server_error";
  }
  return "ui_error";
}

export async function reportIntakeIssue(args: {
  kind: string;
  message: string;
  httpStatus?: number | null;
  details?: Record<string, unknown> | null;
  sessionId?: string | null;
}) {
  try {
    const details = args.details ?? {};
    const firstName = String(details.first_name ?? "").trim();
    const lastName = String(details.last_name ?? "").trim();
    const fullName = `${firstName} ${lastName}`.trim() || null;

    await prisma.intakeIssue.create({
      data: {
        kind: args.kind === "checkin" ? "checkin" : "registration",
        reason: deriveReason(args.kind, args.httpStatus),
        message: clip(args.message),
        source: "client",
        httpStatus: args.httpStatus ?? null,
        phone: clip(String(details.phone_number ?? details.phone ?? "") || null),
        email: clip(String(details.email ?? "") || null),
        name: clip(fullName),
        details: clip(JSON.stringify(details)),
        sessionId: args.sessionId ?? null,
      },
    });
  } catch (error) {
    console.error("reportIntakeIssue failed", error);
  }
}

export async function logCheckinFailure(args: {
  sessionId?: string | null;
  reason: string;
  message: string;
  phone?: string | null;
  serviceType?: string | null;
  connectName?: string | null;
}) {
  try {
    await prisma.intakeIssue.create({
      data: {
        kind: "checkin",
        reason: args.reason,
        message: clip(args.message),
        source: "server",
        phone: clip(args.phone ?? null),
        details: clip(
          JSON.stringify({
            phone: args.phone ?? null,
            service_type: args.serviceType ?? null,
            connect_name: args.connectName ?? null,
          }),
        ),
        sessionId: args.sessionId ?? null,
      },
    });
  } catch (error) {
    console.error("logCheckinFailure failed", error);
  }
}
