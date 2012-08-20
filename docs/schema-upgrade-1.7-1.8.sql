-- schema migration from version 1.7 to 1.8
-- (in progress)
-- note: this update will require additional steps, please see the migration doc

BEGIN;

ALTER TABLE imageinfo_listing RENAME TO old_imageinfo_listing;
-- we need to keep this data temporarily (as well as the obsolete imageinfo
-- table) so that the supplemental migration script can do its job

-- create new image tables
CREATE TABLE image_builds (
    build_id INTEGER NOT NULL PRIMARY KEY REFERENCES build(id)
) WITHOUT OIDS;



-- alter archiveinfo
ALTER TABLE archiveinfo ALTER COLUMN size TYPE BIGINT;
ALTER TABLE archiveinfo RENAME COLUMN md5sum TO checksum;
ALTER TABLE archiveinfo ADD COLUMN checksum_type INTEGER NOT NULL;

-- new archive types
insert into archivetypes (name, description, extensions) values ('iso', 'CD/DVD Image', 'iso');
insert into archivetypes (name, description, extensions) values ('raw', 'Raw disk image', 'raw');
insert into archivetypes (name, description, extensions) values ('qcow', 'QCOW image', 'qcow');
insert into archivetypes (name, description, extensions) values ('qcow2', 'QCOW2 image', 'qcow2');
insert into archivetypes (name, description, extensions) values ('vmx', 'VMX image', 'vmx');

