import { NextResponse } from "next/server";

type Bucket = {
  count: number;
  resetAt: number;
};

const rateLimitBuckets = new Map<string, Bucket>();

function cleanupExpiredBuckets(now: number) {
  if (rateLimitBuckets.size < 5000) {
    return;
  }

  for (const [key, bucket] of rateLimitBuckets.entries()) {
    if (bucket.resetAt <= now) {
      rateLimitBuckets.delete(key);
    }
  }
}

export function getClientIp(req: Request) {
  const headers = req.headers;
  const forwarded = headers.get("x-forwarded-for");
  if (forwarded) {
    return forwarded.split(",")[0]?.trim() || "unknown";
  }

  return (
    headers.get("cf-connecting-ip")?.trim() ||
    headers.get("x-real-ip")?.trim() ||
    "unknown"
  );
}

export function rateLimit(req: Request, key: string, limit: number, windowMs: number) {
  const now = Date.now();
  cleanupExpiredBuckets(now);

  const bucketKey = `${key}:${getClientIp(req)}`;
  const existing = rateLimitBuckets.get(bucketKey);

  if (!existing || existing.resetAt <= now) {
    rateLimitBuckets.set(bucketKey, {
      count: 1,
      resetAt: now + windowMs,
    });
    return null;
  }

  if (existing.count >= limit) {
    const retryAfterSeconds = Math.max(1, Math.ceil((existing.resetAt - now) / 1000));
    return NextResponse.json(
      {
        detail: "Too many requests. Please try again shortly.",
      },
      {
        status: 429,
        headers: {
          "Retry-After": String(retryAfterSeconds),
        },
      },
    );
  }

  existing.count += 1;
  rateLimitBuckets.set(bucketKey, existing);
  return null;
}

export function sanitizeServerError(message: string, status = 500) {
  return NextResponse.json({ detail: message }, { status });
}

export function validateSessionId(value: string) {
  return /^[A-Za-z0-9:_-]{6,128}$/.test(value);
}

export function validateMessageLength(value: string, maxLength = 1000) {
  return value.length > 0 && value.length <= maxLength;
}
