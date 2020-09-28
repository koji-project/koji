-- upgrade script to migrate the Koji database schema
-- from version 1.23 to 1.24


BEGIN;

ALTER TABLE tag_extra ALTER COLUMN value DROP NOT NULL;

COMMIT;
