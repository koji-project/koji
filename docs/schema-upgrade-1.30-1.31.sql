-- upgrade script to migrate the Koji database schema
-- from version 1.30 to 1.31

BEGIN;
    -- index for default search method for rpms
    CREATE INDEX rpminfo_filename ON rpminfo((name || '-' || version || '-' || release || '.' || arch || '.rpm')) INCLUDE (id);
COMMIT;
