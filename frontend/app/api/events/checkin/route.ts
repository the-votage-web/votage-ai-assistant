import { NextResponse } from "next/server";
import { rateLimit } from "@/lib/server/security";
import { prisma } from "@/lib/server/prisma";

export async function POST(req: Request) {
  const limited = rateLimit(req, "checkin_event", 100, 60_000);
  if (limited) return limited;

  let payload: any;
  try {
    payload = await req.json();
  } catch {
    return NextResponse.json({ detail: "Invalid JSON payload." }, { status: 400 });
  }

  const { phone_number, event_name } = payload;
  
  if (!phone_number || typeof phone_number !== "string") {
    return NextResponse.json({ detail: "phone_number is required and must be a string." }, { status: 422 });
  }

  const trimmedPhone = phone_number.trim();

  try {
    return await prisma.$transaction(async (tx) => {
      let event;
      if (event_name) {
        event = await tx.events_event.findFirst({
          where: {
            OR: [
              { slug: event_name },
              { name: { equals: event_name, mode: "insensitive" } },
            ],
            is_active: true,
          },
          orderBy: { created_at: "desc" }
        });
      } else {
        event = await tx.events_event.findFirst({
          where: { is_active: true },
          orderBy: { created_at: "desc" }
        });
      }

      if (!event) {
        return NextResponse.json({ detail: "No active event found to check in to." }, { status: 404 });
      }

      const now = new Date();
      if (event.end_date && now > event.end_date) {
        return NextResponse.json({ detail: "This event has already ended." }, { status: 400 });
      }

      const participant = await tx.events_eventparticipation.findFirst({
        where: {
          event_id: event.id,
          phone_number: trimmedPhone
        }
      });

      if (!participant) {
        return NextResponse.json({
          error: "not_registered",
          detail: `We couldn't find a registration with phone number ${trimmedPhone}. Please register for the event first.`
        }, { status: 404 });
      }

      // Dynamic Code Generation
      const initials = (event.name || "Event").split(/[\s-]+/).map(w => w[0]).join("").toUpperCase().substring(0, 3);
      const utcMs = now.getTime() + (now.getTimezoneOffset() * 60000);
      const watTime = new Date(utcMs + (3600000 * 1));
      const day = watTime.getDate().toString().padStart(2, "0");
      const suffix = watTime.getHours() < 12 ? "M" : "E";
      const sessionPrefix = `${initials}-${day}${suffix}`;

      const attendedSessions = participant.attended_sessions || [];

      const existingSession = attendedSessions.find((s: string) => s === sessionPrefix || s.startsWith(`${sessionPrefix}-`));
      if (existingSession) {
        return NextResponse.json({
          checked_in: true,
          already_checked_in_today: true,
          session_code: existingSession,
          detail: `You have already checked in for this session. Your code is ${existingSession}.`
        }, { status: 200 });
      }

      const randomDigits = Math.floor(100000 + Math.random() * 900000).toString();
      const sessionCode = `${sessionPrefix}-${randomDigits}`;

      const updatedSessions = [...attendedSessions, sessionCode];

      const updatedParticipant = await tx.events_eventparticipation.update({
        where: { id: participant.id },
        data: {
          checked_in: true,
          checked_in_at: now,
          last_checkin_date: now,
          attended_sessions: updatedSessions
        }
      });

      return NextResponse.json({
        checked_in: true,
        already_checked_in_today: false,
        session_code: sessionCode,
        detail: `Welcome, ${updatedParticipant.participant_name} to the ${event.name} ${sessionCode}.`
      }, { status: 200 });
    });
  } catch (error) {
    console.error("Error during check-in:", error);
    return NextResponse.json({ detail: "An internal error occurred." }, { status: 500 });
  }
}
