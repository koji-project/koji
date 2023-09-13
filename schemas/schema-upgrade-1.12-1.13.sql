-- upgrade script to migrate the Koji database schema
-- from version 1.12 to 1.13

BEGIN;

-- Change VARCHAR field for tag names to TEXT to allow longer tag names
ALTER TABLE tag ALTER COLUMN name TYPE TEXT;

COMMIT;
