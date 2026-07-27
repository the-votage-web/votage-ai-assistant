import { NextResponse } from "next/server";
import { handleFaq } from "@/lib/server/faq";

type ChatPayload = {
  session_id?: string;
  message?: string;
};

export async function POST(req: Request) {
  let payload: ChatPayload;
  try {
    payload = (await req.json()) as ChatPayload;
  } catch {
    return NextResponse.json({ detail: "Invalid chat payload." }, { status: 400 });
  }

  const sessionId = typeof payload.session_id === "string" ? payload.session_id.trim() : "";
  const message = typeof payload.message === "string" ? payload.message.trim() : "";

  if (!sessionId || !message) {
    return NextResponse.json({ detail: "session_id and message are required." }, { status: 422 });
  }

  try {
    const reply = await handleFaq(sessionId, message);
    return NextResponse.json({ reply });
  } catch (error) {
    const detail =
      error instanceof Error ? error.message : "Chat is temporarily unavailable.";
    return NextResponse.json({ detail }, { status: 503 });
  }
}
