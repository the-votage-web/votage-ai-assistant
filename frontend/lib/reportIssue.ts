type ReportArgs = {
  kind: "registration" | "checkin";
  message: string;
  httpStatus?: number;
  details?: Record<string, unknown>;
  sessionId?: string;
};

/** Best-effort: report the exact error the user saw. Never throws. */
export async function reportIssue(args: ReportArgs): Promise<void> {
  try {
    const base = process.env.NEXT_PUBLIC_API_BASE || "";
    const url = base ? `${base}/api/intake-issues/report` : "/api/intake-issues/report";
    await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        kind: args.kind,
        message: args.message,
        http_status: args.httpStatus ?? null,
        details: args.details ?? null,
        session_id: args.sessionId ?? null,
      }),
      keepalive: true,
    });
  } catch {
    // best-effort; never disrupt the user
  }
}
