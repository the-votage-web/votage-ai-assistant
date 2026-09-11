import { NextResponse } from "next/server";
import { rateLimit } from "@/lib/server/security";
import { prisma } from "@/lib/server/prisma";

export async function POST(req: Request, { params }: { params: Promise<{ eventName: string }> | { eventName: string } }) {
  const resolvedParams = await params;
  const eventName = resolvedParams.eventName;

  const limited = rateLimit(req, "register_event", 10, 60_000);
  if (limited) return limited;

  let payload: any;
  try {
    payload = await req.json();
  } catch {
    return NextResponse.json({ detail: "Invalid JSON payload." }, { status: 400 });
  }

  const { full_name, phone_number, email, city, state, country } = payload;
  
  if (!full_name || typeof full_name !== "string") {
    return NextResponse.json({ detail: "full_name is required and must be a string." }, { status: 422 });
  }
  if (!phone_number || typeof phone_number !== "string" || phone_number.trim().length < 11) {
    return NextResponse.json({ detail: "phone_number is required and must be at least 11 digits." }, { status: 422 });
  }
  if (!email || typeof email !== "string") {
    return NextResponse.json({ detail: "email is required and must be a string." }, { status: 422 });
  }

  const trimmedPhone = phone_number.trim();
  const trimmedEmail = email.trim().toLowerCase();

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
          OR: [
            { phone_number: trimmedPhone },
            { email: trimmedEmail }
          ]
        }
      });

      if (existing) {
        return NextResponse.json({
          error: "already_registered",
          phone_number: existing.phone_number,
          detail: `You are already registered for this event. You can proceed directly to check in with ${existing.phone_number}.`
        }, { status: 409 });
      }

      const participant = await tx.events_eventparticipation.create({
        data: {
          participant_name: full_name.trim(),
          role: "attendee",
          event_id: event.id,
          phone_number: trimmedPhone,
          email: trimmedEmail,
          city: city?.trim() || null,
          state: state?.trim() || null,
          country: country?.trim() || null,
          checked_in: false,
          created_at: new Date()
        }
      });

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
