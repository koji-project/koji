-- upgrade script to migrate the Koji database schema
-- from version 1.32 to 1.33

BEGIN;
    ALTER TABLE sessions ADD COLUMN renew_time TIMESTAMPTZ DEFAULT NULL;
COMMIT;

