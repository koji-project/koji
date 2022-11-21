-- upgrade script to migrate the Koji database schema
-- from version 1.31 to 1.32

BEGIN;

    -- fix duplicate extension in archivetypes
    UPDATE archivetypes SET extensions = 'vhdx.gz vhdx.xz' WHERE name = 'vhdx-compressed';

    -- for tag if session is closed or not
    ALTER TABLE sessions ADD COLUMN closed BOOLEAN NOT NULL DEFAULT 'false';
COMMIT;
