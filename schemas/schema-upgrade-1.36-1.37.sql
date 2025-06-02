-- upgrade script to migrate the Koji database schema
-- from version 1.36 to 1.37

BEGIN;

INSERT INTO archivetypes (name, description, extensions) VALUES ('wsl', 'Compressed tarball for Windows Subsystem for Linux', 'wsl') ON CONFLICT DO NOTHING;

COMMIT;
