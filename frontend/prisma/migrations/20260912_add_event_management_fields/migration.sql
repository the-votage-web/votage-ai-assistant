-- AlterTable
ALTER TABLE "events_event" ADD COLUMN     "end_date" TIMESTAMPTZ(6),
ADD COLUMN     "is_active" BOOLEAN NOT NULL DEFAULT true,
ADD COLUMN     "location" VARCHAR(255),
ADD COLUMN     "name" VARCHAR(150),
ADD COLUMN     "slug" VARCHAR(150),
ADD COLUMN     "start_date" TIMESTAMPTZ(6),
ALTER COLUMN "service_id" DROP NOT NULL;

-- AlterTable
ALTER TABLE "events_eventparticipation" ADD COLUMN     "address" VARCHAR(255),
ADD COLUMN     "checked_in" BOOLEAN NOT NULL DEFAULT false,
ADD COLUMN     "checked_in_at" TIMESTAMPTZ(6),
ADD COLUMN     "city" VARCHAR(100),
ADD COLUMN     "country" VARCHAR(100),
ADD COLUMN     "created_at" TIMESTAMPTZ(6) NOT NULL DEFAULT CURRENT_TIMESTAMP,
ADD COLUMN     "email" VARCHAR(254),
ADD COLUMN     "last_checkin_date" DATE,
ADD COLUMN     "phone_number" VARCHAR(32),
ADD COLUMN     "state" VARCHAR(100);

-- CreateIndex
CREATE UNIQUE INDEX "events_event_slug_key" ON "events_event"("slug");

-- CreateIndex
CREATE UNIQUE INDEX "unique_event_participant_phone" ON "events_eventparticipation"("event_id", "phone_number");

-- CreateIndex
CREATE UNIQUE INDEX "unique_event_participant_email" ON "events_eventparticipation"("event_id", "email");

