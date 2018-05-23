-- upgrade script to migrate the Koji database schema
-- from version 1.16 to 1.17


BEGIN;

-- Change VARCHAR field for build_target names to TEXT to allow longer names
ALTER TABLE build_target ALTER COLUMN name TYPE TEXT;

COMMIT;
