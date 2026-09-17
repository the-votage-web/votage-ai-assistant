/*
  Warnings:

  - You are about to drop the column `email` on the `events_eventparticipation` table. All the data in the column will be lost.

*/
-- DropIndex
DROP INDEX "unique_event_participant_email";

-- DropIndex
DROP INDEX "members_department_id_idx";

-- AlterTable
ALTER TABLE "events_eventparticipation" DROP COLUMN "email",
ADD COLUMN     "attended_sessions" TEXT[] DEFAULT ARRAY[]::TEXT[],
ADD COLUMN     "heard_about_us" VARCHAR(120),
ADD COLUMN     "state_country" VARCHAR(200);
