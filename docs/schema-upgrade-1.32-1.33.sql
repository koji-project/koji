-- upgrade script to migrate the Koji database schema
-- from version 1.32 to 1.33

BEGIN;
    ALTER TABLE sessions ADD COLUMN renew_time TIMESTAMPTZ;
    INSERT INTO archivetypes (name, description, extensions) VALUES ('checksum', 'Checksum file', 'sha256') ON CONFLICT DO NOTHING;
    INSERT INTO archivetypes (name, description, extensions) VALUES ('changes', 'Kiwi changes file', 'changes.xz changes') ON CONFLICT DO NOTHING;
    INSERT INTO archivetypes (name, description, extensions) VALUES ('packages', 'Kiwi packages listing', 'packages') ON CONFLICT DO NOTHING;
    INSERT INTO archivetypes (name, description, extensions) VALUES ('verified', 'Kiwi verified package list', 'verified') ON CONFLICT DO NOTHING;
    ALTER TABLE host ADD COLUMN update_time TIMESTAMPTZ;
    CREATE TABLE locks (
        name TEXT NOT NULL PRIMARY KEY
    ) WITHOUT OIDS;
    INSERT INTO locks(name) VALUES('protonmsg-plugin');
COMMIT;
