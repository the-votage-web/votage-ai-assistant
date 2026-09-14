-- Repair databases that predate the initial Prisma migration history.
-- These statements are safe to apply when the objects already exist.
ALTER TABLE IF EXISTS "members"
ADD COLUMN IF NOT EXISTS "purpose_of_attending" TEXT;

CREATE TABLE IF NOT EXISTS "intake_issues" (
    "id" UUID NOT NULL,
    "kind" TEXT NOT NULL,
    "reason" TEXT,
    "message" TEXT,
    "source" TEXT NOT NULL DEFAULT 'server',
    "http_status" INTEGER,
    "phone" TEXT,
    "email" TEXT,
    "name" TEXT,
    "details" TEXT,
    "session_id" TEXT,
    "created_at" TIMESTAMPTZ(6) DEFAULT CURRENT_TIMESTAMP,
    "resolved_at" TIMESTAMPTZ(6),

    CONSTRAINT "intake_issues_pkey" PRIMARY KEY ("id")
);
