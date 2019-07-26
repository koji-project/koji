-- upgrade script to migrate the Koji database schema
-- from version 1.17 to 1.18


BEGIN;

-- new table for notifications' optouts
CREATE TABLE build_notifications_block (
    id SERIAL NOT NULL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users (id),
    package_id INTEGER REFERENCES package (id),
    tag_id INTEGER REFERENCES tag (id)
) WITHOUT OIDS;

-- add tgz to list of tar's extensions
UPDATE archivetypes SET extensions = 'tar tar.gz tar.bz2 tar.xz tgz' WHERE name = 'tar';
INSERT INTO archivetypes (name, description, extensions) VALUES ('vhdx', 'Hyper-V Virtual Hard Disk v2 image', 'vhdx');

-- add compressed raw-gzip and compressed qcow2 images
insert into archivetypes (name, description, extensions) values ('raw-gz', 'GZIP compressed raw disk image', 'raw.gz');
insert into archivetypes (name, description, extensions) values ('qcow2-compressed', 'Compressed QCOW2 image', 'qcow2.gz qcow2.xz');

-- add better index for sessions
CREATE INDEX sessions_expired ON sessions(expired);

-- table for content generator build reservations
CREATE TABLE build_reservations (
	build_id INTEGER NOT NULL REFERENCES build(id),
	token VARCHAR(64),
        created TIMESTAMP NOT NULL,
	PRIMARY KEY (build_id)
) WITHOUT OIDS;
CREATE INDEX build_reservations_created ON build_reservations(created);

ALTER TABLE build ADD COLUMN cg_id INTEGER REFERENCES content_generator(id);


-- new indexes added in 1.18
CREATE INDEX tag_packages_active_tag_id ON tag_packages(active, tag_id);
CREATE INDEX tag_packages_create_event ON tag_packages(create_event);
CREATE INDEX tag_packages_revoke_event ON tag_packages(revoke_event);
CREATE INDEX tag_packages_owner ON tag_packages(owner);


COMMIT;
