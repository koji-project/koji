-- upgrade script to migrate the Koji database schema
-- from version 1.29 to 1.30


BEGIN;

ALTER TABLE archivetypes ADD COLUMN compression_type TEXT;

UPDATE archivetypes set compression_type='zip' WHERE name = 'jar';
UPDATE archivetypes set compression_type='zip' WHERE name = 'zip';
UPDATE archivetypes set compression_type='tar' WHERE name = 'tar';

COMMIT;
