import { NextResponse } from "next/server";
import { rateLimit } from "@/lib/server/security";
import { prisma } from "@/lib/server/prisma";

export async function POST(req: Request) {
  const limited = rateLimit(req, "create_event", 10, 60_000);
  if (limited) return limited;

  let payload: any;
  try {
    payload = await req.json();
  } catch {
    return NextResponse.json({ detail: "Invalid JSON payload." }, { status: 400 });
  }

  const { name, event_type, description, location, start_date, end_date } = payload;
  if (!name || typeof name !== "string") {
    return NextResponse.json({ detail: "Name is required and must be a string." }, { status: 422 });
  }

  const slug = payload.slug || name.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/(^-|-$)/g, "");

  try {
    const event = await prisma.$transaction(async (tx) => {
      return await tx.events_event.create({
        data: {
          name,
          slug,
          event_type: event_type || "apostolic_shift",
          description: description || "",
          location: location || null,
          start_date: start_date ? new Date(start_date) : null,
          end_date: end_date ? new Date(end_date) : null,
          created_at: new Date(),
          is_active: true,
        },
      });
    });

    return NextResponse.json({
      id: event.id.toString(),
      name: event.name,
      slug: event.slug,
      event_type: event.event_type,
      description: event.description,
      location: event.location,
      start_date: event.start_date,
      end_date: event.end_date,
      is_active: event.is_active,
    }, { status: 201 });
  } catch (error: any) {
    if (error?.code === "P2002") {
      return NextResponse.json({ detail: "An event with this slug already exists." }, { status: 409 });
    }
    console.error("Error creating event:", error);
    return NextResponse.json({ detail: "An internal error occurred." }, { status: 500 });
  }
}

export async function GET(req: Request) {
  const limited = rateLimit(req, "list_events", 50, 60_000);
  if (limited) return limited;

  try {
    const events = await prisma.events_event.findMany({
      where: { is_active: true },
      orderBy: { created_at: "desc" },
      take: 20,
    });

    return NextResponse.json(
      events.map((e) => ({
        id: e.id.toString(),
        name: e.name,
        slug: e.slug,
        event_type: e.event_type,
        description: e.description,
        location: e.location,
        start_date: e.start_date,
        end_date: e.end_date,
        is_active: e.is_active,
      }))
    );
  } catch (error) {
    console.error("Error fetching events:", error);
    return NextResponse.json({ detail: "An internal error occurred." }, { status: 500 });
  }
}
