ALTER TABLE "attendance"
ADD COLUMN "checkin_code" VARCHAR(32);

UPDATE "attendance"
SET "checkin_code" = CASE
  WHEN "service_type" = 'sunday_service' THEN 'SUN-'
  WHEN "service_type" = 'connect' THEN 'CON-'
  WHEN "service_type" = 'special_service' THEN 'SPC-'
  ELSE 'CHK-'
END || UPPER(SUBSTRING(REPLACE("id"::text, '-', '') FROM GREATEST(LENGTH(REPLACE("id"::text, '-', '')) - 5, 1)));

ALTER TABLE "attendance"
ALTER COLUMN "checkin_code" SET NOT NULL;

CREATE UNIQUE INDEX "attendance_checkin_code_key"
ON "attendance"("checkin_code");
