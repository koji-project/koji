-- upgrade script to migrate the Koji database schema
-- from version 1.33 to 1.34

BEGIN;

CREATE INDEX CONCURRENTLY IF NOT EXISTS rpminfo_nvra
    ON rpminfo(name,version,release,arch,external_repo_id);

COMMIT;
