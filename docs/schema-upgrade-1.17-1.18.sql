-- upgrade script to migrate the Koji database schema
-- from version 1.16 to 1.17


BEGIN;

-- add tgz to list of tar's extensions
UPDATE archivetypes SET extensions = 'tar tar.gz tar.bz2 tar.xz tgz' WHERE name = 'tar';
INSERT INTO archivetypes (name, description, extensions) VALUES ('vhdx', 'Hyper-V Virtual Hard Disk v2 image', 'vhdx');

-- add better index for sessions
CREATE INDEX sessions_expired ON sessions(expired);

COMMIT;
