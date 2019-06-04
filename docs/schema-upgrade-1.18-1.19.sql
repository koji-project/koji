-- upgrade script to migrate the Koji database schema
-- from version 1.18 to 1.19


BEGIN;

-- add compressed raw-gzip and compressed qcow2 images
insert into archivetypes (name, description, extensions) values ('raw-gz', 'GZIP compressed raw disk image', 'raw.gz');
insert into archivetypes (name, description, extensions) values ('qcow2-compressed', 'Compressed QCOW2 image', 'qcow2.gz qcow2.xz');

COMMIT;
