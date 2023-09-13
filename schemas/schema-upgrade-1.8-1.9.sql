
BEGIN;

-- new archive types
insert into archivetypes (name, description, extensions) values ('vmdk', 'vSphere image', 'vmdk');
insert into archivetypes (name, description, extensions) values ('ova', 'OVA image', 'ova');
insert into archivetypes (name, description, extensions) values ('ks', 'Kickstart', 'ks');
insert into archivetypes (name, description, extensions) values ('cfg', 'Configuration file', 'cfg');

COMMIT;

BEGIN;
-- it's harmless if this part fails.
-- there shouldn't be any references to this, but keep it in a separate transaction just in case
delete from archivetypes where name = 'vmx';
COMMIT;
