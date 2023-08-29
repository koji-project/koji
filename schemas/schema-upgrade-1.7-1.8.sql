-- schema migration from version 1.7 to 1.8
-- note: this update will require additional steps, please see the migration doc

BEGIN;


-- The following tables are now obsolete:
--    imageinfo
--    imageinfo_listing
-- However, we cannot drop them until after we migrate the data

-- create new image tables
CREATE TABLE image_builds (
    build_id INTEGER NOT NULL PRIMARY KEY REFERENCES build(id)
) WITHOUT OIDS;

CREATE TABLE image_archives (
    archive_id INTEGER NOT NULL PRIMARY KEY REFERENCES archiveinfo(id),
    arch VARCHAR(16) NOT NULL
) WITHOUT OIDS;

CREATE TABLE image_listing (
       image_id INTEGER NOT NULL REFERENCES image_archives(archive_id),
       rpm_id INTEGER NOT NULL REFERENCES rpminfo(id),
       UNIQUE (image_id, rpm_id)
) WITHOUT OIDS;
CREATE INDEX image_listing_rpms on image_listing(rpm_id);

-- alter archiveinfo
ALTER TABLE archiveinfo ALTER COLUMN size TYPE BIGINT;
ALTER TABLE archiveinfo RENAME COLUMN md5sum TO checksum;
ALTER TABLE archiveinfo ADD COLUMN checksum_type INTEGER NOT NULL DEFAULT 0;
ALTER TABLE archiveinfo ALTER COLUMN checksum_type DROP DEFAULT;
-- the main schema has no default for checksum_type
-- this is just an easy way to populate the fields for the old entries



-- new archive types
insert into archivetypes (name, description, extensions) values ('iso', 'CD/DVD Image', 'iso');
insert into archivetypes (name, description, extensions) values ('raw', 'Raw disk image', 'raw');
insert into archivetypes (name, description, extensions) values ('qcow', 'QCOW image', 'qcow');
insert into archivetypes (name, description, extensions) values ('qcow2', 'QCOW2 image', 'qcow2');
insert into archivetypes (name, description, extensions) values ('vmx', 'VMX image', 'vmx');
insert into archivetypes (name, description, extensions) values ('xsd', 'XML Schema Definition', 'xsd');

COMMIT;
