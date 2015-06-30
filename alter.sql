-- 2013-10-21 - update table names
-- BEGIN;
--     ALTER TABLE pluto_activityauditstatus            RENAME TO openode_activityauditstatus;
--     ALTER TABLE pluto_actuality                      RENAME TO openode_actuality;
--     ALTER TABLE pluto_anonymousanswer                RENAME TO openode_anonymousanswer;
--     ALTER TABLE pluto_anonymousquestion              RENAME TO openode_anonymousquestion;
--     ALTER TABLE pluto_attachmentfilenode             RENAME TO openode_attachmentfilenode;
--     ALTER TABLE pluto_attachmentfilethread           RENAME TO openode_attachmentfilethread;
--     ALTER TABLE pluto_draftanswer                    RENAME TO openode_draftanswer;
--     ALTER TABLE pluto_draftquestion                  RENAME TO openode_draftquestion;
--     ALTER TABLE pluto_emailfeedsetting               RENAME TO openode_emailfeedsetting;
--     ALTER TABLE pluto_log                            RENAME TO openode_log;
--     ALTER TABLE pluto_markedtag                      RENAME TO openode_markedtag;
--     ALTER TABLE pluto_menuitem                       RENAME TO openode_menuitem;
--     ALTER TABLE pluto_node                           RENAME TO openode_node;
--     ALTER TABLE pluto_nodeuser                       RENAME TO openode_nodeuser;
--     ALTER TABLE pluto_organization                   RENAME TO openode_organization;
--     ALTER TABLE pluto_organizationmembership         RENAME TO openode_organizationmembership;
--     ALTER TABLE pluto_post                           RENAME TO openode_post;
--     ALTER TABLE pluto_postflagreason                 RENAME TO openode_postflagreason;
--     ALTER TABLE pluto_postrevision                   RENAME TO openode_postrevision;
--     ALTER TABLE pluto_replyaddress                   RENAME TO openode_replyaddress;
--     ALTER TABLE pluto_staticpage                     RENAME TO openode_staticpage;
--     ALTER TABLE pluto_thread                         RENAME TO openode_thread;
--     ALTER TABLE pluto_thread_tags                    RENAME TO openode_thread_tags;
--     ALTER TABLE pluto_threadcategory                 RENAME TO openode_threadcategory;
--     ALTER TABLE pluto_threadview                     RENAME TO openode_threadview;
--     UPDATE django_content_type SET app_label = 'openode' WHERE app_label = 'pluto';
-- COMMIT;

-- -- 2014-01-24
-- BEGIN;
--     ALTER TABLE "auth_user" ADD COLUMN "change_password_key" varchar(255);
-- COMMIT;


-- -- 2014-09-4

-- BEGIN;
--      ALTER TABLE "activity" ALTER COLUMN "content_type_id" DROP NOT NULL;
--      ALTER TABLE "activity" ALTER COLUMN "object_id" DROP NOT NULL;
-- COMMIT;

-- -- 2014-09-04
-- BEGIN;
--   ALTER TABLE "openode_organization" ADD COLUMN "approved" boolean;
--   UPDATE "openode_organization" SET approved=TRUE;
-- COMMIT;

-- -- 2014-10-02
-- BEGIN;
--      ALTER TABLE "activity" ADD COLUMN "data" text;
-- COMMIT;

-- 2015-06-25 - Question flow fields
BEGIN;
    ALTER TABLE "openode_node" ADD COLUMN "is_question_flow_enabled" boolean DEFAULT false;
    ALTER TABLE "openode_thread" ADD COLUMN "question_flow_state" varchar(255) DEFAULT 'new';
    ALTER TABLE "openode_thread" ADD COLUMN "question_flow_responsible_user_id" integer REFERENCES "auth_user" ("id") DEFERRABLE INITIALLY DEFERRED;
    ALTER TABLE "openode_thread" ADD COLUMN "question_flow_interviewee_user_id" integer REFERENCES "auth_user" ("id") DEFERRABLE INITIALLY DEFERRED;
    CREATE INDEX "openode_thread_question_flow_responsible_user_id" ON "openode_thread" ("question_flow_responsible_user_id");
    CREATE INDEX "openode_thread_question_flow_interviewee_user_id" ON "openode_thread" ("question_flow_interviewee_user_id");

    ALTER TABLE "openode_post" ADD COLUMN "question_flow_is_published" boolean DEFAULT true;
    CREATE INDEX "openode_post_is_published" ON "openode_post" ("is_published");
COMMIT;

