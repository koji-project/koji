-- upgrade script to migrate the Koji database schema
-- from version 1.16 to 1.17


BEGIN;

-- Change VARCHAR field for build_target names to TEXT to allow longer names
ALTER TABLE build_target ALTER COLUMN name TYPE TEXT;

-- Allow different merge modes for mergerepo
ALTER TABLE tag_external_repos ADD COLUMN merge_mode TEXT DEFAULT 'koji';

COMMIT;
