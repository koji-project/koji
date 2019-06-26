-- upgrade script to migrate the Koji database schema
-- from version 1.17 to 1.18


BEGIN;

-- add tgz to list of tar's extensions
UPDATE archivetypes SET extensions = 'tar tar.gz tar.bz2 tar.xz tgz' WHERE name = 'tar';
INSERT INTO archivetypes (name, description, extensions) VALUES ('vhdx', 'Hyper-V Virtual Hard Disk v2 image', 'vhdx');

-- add compressed raw-gzip and compressed qcow2 images
insert into archivetypes (name, description, extensions) values ('raw-gz', 'GZIP compressed raw disk image', 'raw.gz');
insert into archivetypes (name, description, extensions) values ('qcow2-compressed', 'Compressed QCOW2 image', 'qcow2.gz qcow2.xz');

-- add better index for sessions
CREATE INDEX sessions_expired ON sessions(expired);

COMMIT;
