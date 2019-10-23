-- upgrade script to migrate the Koji database schema
-- from version 1.18 to 1.19


BEGIN;

CREATE TABLE tag_package_owners (
	package_id INTEGER NOT NULL REFERENCES package(id),
	tag_id INTEGER NOT NULL REFERENCES tag (id),
	owner INTEGER NOT NULL REFERENCES users(id),
-- versioned - see earlier description of versioning
	create_event INTEGER NOT NULL REFERENCES events(id) DEFAULT get_event(),
	revoke_event INTEGER REFERENCES events(id),
	creator_id INTEGER NOT NULL REFERENCES users(id),
	revoker_id INTEGER REFERENCES users(id),
	active BOOLEAN DEFAULT 'true' CHECK (active),
	CONSTRAINT active_revoke_sane CHECK (
		(active IS NULL AND revoke_event IS NOT NULL AND revoker_id IS NOT NULL)
		OR (active IS NOT NULL AND revoke_event IS NULL AND revoker_id IS NULL)),
	PRIMARY KEY (create_event, package_id, tag_id),
	UNIQUE (package_id,tag_id,active)
) WITHOUT OIDS;

CREATE OR REPLACE FUNCTION convert_owners() RETURNS SETOF tag_packages AS
$BODY$
DECLARE
    r tag_packages%rowtype;
    r2 tag_packages%rowtype;
    last_owner int;
BEGIN
    FOR r IN SELECT package_id, tag_id FROM tag_packages GROUP BY package_id, tag_id ORDER BY package_id, tag_id
    LOOP
        last_owner := 0;
        FOR r2 IN SELECT * FROM tag_packages WHERE package_id = r.package_id AND tag_id = r.tag_id ORDER BY create_event
        LOOP
            -- always use first and last (active) row
            IF last_owner = 0 OR r2.active IS TRUE THEN
                last_owner := r2.owner;
                RETURN NEXT r2; -- return current row of SELECT
            ELSE
                -- copy others only if owner changed
                IF last_owner <> r2.owner THEN
                    RETURN NEXT r2;
                    last_owner := r2.owner;
                END IF;
            END IF;
        END LOOP;
    END LOOP;
    RETURN;
END
$BODY$
LANGUAGE plpgsql;

INSERT INTO tag_package_owners (SELECT package_id, tag_id, owner, create_event, revoke_event, creator_id, revoker_id, active FROM convert_owners());
DROP INDEX IF EXISTS tag_packages_owner;
ALTER TABLE tag_packages DROP COLUMN owner;
DROP FUNCTION convert_owners();

-- add compressed iso-compressed, vhd-compressed, vhdx-compressed, and vmdk-compressed
insert into archivetypes (name, description, extensions) values ('iso-compressed', 'Compressed iso image', 'iso.gz iso.xz');
insert into archivetypes (name, description, extensions) values ('vhd-compressed', 'Compressed VHD image', 'vhd.gz vhd.xz');
insert into archivetypes (name, description, extensions) values ('vhdx-compressed', 'Compressed VHDx image', 'vhd.gz vhd.xz');
insert into archivetypes (name, description, extensions) values ('vmdk-compressed', 'Compressed VMDK image', 'vmdk.gz vmdk.xz');

-- add kernel-image and imitramfs
insert into archivetypes (name, description, extensions) values ('kernel-image', 'Kernel BZ2 Image', 'vmlinuz vmlinuz.gz vmlinuz.xz');
insert into archivetypes (name, description, extensions) values ('initramfs', 'Compressed Initramfs Image', 'img');

-- schema update for https://pagure.io/koji/issue/1629
CREATE TABLE user_krb_principals (
    user_id INTEGER NOT NULL REFERENCES users(id),
    krb_principal VARCHAR(255) NOT NULL UNIQUE,
    PRIMARY KEY (user_id, krb_principal)
) WITHOUT OIDS;

INSERT INTO user_krb_principals ( SELECT id, krb_principal FROM users WHERE users.krb_principal IS NOT NULL);

ALTER TABLE users DROP COLUMN krb_principal;

-- Disallow duplicate content generator names
ALTER TABLE content_generator ADD UNIQUE (name);
ALTER TABLE content_generator ALTER COLUMN name SET NOT NULL;


-- add all basic permissions
INSERT INTO permissions (name) SELECT 'dist-repo' WHERE NOT EXISTS (SELECT 1 FROM permissions WHERE name = 'dist-repo');
INSERT INTO permissions (name) SELECT 'host' WHERE NOT EXISTS (SELECT 1 FROM permissions WHERE name = 'host');
INSERT INTO permissions (name) SELECT 'image-import' WHERE NOT EXISTS (SELECT 1 FROM permissions WHERE name = 'image-import');
INSERT INTO permissions (name) SELECT 'sign' WHERE NOT EXISTS (SELECT 1 FROM permissions WHERE name = 'sign');
INSERT INTO permissions (name) SELECT 'tag' WHERE NOT EXISTS (SELECT 1 FROM permissions WHERE name = 'tag');
INSERT INTO permissions (name) SELECT 'target' WHERE NOT EXISTS (SELECT 1 FROM permissions WHERE name = 'target');

COMMIT;
