import { NextResponse } from "next/server";
import { handleCheckin } from "@/lib/server/checkin-flow";

type CheckinPayload = {
  session_id?: string;
  message?: string;
};

export async function POST(req: Request) {
  let payload: CheckinPayload;
  try {
    payload = (await req.json()) as CheckinPayload;
  } catch {
    return NextResponse.json({ detail: "Invalid check-in payload." }, { status: 400 });
  }

  const sessionId = typeof payload.session_id === "string" ? payload.session_id.trim() : "";
  const message = typeof payload.message === "string" ? payload.message.trim() : "";

  if (!sessionId || !message) {
    return NextResponse.json({ detail: "session_id and message are required." }, { status: 422 });
  }

  const reply = await handleCheckin(sessionId, message);
  return NextResponse.json({ reply });
}
