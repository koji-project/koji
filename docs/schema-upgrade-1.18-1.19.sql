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

INSERT INTO tag_package_owners (SELECT package_id, tag_id, owner create_event revoke_event creator_id revoker_id active FROM convert_owners());
ALTER TABLE tag_packages DROP COLUMN owner;
DROP FUNCTION convert_owners();

COMMIT;
