-- schema migration from version 1.9 to next
-- note: this update will require additional steps, please see the migration doc

BEGIN;

-- new archive types
insert into archivetypes (name, description, extensions) values ('raw-xz', 'xz compressed raw disk image', 'raw.xz');

COMMIT;
