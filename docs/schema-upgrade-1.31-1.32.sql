-- upgrade script to migrate the Koji database schema
-- from version 1.31 to 1.32

BEGIN;

    -- fix duplicate extension in archivetypes
    UPDATE archivetypes SET extensions = 'vhdx.gz vhdx.xz' WHERE name = 'vhdx-compressed';

    -- track checksum of rpms
    CREATE TABLE rpm_checksum (
            rpm_id INTEGER NOT NULL REFERENCES rpminfo(id),
            sigkey TEXT NOT NULL,
            checksum TEXT NOT NULL UNIQUE,
            checksum_type SMALLINT NOT NULL,
            UNIQUE(rpm_id, sigkey, checksum_type)
    ) WITHOUT OIDS;
    CREATE INDEX rpm_checksum_rpm_id ON rpm_checksum(rpm_id);
COMMIT;
