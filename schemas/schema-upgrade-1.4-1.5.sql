-- upgrade script to migrate the Koji database schema
-- from version 1.4 to 1.5

BEGIN;

INSERT INTO permissions (name) VALUES ('win-import');
INSERT INTO permissions (name) VALUES ('win-admin');

INSERT INTO channels (name) VALUES ('vm');

insert into archivetypes (name, description, extensions) values ('spec', 'RPM spec file', 'spec');
insert into archivetypes (name, description, extensions) values ('exe', 'Windows executable', 'exe');
insert into archivetypes (name, description, extensions) values ('dll', 'Windows dynamic link library', 'dll');
insert into archivetypes (name, description, extensions) values ('lib', 'Windows import library', 'lib');
insert into archivetypes (name, description, extensions) values ('sys', 'Windows device driver', 'sys');
insert into archivetypes (name, description, extensions) values ('inf', 'Windows driver information file', 'inf');
insert into archivetypes (name, description, extensions) values ('cat', 'Windows catalog file', 'cat');
insert into archivetypes (name, description, extensions) values ('msi', 'Windows Installer package', 'msi');
insert into archivetypes (name, description, extensions) values ('pdb', 'Windows debug information', 'pdb');
insert into archivetypes (name, description, extensions) values ('oem', 'Windows driver oem file', 'oem');

-- flag to indicate that a build is a Windows build
CREATE TABLE win_builds (
        build_id INTEGER NOT NULL PRIMARY KEY REFERENCES build(id),
        platform TEXT NOT NULL
) WITHOUT OIDS;

-- Extended information about files built in Windows VMs
CREATE TABLE win_archives (
        archive_id INTEGER NOT NULL PRIMARY KEY REFERENCES archiveinfo(id),
        relpath TEXT NOT NULL,
        platforms TEXT NOT NULL,
        flags TEXT
) WITHOUT OIDS;

COMMIT WORK;
