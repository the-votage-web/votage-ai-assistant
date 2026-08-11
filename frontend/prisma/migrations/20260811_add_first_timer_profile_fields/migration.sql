ALTER TABLE "members"
ADD COLUMN IF NOT EXISTS "address" VARCHAR(255),
ADD COLUMN IF NOT EXISTS "date_of_birth" DATE,
ADD COLUMN IF NOT EXISTS "employment_status" VARCHAR(32),
ADD COLUMN IF NOT EXISTS "heard_about_church" VARCHAR(32),
ADD COLUMN IF NOT EXISTS "heard_about_church_other" VARCHAR(120),
ADD COLUMN IF NOT EXISTS "purpose_of_attending" TEXT,
ADD COLUMN IF NOT EXISTS "would_like_to_be_member" VARCHAR(16);
