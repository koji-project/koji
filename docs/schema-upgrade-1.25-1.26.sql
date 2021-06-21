-- upgrade script to migrate the Koji database schema
-- from version 1.25 to 1.26


BEGIN;

ALTER TABLE channels ADD COLUMN description TEXT;
ALTER TABLE channels ADD COLUMN enabled BOOLEAN NOT NULL DEFAULT 'true';
ALTER TABLE channels ADD COLUMN comment TEXT;

COMMIT;
