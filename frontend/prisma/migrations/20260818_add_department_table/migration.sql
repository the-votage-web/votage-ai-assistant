CREATE TABLE "department" (
    "id" UUID NOT NULL,
    "name" VARCHAR(120) NOT NULL,
    "created_at" TIMESTAMPTZ(6) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "department_pkey" PRIMARY KEY ("id")
);

CREATE UNIQUE INDEX "department_name_key" ON "department"("name");

ALTER TABLE "members"
ADD COLUMN "department_id" UUID;

ALTER TABLE "members"
ADD CONSTRAINT "members_department_id_fkey"
FOREIGN KEY ("department_id") REFERENCES "department"("id")
ON DELETE NO ACTION
ON UPDATE NO ACTION;

CREATE INDEX "members_department_id_idx" ON "members"("department_id");
