-- upgrade script to migrate the Koji database schema
-- from version 1.24 to 1.25


BEGIN;

ALTER TABLE repo ADD COLUMN task_id INTEGER NULL REFERENCES task(id);

COMMIT;
