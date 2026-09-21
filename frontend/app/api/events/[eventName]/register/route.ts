import { NextResponse } from "next/server";
import { rateLimit } from "@/lib/server/security";
import { prisma } from "@/lib/server/prisma";

export async function POST(req: Request, { params }: { params: Promise<{ eventName: string }> | { eventName: string } }) {
  const resolvedParams = await params;
  const eventName = resolvedParams.eventName;

  const limited = rateLimit(req, "register_event", 100, 60_000);
  if (limited) return limited;

  let payload: any;
  try {
    payload = await req.json();
  } catch {
    return NextResponse.json({ detail: "Invalid JSON payload." }, { status: 400 });
  }

  const { full_name, phone_number, state_country, heard_about_us } = payload;
  
  if (!full_name || typeof full_name !== "string") {
    return NextResponse.json({ detail: "full_name is required and must be a string." }, { status: 422 });
  }
  if (!phone_number || typeof phone_number !== "string" || phone_number.trim().length < 11) {
    return NextResponse.json({ detail: "phone_number is required and must be at least 11 digits." }, { status: 422 });
  }

  const trimmedPhone = phone_number.trim();

  try {
    return await prisma.$transaction(async (tx) => {
      const event = await tx.events_event.findFirst({
        where: {
          OR: [
            { slug: eventName },
            { name: { equals: eventName, mode: "insensitive" } },
          ],
          is_active: true,
        },
      });

      if (!event) {
        return NextResponse.json({ detail: "Event not found or is inactive." }, { status: 404 });
      }

      const existing = await tx.events_eventparticipation.findFirst({
        where: {
          event_id: event.id,
          phone_number: trimmedPhone
        }
      });

      if (existing) {
        return NextResponse.json({
          error: "already_registered",
          phone_number: existing.phone_number,
          detail: `You are already registered for this event. You can proceed directly to check in with ${existing.phone_number}.`
        }, { status: 409 });
      }

      let autoCheckedIn = false;
      let sessionCode = "";
      const attendedSessions: string[] = [];
      const now = new Date();
      
      // Auto check-in if registering during the event
      if (event.start_date && event.end_date) {
        if (now >= event.start_date && now <= event.end_date) {
          autoCheckedIn = true;
          const initials = (event.name || "Event").split(/[\s-]+/).map(w => w[0]).join("").toUpperCase().substring(0, 3);
          const utcMs = now.getTime() + (now.getTimezoneOffset() * 60000);
          const watTime = new Date(utcMs + (3600000 * 1));
          const day = watTime.getDate().toString().padStart(2, "0");
          const suffix = watTime.getHours() < 12 ? "M" : "E";
          sessionCode = `${initials}-${day}${suffix}`;
          attendedSessions.push(sessionCode);
        }
      }

      const participant = await tx.events_eventparticipation.create({
        data: {
          participant_name: full_name.trim(),
          role: "attendee",
          event_id: event.id,
          phone_number: trimmedPhone,
          state_country: state_country?.trim() || null,
          heard_about_us: heard_about_us?.trim() || null,
          checked_in: autoCheckedIn,
          checked_in_at: autoCheckedIn ? now : null,
          last_checkin_date: autoCheckedIn ? now : null,
          attended_sessions: attendedSessions,
          created_at: now
        }
      });

      if (autoCheckedIn) {
        return NextResponse.json({
          id: participant.id.toString(),
          event_id: participant.event_id.toString(),
          participant_name: participant.participant_name,
          phone_number: participant.phone_number,
          session_code: sessionCode,
          detail: `Registration and check-in successful! Welcome to ${event.name}, ${participant.participant_name}. Your code is ${sessionCode}.`
        }, { status: 201 });
      }

      return NextResponse.json({
        id: participant.id.toString(),
        event_id: participant.event_id.toString(),
        participant_name: participant.participant_name,
        phone_number: participant.phone_number,
        detail: "Registration successful. We look forward to seeing you!"
      }, { status: 201 });
    });
  } catch (error: any) {
    if (error?.code === "P2002") {
      return NextResponse.json({ detail: "You are already registered." }, { status: 409 });
    }
    console.error("Error registering participant:", error);
    return NextResponse.json({ detail: "An internal error occurred." }, { status: 500 });
  }
}
