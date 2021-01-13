-- upgrade script to migrate the Koji database schema
-- from version 1.23 to 1.24


BEGIN;

ALTER TABLE tag_external_repos ADD COLUMN arches TEXT;

INSERT INTO archivetypes (name, description, extensions) VALUES ('deb', 'Debian package', 'deb');

COMMIT;
