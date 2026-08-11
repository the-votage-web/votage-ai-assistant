import { NextResponse } from "next/server";
import { handleFaq } from "@/lib/server/faq";
import { rateLimit, sanitizeServerError, validateMessageLength, validateSessionId } from "@/lib/server/security";

type ChatPayload = {
  session_id?: string;
  message?: string;
};

export async function POST(req: Request) {
  const limited = rateLimit(req, "chat", 20, 60_000);
  if (limited) {
    return limited;
  }

  let payload: ChatPayload;
  try {
    payload = (await req.json()) as ChatPayload;
  } catch {
    return NextResponse.json({ detail: "Invalid chat payload." }, { status: 400 });
  }

  const sessionId = typeof payload.session_id === "string" ? payload.session_id.trim() : "";
  const message = typeof payload.message === "string" ? payload.message.trim() : "";

  if (!validateSessionId(sessionId) || !validateMessageLength(message, 1000)) {
    return NextResponse.json(
      { detail: "session_id and message are required and must be valid." },
      { status: 422 },
    );
  }

  try {
    const reply = await handleFaq(sessionId, message);
    return NextResponse.json({ reply });
  } catch (error) {
    console.error("chat route failed", error);
    return sanitizeServerError("Chat is temporarily unavailable.", 503);
  }
}
