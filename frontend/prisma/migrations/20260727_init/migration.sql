-- CreateSchema
CREATE SCHEMA IF NOT EXISTS "public";

-- CreateExtension
CREATE EXTENSION IF NOT EXISTS vector;

-- CreateTable
CREATE TABLE "members" (
    "id" UUID NOT NULL,
    "first_name" VARCHAR(80) NOT NULL,
    "last_name" VARCHAR(80) NOT NULL,
    "phone_number" VARCHAR(32) NOT NULL,
    "email" VARCHAR(254),
    "created_at" TIMESTAMPTZ(6) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "gender" VARCHAR(32),
    "marital_status" VARCHAR(32),
    "first_timer" BOOLEAN NOT NULL,
    "connect_name" VARCHAR(80),
    "date_joined" TIMESTAMPTZ(6) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "birthday" VARCHAR(4),

    CONSTRAINT "members_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "service" (
    "id" UUID NOT NULL,
    "name" VARCHAR(80) NOT NULL,
    "theme" VARCHAR(80),
    "location" VARCHAR(80),
    "created_at" TIMESTAMPTZ(6) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "service_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "connect_group" (
    "id" UUID NOT NULL,
    "service_id" UUID,
    "name" VARCHAR(80) NOT NULL,
    "description" VARCHAR(254) NOT NULL,
    "meeting_time" VARCHAR(80) NOT NULL,
    "meeting_day" VARCHAR(20) NOT NULL,
    "created_at" TIMESTAMPTZ(6) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "connect_group_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "attendance" (
    "id" UUID NOT NULL,
    "member_id" UUID NOT NULL,
    "service_id" UUID,
    "service_type" VARCHAR(32) NOT NULL,
    "connect_name" VARCHAR(80),
    "service_date" DATE NOT NULL,
    "created_at" TIMESTAMPTZ(6) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "attendance_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "chat_sessions" (
    "id" VARCHAR(64) NOT NULL,
    "state_json" TEXT NOT NULL,
    "created_at" TIMESTAMPTZ(6) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "chat_sessions_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "first_timer_events" (
    "id" UUID NOT NULL,
    "member_id" UUID NOT NULL,
    "service_id" UUID,
    "service_type" VARCHAR(32) NOT NULL,
    "service_name" VARCHAR(120) NOT NULL,
    "service_date" DATE NOT NULL,
    "created_at" TIMESTAMPTZ(6) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "first_timer_events_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "intake_issues" (
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

-- CreateTable
CREATE TABLE "alembic_version" (
    "version_num" VARCHAR(32) NOT NULL,

    CONSTRAINT "alembic_version_pkc" PRIMARY KEY ("version_num")
);

-- CreateTable
CREATE TABLE "attendance_attendance" (
    "id" BIGSERIAL NOT NULL,
    "created_at" TIMESTAMPTZ(6) NOT NULL,
    "member_id" BIGINT NOT NULL,
    "service_id" BIGINT NOT NULL,

    CONSTRAINT "attendance_attendance_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "auth_group" (
    "id" SERIAL NOT NULL,
    "name" VARCHAR(150) NOT NULL,

    CONSTRAINT "auth_group_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "auth_group_permissions" (
    "id" BIGSERIAL NOT NULL,
    "group_id" INTEGER NOT NULL,
    "permission_id" INTEGER NOT NULL,

    CONSTRAINT "auth_group_permissions_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "auth_permission" (
    "id" SERIAL NOT NULL,
    "name" VARCHAR(255) NOT NULL,
    "content_type_id" INTEGER NOT NULL,
    "codename" VARCHAR(100) NOT NULL,

    CONSTRAINT "auth_permission_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "auth_user" (
    "id" SERIAL NOT NULL,
    "password" VARCHAR(128) NOT NULL,
    "last_login" TIMESTAMPTZ(6),
    "is_superuser" BOOLEAN NOT NULL,
    "username" VARCHAR(150) NOT NULL,
    "first_name" VARCHAR(150) NOT NULL,
    "last_name" VARCHAR(150) NOT NULL,
    "email" VARCHAR(254) NOT NULL,
    "is_staff" BOOLEAN NOT NULL,
    "is_active" BOOLEAN NOT NULL,
    "date_joined" TIMESTAMPTZ(6) NOT NULL,

    CONSTRAINT "auth_user_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "auth_user_groups" (
    "id" BIGSERIAL NOT NULL,
    "user_id" INTEGER NOT NULL,
    "group_id" INTEGER NOT NULL,

    CONSTRAINT "auth_user_groups_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "auth_user_user_permissions" (
    "id" BIGSERIAL NOT NULL,
    "user_id" INTEGER NOT NULL,
    "permission_id" INTEGER NOT NULL,

    CONSTRAINT "auth_user_user_permissions_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "chat_logs" (
    "id" UUID NOT NULL,
    "session_id" TEXT,
    "question" TEXT,
    "answer" TEXT,
    "answered" BOOLEAN,
    "top_score" DOUBLE PRECISION,
    "created_at" TIMESTAMPTZ(6) DEFAULT CURRENT_TIMESTAMP,
    "resolved_at" TIMESTAMPTZ(6),

    CONSTRAINT "chat_logs_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "connect_group_members" (
    "id" UUID NOT NULL,
    "connect_group_id" UUID NOT NULL,
    "member_id" UUID NOT NULL,
    "created_at" TIMESTAMPTZ(6) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "left_at" TIMESTAMPTZ(6),

    CONSTRAINT "connect_group_members_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "connect_groups_connectgroup" (
    "id" BIGSERIAL NOT NULL,
    "name" VARCHAR(150) NOT NULL,
    "description" TEXT NOT NULL,
    "meeting_day" VARCHAR(20) NOT NULL,
    "meeting_time" TIME(6) NOT NULL,
    "created_at" TIMESTAMPTZ(6) NOT NULL,

    CONSTRAINT "connect_groups_connectgroup_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "connect_groups_connectgroupmember" (
    "id" BIGSERIAL NOT NULL,
    "joined_at" DATE NOT NULL,
    "left_at" DATE,
    "connect_group_id" BIGINT NOT NULL,
    "member_id" BIGINT NOT NULL,

    CONSTRAINT "connect_groups_connectgroupmember_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "connect_groups_connectgrouppastor" (
    "id" BIGSERIAL NOT NULL,
    "start_date" DATE NOT NULL,
    "end_date" DATE,
    "connect_group_id" BIGINT NOT NULL,
    "pastor_id" BIGINT NOT NULL,

    CONSTRAINT "connect_groups_connectgrouppastor_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "django_admin_log" (
    "id" SERIAL NOT NULL,
    "action_time" TIMESTAMPTZ(6) NOT NULL,
    "object_id" TEXT,
    "object_repr" VARCHAR(200) NOT NULL,
    "action_flag" SMALLINT NOT NULL,
    "change_message" TEXT NOT NULL,
    "content_type_id" INTEGER,
    "user_id" INTEGER NOT NULL,

    CONSTRAINT "django_admin_log_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "django_content_type" (
    "id" SERIAL NOT NULL,
    "app_label" VARCHAR(100) NOT NULL,
    "model" VARCHAR(100) NOT NULL,

    CONSTRAINT "django_content_type_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "django_migrations" (
    "id" BIGSERIAL NOT NULL,
    "app" VARCHAR(255) NOT NULL,
    "name" VARCHAR(255) NOT NULL,
    "applied" TIMESTAMPTZ(6) NOT NULL,

    CONSTRAINT "django_migrations_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "django_session" (
    "session_key" VARCHAR(40) NOT NULL,
    "session_data" TEXT NOT NULL,
    "expire_date" TIMESTAMPTZ(6) NOT NULL,

    CONSTRAINT "django_session_pkey" PRIMARY KEY ("session_key")
);

-- CreateTable
CREATE TABLE "events_event" (
    "id" BIGSERIAL NOT NULL,
    "event_type" VARCHAR(100) NOT NULL,
    "description" TEXT NOT NULL,
    "created_at" TIMESTAMPTZ(6) NOT NULL,
    "service_id" BIGINT NOT NULL,

    CONSTRAINT "events_event_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "events_eventparticipation" (
    "id" BIGSERIAL NOT NULL,
    "participant_name" VARCHAR(255) NOT NULL,
    "role" VARCHAR(100) NOT NULL,
    "event_id" BIGINT NOT NULL,
    "member_id" BIGINT,

    CONSTRAINT "events_eventparticipation_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "faq_embeddings" (
    "id" TEXT NOT NULL,
    "question" TEXT,
    "answer" TEXT,
    "text" TEXT,
    "embedding" vector(1536),
    "metadata" JSONB,

    CONSTRAINT "faq_embeddings_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "growth_track_growthtrack" (
    "id" BIGSERIAL NOT NULL,
    "cohort_name" VARCHAR(100) NOT NULL,
    "start_date" DATE NOT NULL,
    "end_date" DATE NOT NULL,
    "status" VARCHAR(20) NOT NULL,
    "created_at" TIMESTAMPTZ(6) NOT NULL,

    CONSTRAINT "growth_track_growthtrack_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "growth_track_growthtrackenrollment" (
    "id" BIGSERIAL NOT NULL,
    "enrollment_date" DATE NOT NULL,
    "status" VARCHAR(20) NOT NULL,
    "graduation_date" DATE,
    "growth_track_id" BIGINT NOT NULL,
    "member_id" BIGINT NOT NULL,

    CONSTRAINT "growth_track_growthtrackenrollment_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "kb_entries" (
    "id" UUID NOT NULL,
    "question" TEXT NOT NULL,
    "answer" TEXT NOT NULL,
    "source" TEXT NOT NULL DEFAULT 'admin',
    "created_at" TIMESTAMPTZ(6) DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMPTZ(6),
    "exported_at" TIMESTAMPTZ(6),

    CONSTRAINT "kb_entries_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "members_firsttimers" (
    "id" BIGSERIAL NOT NULL,
    "service_name" VARCHAR(200) NOT NULL,
    "service_date" DATE NOT NULL,
    "created_at" TIMESTAMPTZ(6) NOT NULL,
    "member_id" BIGINT NOT NULL,
    "service_id_id" BIGINT,

    CONSTRAINT "members_firsttimers_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "members_member" (
    "id" BIGSERIAL NOT NULL,
    "first_name" VARCHAR(100) NOT NULL,
    "last_name" VARCHAR(100) NOT NULL,
    "phone_number" VARCHAR(20) NOT NULL,
    "email" VARCHAR(254) NOT NULL,
    "birthday" VARCHAR(4),
    "gender" VARCHAR(10) NOT NULL,
    "member_status" VARCHAR(20) NOT NULL,
    "date_joined" DATE,

    CONSTRAINT "members_member_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "pastors_pastor" (
    "id" BIGSERIAL NOT NULL,
    "first_name" VARCHAR(100) NOT NULL,
    "last_name" VARCHAR(100) NOT NULL,
    "phone" VARCHAR(20) NOT NULL,
    "email" VARCHAR(254) NOT NULL,

    CONSTRAINT "pastors_pastor_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "rag_documents" (
    "id" UUID NOT NULL,
    "collection_name" VARCHAR(120) NOT NULL,
    "page_content" TEXT NOT NULL,
    "metadata" JSONB NOT NULL DEFAULT '{}',
    "created_at" TIMESTAMPTZ(6) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "rag_documents_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "services_service" (
    "id" BIGSERIAL NOT NULL,
    "service_date" DATE NOT NULL,
    "theme" VARCHAR(255) NOT NULL,
    "location" VARCHAR(255) NOT NULL,
    "connect_group_id" BIGINT,
    "service_type_id" BIGINT NOT NULL,

    CONSTRAINT "services_service_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "services_servicetype" (
    "id" BIGSERIAL NOT NULL,
    "name" VARCHAR(100) NOT NULL,
    "description" TEXT NOT NULL,
    "is_recurring" BOOLEAN NOT NULL,

    CONSTRAINT "services_servicetype_pkey" PRIMARY KEY ("id")
);

-- CreateIndex
CREATE UNIQUE INDEX "members_phone_number_key" ON "members"("phone_number");

-- CreateIndex
CREATE UNIQUE INDEX "members_email_key" ON "members"("email");

-- CreateIndex
CREATE UNIQUE INDEX "uq_member_day_service_connect" ON "attendance"("member_id", "service_date", "service_type", "connect_name");

-- CreateIndex
CREATE UNIQUE INDEX "uq_first_timer_member_day_event" ON "first_timer_events"("member_id", "service_date", "service_name");

-- CreateIndex
CREATE INDEX "attendance__created_a6132d_idx" ON "attendance_attendance"("created_at");

-- CreateIndex
CREATE INDEX "attendance__member__481773_idx" ON "attendance_attendance"("member_id");

-- CreateIndex
CREATE INDEX "attendance__service_a282dc_idx" ON "attendance_attendance"("service_id");

-- CreateIndex
CREATE INDEX "attendance__service_bb20a3_idx" ON "attendance_attendance"("service_id", "member_id");

-- CreateIndex
CREATE INDEX "attendance_attendance_member_id_9777e18b" ON "attendance_attendance"("member_id");

-- CreateIndex
CREATE INDEX "attendance_attendance_service_id_904d6c3f" ON "attendance_attendance"("service_id");

-- CreateIndex
CREATE UNIQUE INDEX "unique_attendance_per_service" ON "attendance_attendance"("member_id", "service_id");

-- CreateIndex
CREATE UNIQUE INDEX "auth_group_name_key" ON "auth_group"("name");

-- CreateIndex
CREATE INDEX "auth_group_name_a6ea08ec_like" ON "auth_group"("name");

-- CreateIndex
CREATE INDEX "auth_group_permissions_group_id_b120cbf9" ON "auth_group_permissions"("group_id");

-- CreateIndex
CREATE INDEX "auth_group_permissions_permission_id_84c5c92e" ON "auth_group_permissions"("permission_id");

-- CreateIndex
CREATE UNIQUE INDEX "auth_group_permissions_group_id_permission_id_0cd325b0_uniq" ON "auth_group_permissions"("group_id", "permission_id");

-- CreateIndex
CREATE INDEX "auth_permission_content_type_id_2f476e4b" ON "auth_permission"("content_type_id");

-- CreateIndex
CREATE UNIQUE INDEX "auth_permission_content_type_id_codename_01ab375a_uniq" ON "auth_permission"("content_type_id", "codename");

-- CreateIndex
CREATE UNIQUE INDEX "auth_user_username_key" ON "auth_user"("username");

-- CreateIndex
CREATE INDEX "auth_user_username_6821ab7c_like" ON "auth_user"("username");

-- CreateIndex
CREATE INDEX "auth_user_groups_group_id_97559544" ON "auth_user_groups"("group_id");

-- CreateIndex
CREATE INDEX "auth_user_groups_user_id_6a12ed8b" ON "auth_user_groups"("user_id");

-- CreateIndex
CREATE UNIQUE INDEX "auth_user_groups_user_id_group_id_94350c0c_uniq" ON "auth_user_groups"("user_id", "group_id");

-- CreateIndex
CREATE INDEX "auth_user_user_permissions_permission_id_1fbb5f2c" ON "auth_user_user_permissions"("permission_id");

-- CreateIndex
CREATE INDEX "auth_user_user_permissions_user_id_a95ead1b" ON "auth_user_user_permissions"("user_id");

-- CreateIndex
CREATE UNIQUE INDEX "auth_user_user_permissions_user_id_permission_id_14a6b632_uniq" ON "auth_user_user_permissions"("user_id", "permission_id");

-- CreateIndex
CREATE INDEX "connect_groups_connectgroupmember_connect_group_id_ae7f8326" ON "connect_groups_connectgroupmember"("connect_group_id");

-- CreateIndex
CREATE INDEX "connect_groups_connectgroupmember_member_id_5a29e01d" ON "connect_groups_connectgroupmember"("member_id");

-- CreateIndex
CREATE INDEX "connect_groups_connectgrouppastor_connect_group_id_46dc37ba" ON "connect_groups_connectgrouppastor"("connect_group_id");

-- CreateIndex
CREATE INDEX "connect_groups_connectgrouppastor_pastor_id_e5891bc9" ON "connect_groups_connectgrouppastor"("pastor_id");

-- CreateIndex
CREATE INDEX "django_admin_log_content_type_id_c4bce8eb" ON "django_admin_log"("content_type_id");

-- CreateIndex
CREATE INDEX "django_admin_log_user_id_c564eba6" ON "django_admin_log"("user_id");

-- CreateIndex
CREATE UNIQUE INDEX "django_content_type_app_label_model_76bd3d3b_uniq" ON "django_content_type"("app_label", "model");

-- CreateIndex
CREATE INDEX "django_session_expire_date_a5c62663" ON "django_session"("expire_date");

-- CreateIndex
CREATE INDEX "django_session_session_key_c0390e0f_like" ON "django_session"("session_key");

-- CreateIndex
CREATE INDEX "events_event_service_id_8a87164e" ON "events_event"("service_id");

-- CreateIndex
CREATE INDEX "events_eventparticipation_event_id_5543f4b9" ON "events_eventparticipation"("event_id");

-- CreateIndex
CREATE INDEX "events_eventparticipation_member_id_54c55f51" ON "events_eventparticipation"("member_id");

-- CreateIndex
CREATE INDEX "faq_embedding_idx" ON "faq_embeddings"("embedding");

-- CreateIndex
CREATE INDEX "growth_track_growthtrackenrollment_growth_track_id_e0254d9d" ON "growth_track_growthtrackenrollment"("growth_track_id");

-- CreateIndex
CREATE INDEX "growth_track_growthtrackenrollment_member_id_c370c3ad" ON "growth_track_growthtrackenrollment"("member_id");

-- CreateIndex
CREATE UNIQUE INDEX "unique_enrollment" ON "growth_track_growthtrackenrollment"("growth_track_id", "member_id");

-- CreateIndex
CREATE INDEX "members_firsttimers_member_id_5125e455" ON "members_firsttimers"("member_id");

-- CreateIndex
CREATE INDEX "members_firsttimers_service_id_id_5bc55a65" ON "members_firsttimers"("service_id_id");

-- CreateIndex
CREATE UNIQUE INDEX "members_member_email_key" ON "members_member"("email");

-- CreateIndex
CREATE INDEX "members_mem_date_jo_0f4cff_idx" ON "members_member"("date_joined");

-- CreateIndex
CREATE INDEX "members_mem_phone_n_28ee55_idx" ON "members_member"("phone_number");

-- CreateIndex
CREATE INDEX "members_member_email_156bbce1_like" ON "members_member"("email");

-- CreateIndex
CREATE UNIQUE INDEX "pastors_pastor_email_key" ON "pastors_pastor"("email");

-- CreateIndex
CREATE INDEX "pastors_pastor_email_f3948b4c_like" ON "pastors_pastor"("email");

-- CreateIndex
CREATE INDEX "ix_rag_documents_collection_name" ON "rag_documents"("collection_name");

-- CreateIndex
CREATE INDEX "ix_rag_documents_metadata_gin" ON "rag_documents" USING GIN ("metadata");

-- CreateIndex
CREATE INDEX "services_se_service_57f6a4_idx" ON "services_service"("service_type_id");

-- CreateIndex
CREATE INDEX "services_se_service_674f67_idx" ON "services_service"("service_date");

-- CreateIndex
CREATE INDEX "services_service_connect_group_id_02acd4ab" ON "services_service"("connect_group_id");

-- CreateIndex
CREATE INDEX "services_service_service_type_id_6d1ff243" ON "services_service"("service_type_id");

-- AddForeignKey
ALTER TABLE "connect_group" ADD CONSTRAINT "connect_group_service_id_fkey" FOREIGN KEY ("service_id") REFERENCES "service"("id") ON DELETE NO ACTION ON UPDATE NO ACTION;

-- AddForeignKey
ALTER TABLE "attendance" ADD CONSTRAINT "attendance_member_id_fkey" FOREIGN KEY ("member_id") REFERENCES "members"("id") ON DELETE NO ACTION ON UPDATE NO ACTION;

-- AddForeignKey
ALTER TABLE "attendance" ADD CONSTRAINT "attendance_service_id_fkey" FOREIGN KEY ("service_id") REFERENCES "service"("id") ON DELETE NO ACTION ON UPDATE NO ACTION;

-- AddForeignKey
ALTER TABLE "first_timer_events" ADD CONSTRAINT "first_timer_events_member_id_fkey" FOREIGN KEY ("member_id") REFERENCES "members"("id") ON DELETE NO ACTION ON UPDATE NO ACTION;

-- AddForeignKey
ALTER TABLE "first_timer_events" ADD CONSTRAINT "first_timer_events_service_id_fkey" FOREIGN KEY ("service_id") REFERENCES "service"("id") ON DELETE NO ACTION ON UPDATE NO ACTION;

-- AddForeignKey
ALTER TABLE "attendance_attendance" ADD CONSTRAINT "attendance_attendanc_service_id_904d6c3f_fk_services_" FOREIGN KEY ("service_id") REFERENCES "services_service"("id") ON DELETE NO ACTION ON UPDATE NO ACTION;

-- AddForeignKey
ALTER TABLE "attendance_attendance" ADD CONSTRAINT "attendance_attendance_member_id_9777e18b_fk_members_member_id" FOREIGN KEY ("member_id") REFERENCES "members_member"("id") ON DELETE NO ACTION ON UPDATE NO ACTION;

-- AddForeignKey
ALTER TABLE "auth_group_permissions" ADD CONSTRAINT "auth_group_permissio_permission_id_84c5c92e_fk_auth_perm" FOREIGN KEY ("permission_id") REFERENCES "auth_permission"("id") ON DELETE NO ACTION ON UPDATE NO ACTION;

-- AddForeignKey
ALTER TABLE "auth_group_permissions" ADD CONSTRAINT "auth_group_permissions_group_id_b120cbf9_fk_auth_group_id" FOREIGN KEY ("group_id") REFERENCES "auth_group"("id") ON DELETE NO ACTION ON UPDATE NO ACTION;

-- AddForeignKey
ALTER TABLE "auth_permission" ADD CONSTRAINT "auth_permission_content_type_id_2f476e4b_fk_django_co" FOREIGN KEY ("content_type_id") REFERENCES "django_content_type"("id") ON DELETE NO ACTION ON UPDATE NO ACTION;

-- AddForeignKey
ALTER TABLE "auth_user_groups" ADD CONSTRAINT "auth_user_groups_group_id_97559544_fk_auth_group_id" FOREIGN KEY ("group_id") REFERENCES "auth_group"("id") ON DELETE NO ACTION ON UPDATE NO ACTION;

-- AddForeignKey
ALTER TABLE "auth_user_groups" ADD CONSTRAINT "auth_user_groups_user_id_6a12ed8b_fk_auth_user_id" FOREIGN KEY ("user_id") REFERENCES "auth_user"("id") ON DELETE NO ACTION ON UPDATE NO ACTION;

-- AddForeignKey
ALTER TABLE "auth_user_user_permissions" ADD CONSTRAINT "auth_user_user_permi_permission_id_1fbb5f2c_fk_auth_perm" FOREIGN KEY ("permission_id") REFERENCES "auth_permission"("id") ON DELETE NO ACTION ON UPDATE NO ACTION;

-- AddForeignKey
ALTER TABLE "auth_user_user_permissions" ADD CONSTRAINT "auth_user_user_permissions_user_id_a95ead1b_fk_auth_user_id" FOREIGN KEY ("user_id") REFERENCES "auth_user"("id") ON DELETE NO ACTION ON UPDATE NO ACTION;

-- AddForeignKey
ALTER TABLE "connect_group_members" ADD CONSTRAINT "connect_group_members_connect_group_id_fkey" FOREIGN KEY ("connect_group_id") REFERENCES "connect_group"("id") ON DELETE NO ACTION ON UPDATE NO ACTION;

-- AddForeignKey
ALTER TABLE "connect_group_members" ADD CONSTRAINT "connect_group_members_member_id_fkey" FOREIGN KEY ("member_id") REFERENCES "members"("id") ON DELETE NO ACTION ON UPDATE NO ACTION;

-- AddForeignKey
ALTER TABLE "connect_groups_connectgroupmember" ADD CONSTRAINT "connect_groups_conne_connect_group_id_ae7f8326_fk_connect_g" FOREIGN KEY ("connect_group_id") REFERENCES "connect_groups_connectgroup"("id") ON DELETE NO ACTION ON UPDATE NO ACTION;

-- AddForeignKey
ALTER TABLE "connect_groups_connectgroupmember" ADD CONSTRAINT "connect_groups_conne_member_id_5a29e01d_fk_members_m" FOREIGN KEY ("member_id") REFERENCES "members_member"("id") ON DELETE NO ACTION ON UPDATE NO ACTION;

-- AddForeignKey
ALTER TABLE "connect_groups_connectgrouppastor" ADD CONSTRAINT "connect_groups_conne_connect_group_id_46dc37ba_fk_connect_g" FOREIGN KEY ("connect_group_id") REFERENCES "connect_groups_connectgroup"("id") ON DELETE NO ACTION ON UPDATE NO ACTION;

-- AddForeignKey
ALTER TABLE "connect_groups_connectgrouppastor" ADD CONSTRAINT "connect_groups_conne_pastor_id_e5891bc9_fk_pastors_p" FOREIGN KEY ("pastor_id") REFERENCES "pastors_pastor"("id") ON DELETE NO ACTION ON UPDATE NO ACTION;

-- AddForeignKey
ALTER TABLE "django_admin_log" ADD CONSTRAINT "django_admin_log_content_type_id_c4bce8eb_fk_django_co" FOREIGN KEY ("content_type_id") REFERENCES "django_content_type"("id") ON DELETE NO ACTION ON UPDATE NO ACTION;

-- AddForeignKey
ALTER TABLE "django_admin_log" ADD CONSTRAINT "django_admin_log_user_id_c564eba6_fk_auth_user_id" FOREIGN KEY ("user_id") REFERENCES "auth_user"("id") ON DELETE NO ACTION ON UPDATE NO ACTION;

-- AddForeignKey
ALTER TABLE "events_event" ADD CONSTRAINT "events_event_service_id_8a87164e_fk_services_service_id" FOREIGN KEY ("service_id") REFERENCES "services_service"("id") ON DELETE NO ACTION ON UPDATE NO ACTION;

-- AddForeignKey
ALTER TABLE "events_eventparticipation" ADD CONSTRAINT "events_eventparticip_member_id_54c55f51_fk_members_m" FOREIGN KEY ("member_id") REFERENCES "members_member"("id") ON DELETE NO ACTION ON UPDATE NO ACTION;

-- AddForeignKey
ALTER TABLE "events_eventparticipation" ADD CONSTRAINT "events_eventparticipation_event_id_5543f4b9_fk_events_event_id" FOREIGN KEY ("event_id") REFERENCES "events_event"("id") ON DELETE NO ACTION ON UPDATE NO ACTION;

-- AddForeignKey
ALTER TABLE "growth_track_growthtrackenrollment" ADD CONSTRAINT "growth_track_growtht_growth_track_id_e0254d9d_fk_growth_tr" FOREIGN KEY ("growth_track_id") REFERENCES "growth_track_growthtrack"("id") ON DELETE NO ACTION ON UPDATE NO ACTION;

-- AddForeignKey
ALTER TABLE "growth_track_growthtrackenrollment" ADD CONSTRAINT "growth_track_growtht_member_id_c370c3ad_fk_members_m" FOREIGN KEY ("member_id") REFERENCES "members_member"("id") ON DELETE NO ACTION ON UPDATE NO ACTION;

-- AddForeignKey
ALTER TABLE "members_firsttimers" ADD CONSTRAINT "members_firsttimers_member_id_5125e455_fk_members_member_id" FOREIGN KEY ("member_id") REFERENCES "members_member"("id") ON DELETE NO ACTION ON UPDATE NO ACTION;

-- AddForeignKey
ALTER TABLE "members_firsttimers" ADD CONSTRAINT "members_firsttimers_service_id_id_5bc55a65_fk_services_" FOREIGN KEY ("service_id_id") REFERENCES "services_service"("id") ON DELETE NO ACTION ON UPDATE NO ACTION;

-- AddForeignKey
ALTER TABLE "services_service" ADD CONSTRAINT "services_service_connect_group_id_02acd4ab_fk_connect_g" FOREIGN KEY ("connect_group_id") REFERENCES "connect_groups_connectgroup"("id") ON DELETE NO ACTION ON UPDATE NO ACTION;

-- AddForeignKey
ALTER TABLE "services_service" ADD CONSTRAINT "services_service_service_type_id_6d1ff243_fk_services_" FOREIGN KEY ("service_type_id") REFERENCES "services_servicetype"("id") ON DELETE NO ACTION ON UPDATE NO ACTION;
