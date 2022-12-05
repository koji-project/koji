-- upgrade script to migrate the Koji database schema
-- from version 1.19 to 1.20

BEGIN;

-- fix duplicate extension in archivetypes
UPDATE archivetypes SET extensions = 'vhdx.gz vhdx.xz' WHERE name = 'vhdx-compressed';

COMMIT;
