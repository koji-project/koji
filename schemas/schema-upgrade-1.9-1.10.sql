
BEGIN;

INSERT INTO channels (name) VALUES ('image');


CREATE TABLE tag_extra (
	tag_id INTEGER NOT NULL REFERENCES tag(id),
	key TEXT NOT NULL,
	value TEXT NOT NULL,  -- TODO - move this to jsonb when we can
-- versioned - see desc above
	create_event INTEGER NOT NULL REFERENCES events(id) DEFAULT get_event(),
	revoke_event INTEGER REFERENCES events(id),
	creator_id INTEGER NOT NULL REFERENCES users(id),
	revoker_id INTEGER REFERENCES users(id),
	active BOOLEAN DEFAULT 'true' CHECK (active),
	CONSTRAINT active_revoke_sane CHECK (
		(active IS NULL AND revoke_event IS NOT NULL AND revoker_id IS NOT NULL)
		OR (active IS NOT NULL AND revoke_event IS NULL AND revoker_id IS NULL)),
	PRIMARY KEY (create_event, tag_id, key),
	UNIQUE (tag_id, key, active)
) WITHOUT OIDS;


update archivetypes set extensions='jar war rar ear sar jdocbook jdocbook-style' where name='jar';
update archivetypes set description='Zip file' where name='zip';
update archivetypes set extensions='tar tar.gz tar.bz2 tar.xz' where name='tar';
update archivetypes set description='Open Virtualization Archive' where name='ova';

insert into archivetypes (name, description, extensions) values ('vdi', 'VirtualBox Virtual Disk Image', 'vdi');
insert into archivetypes (name, description, extensions) values ('aar', 'Binary distribution of an Android Library project', 'aar');
insert into archivetypes (name, description, extensions) values ('apklib', 'Source distribution of an Android Library project', 'apklib');
insert into archivetypes (name, description, extensions) values ('cab', 'Windows cabinet file', 'cab');
insert into archivetypes (name, description, extensions) values ('dylib', 'OS X dynamic library', 'dylib');
insert into archivetypes (name, description, extensions) values ('gem', 'Ruby gem', 'gem');
insert into archivetypes (name, description, extensions) values ('ini', 'INI config file', 'ini');
insert into archivetypes (name, description, extensions) values ('js', 'Javascript file', 'js');
insert into archivetypes (name, description, extensions) values ('ldif', 'LDAP Data Interchange Format file', 'ldif');
insert into archivetypes (name, description, extensions) values ('manifest', 'Runtime environment for .NET applications', 'manifest');
insert into archivetypes (name, description, extensions) values ('msm', 'Windows merge module', 'msm');
insert into archivetypes (name, description, extensions) values ('properties', 'Properties file', 'properties');
insert into archivetypes (name, description, extensions) values ('sig', 'Signature file', 'sig signature');
insert into archivetypes (name, description, extensions) values ('so', 'Shared library', 'so');
insert into archivetypes (name, description, extensions) values ('txt', 'Text file', 'txt');
insert into archivetypes (name, description, extensions) values ('vhd', 'Hyper-V image', 'vhd');
insert into archivetypes (name, description, extensions) values ('wsf', 'Windows script file', 'wsf');
insert into archivetypes (name, description, extensions) values ('box', 'Vagrant Box Image', 'box');
insert into archivetypes (name, description, extensions) values ('raw-xz', 'xz compressed raw disk image', 'raw.xz');

COMMIT;
