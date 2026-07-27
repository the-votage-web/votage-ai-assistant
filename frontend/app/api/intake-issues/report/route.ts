import { NextResponse } from "next/server";
import { reportIntakeIssue } from "@/lib/server/intake";

type IssueReportPayload = {
  kind?: string;
  message?: string;
  http_status?: number | null;
  details?: Record<string, unknown> | null;
  session_id?: string | null;
};

export async function POST(req: Request) {
  let payload: IssueReportPayload;
  try {
    payload = (await req.json()) as IssueReportPayload;
  } catch {
    return NextResponse.json({ detail: "Invalid intake issue payload." }, { status: 400 });
  }

  if (typeof payload.message !== "string" || !payload.message.trim()) {
    return NextResponse.json({ detail: "message is required." }, { status: 422 });
  }

  await reportIntakeIssue({
    kind: typeof payload.kind === "string" ? payload.kind : "registration",
    message: payload.message.trim(),
    httpStatus: typeof payload.http_status === "number" ? payload.http_status : null,
    details: payload.details ?? null,
    sessionId: typeof payload.session_id === "string" ? payload.session_id : null,
  });

  return NextResponse.json({ ok: true });
}
