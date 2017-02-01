
BEGIN;

-- from schema-update-cgen.sql


-- New tables

SELECT statement_timestamp(), 'Creating new tables' as msg;

CREATE TABLE content_generator (
       id SERIAL PRIMARY KEY,
       name TEXT
) WITHOUT OIDS;

CREATE TABLE cg_users (
        cg_id INTEGER NOT NULL REFERENCES content_generator (id),
        user_id INTEGER NOT NULL REFERENCES users (id),
-- versioned
        create_event INTEGER NOT NULL REFERENCES events(id) DEFAULT get_event(),
        revoke_event INTEGER REFERENCES events(id),
        creator_id INTEGER NOT NULL REFERENCES users(id),
        revoker_id INTEGER REFERENCES users(id),
        active BOOLEAN DEFAULT 'true' CHECK (active),
        CONSTRAINT active_revoke_sane CHECK (
                (active IS NULL AND revoke_event IS NOT NULL AND revoker_id IS NOT NULL)
                OR (active IS NOT NULL AND revoke_event IS NULL AND revoker_id IS NULL)),
        PRIMARY KEY (create_event, cg_id, user_id),
        UNIQUE (cg_id, user_id, active)
) WITHOUT OIDS;


CREATE TABLE buildroot_tools_info (
       buildroot_id INTEGER NOT NULL REFERENCES buildroot(id),
       tool TEXT NOT NULL,
       version TEXT NOT NULL,
       PRIMARY KEY (buildroot_id, tool)
) WITHOUT OIDS;


CREATE TABLE image_archive_listing (
       image_id INTEGER NOT NULL REFERENCES image_archives(archive_id),
       archive_id INTEGER NOT NULL REFERENCES archiveinfo(id),
       UNIQUE (image_id, archive_id)
) WITHOUT OIDS;
CREATE INDEX image_listing_archives on image_archive_listing(archive_id);


-- new columns --

select statement_timestamp(), 'Adding new columns' as msg;
ALTER TABLE build ADD COLUMN start_time TIMESTAMP;
ALTER TABLE build ADD COLUMN source TEXT;
ALTER TABLE build ADD COLUMN extra TEXT;
ALTER TABLE rpminfo ADD COLUMN metadata_only BOOLEAN NOT NULL DEFAULT FALSE;
ALTER TABLE rpminfo ADD COLUMN extra TEXT;
ALTER TABLE archiveinfo ADD COLUMN metadata_only BOOLEAN NOT NULL DEFAULT FALSE;
ALTER TABLE archiveinfo ADD COLUMN extra TEXT;


-- the more complicated stuff

SELECT statement_timestamp(), 'Copying buildroot to standard_buildroot' as msg;
CREATE TABLE standard_buildroot AS SELECT id,host_id,repo_id,task_id,create_event,retire_event,state from buildroot;
-- doing it this way and fixing up after is *much* faster than creating the empty table
-- and using insert..select to populate

SELECT statement_timestamp(), 'Fixing up standard_buildroot table' as msg;
ALTER TABLE standard_buildroot RENAME id TO buildroot_id;
ALTER TABLE standard_buildroot ALTER COLUMN buildroot_id SET NOT NULL;
ALTER TABLE standard_buildroot ALTER COLUMN host_id SET NOT NULL;
ALTER TABLE standard_buildroot ALTER COLUMN repo_id SET NOT NULL;
ALTER TABLE standard_buildroot ALTER COLUMN task_id SET NOT NULL;
ALTER TABLE standard_buildroot ALTER COLUMN create_event SET NOT NULL;
ALTER TABLE standard_buildroot ALTER COLUMN create_event SET DEFAULT get_event();
SELECT statement_timestamp(), 'Fixing up standard_buildroot table, foreign key constraints' as msg;
ALTER TABLE standard_buildroot ADD CONSTRAINT standard_buildroot_buildroot_id_fkey FOREIGN KEY (buildroot_id) REFERENCES buildroot(id);
ALTER TABLE standard_buildroot ADD CONSTRAINT standard_buildroot_host_id_fkey FOREIGN KEY (host_id) REFERENCES host(id);
ALTER TABLE standard_buildroot ADD CONSTRAINT standard_buildroot_repo_id_fkey FOREIGN KEY (repo_id) REFERENCES repo(id);
ALTER TABLE standard_buildroot ADD CONSTRAINT standard_buildroot_task_id_fkey FOREIGN KEY (task_id) REFERENCES task(id);
ALTER TABLE standard_buildroot ADD CONSTRAINT standard_buildroot_create_event_fkey FOREIGN KEY (create_event) REFERENCES events(id) ;
SELECT statement_timestamp(), 'Fixing up standard_buildroot table, primary key' as msg;
ALTER TABLE standard_buildroot ADD PRIMARY KEY (buildroot_id);


SELECT statement_timestamp(), 'Altering buildroot table (dropping columns)' as msg;
ALTER TABLE buildroot DROP COLUMN host_id;
ALTER TABLE buildroot DROP COLUMN repo_id;
ALTER TABLE buildroot DROP COLUMN task_id;
ALTER TABLE buildroot DROP COLUMN create_event;
ALTER TABLE buildroot DROP COLUMN retire_event;
ALTER TABLE buildroot DROP COLUMN state;
ALTER TABLE buildroot DROP COLUMN dirtyness;

SELECT statement_timestamp(), 'Altering buildroot table (adding columns)' as msg;
ALTER TABLE buildroot ADD COLUMN br_type INTEGER NOT NULL DEFAULT 0;
ALTER TABLE buildroot ADD COLUMN cg_id INTEGER REFERENCES content_generator (id);
ALTER TABLE buildroot ADD COLUMN cg_version TEXT;
ALTER TABLE buildroot ADD COLUMN container_type TEXT;
ALTER TABLE buildroot ADD COLUMN host_os TEXT;
ALTER TABLE buildroot ADD COLUMN host_arch TEXT;
ALTER TABLE buildroot ADD COLUMN extra TEXT;

SELECT statement_timestamp(), 'Altering buildroot table (altering columns)' as msg;
ALTER TABLE buildroot RENAME arch TO container_arch;
ALTER TABLE buildroot ALTER COLUMN container_arch TYPE TEXT;
ALTER TABLE buildroot ALTER COLUMN br_type DROP DEFAULT;

SELECT statement_timestamp(), 'Altering buildroot table (altering constraints)' as msg;
ALTER TABLE buildroot ADD CONSTRAINT cg_sane CHECK (
        (cg_id IS NULL AND cg_version IS NULL)
        OR (cg_id IS NOT NULL AND cg_version IS NOT NULL));
UPDATE buildroot SET container_type = 'chroot' WHERE container_type IS NULL AND container_arch IS NOT NULL;
ALTER TABLE buildroot ADD CONSTRAINT container_sane CHECK (
        (container_type IS NULL AND container_arch IS NULL)
        OR (container_type IS NOT NULL AND container_arch IS NOT NULL));
ALTER TABLE buildroot ALTER COLUMN container_arch DROP NOT NULL;



-- from schema-update-cgen2.sql


-- New tables

SELECT statement_timestamp(), 'Creating new tables' as msg;

CREATE TABLE btype (
        id SERIAL NOT NULL PRIMARY KEY,
        name TEXT UNIQUE NOT NULL
) WITHOUT OIDS;

CREATE TABLE build_types (
        build_id INTEGER NOT NULL REFERENCES build(id),
        btype_id INTEGER NOT NULL REFERENCES btype(id),
        PRIMARY KEY (build_id, btype_id)
) WITHOUT OIDS;

-- predefined build types

SELECT statement_timestamp(), 'Adding predefined build types' as msg;
INSERT INTO btype(name) VALUES ('rpm');
INSERT INTO btype(name) VALUES ('maven');
INSERT INTO btype(name) VALUES ('win');
INSERT INTO btype(name) VALUES ('image');

-- new column for archiveinfo

SELECT statement_timestamp(), 'Altering archiveinfo table' as msg;
ALTER TABLE archiveinfo ADD COLUMN btype_id INTEGER REFERENCES btype(id);

-- fill in legacy types
SELECT statement_timestamp(), 'Adding legacy btypes to builds' as msg;
INSERT INTO build_types(btype_id, build_id)
    SELECT btype.id, maven_builds.build_id FROM btype JOIN maven_builds ON btype.name='maven';
INSERT INTO build_types(btype_id, build_id)
    SELECT btype.id, win_builds.build_id FROM btype JOIN win_builds ON btype.name='win';
INSERT INTO build_types(btype_id, build_id)
    SELECT btype.id, image_builds.build_id FROM btype JOIN image_builds ON btype.name='image';
-- not sure if this is the best way to select rpm builds...
INSERT INTO build_types(btype_id, build_id)
    SELECT DISTINCT btype.id, build_id FROM btype JOIN rpminfo ON btype.name='rpm'
        WHERE build_id IS NOT NULL;

SELECT statement_timestamp(), 'Adding legacy btypes to archiveinfo' as msg;
UPDATE archiveinfo SET btype_id=(SELECT id FROM btype WHERE name='maven' LIMIT 1)
    WHERE (SELECT archive_id FROM maven_archives WHERE archive_id=archiveinfo.id) IS NOT NULL;
UPDATE archiveinfo SET btype_id=(SELECT id FROM btype WHERE name='win' LIMIT 1)
    WHERE (SELECT archive_id FROM win_archives WHERE archive_id=archiveinfo.id) IS NOT NULL;
UPDATE archiveinfo SET btype_id=(SELECT id FROM btype WHERE name='image' LIMIT 1)
    WHERE (SELECT archive_id FROM image_archives WHERE archive_id=archiveinfo.id) IS NOT NULL;

-- new component tables
SELECT statement_timestamp(), 'Creating new component tables' as msg;
CREATE TABLE archive_rpm_components AS SELECT image_id, rpm_id from image_listing;
CREATE TABLE archive_components AS SELECT image_id, archive_id from image_archive_listing;
-- doing it this way and fixing up after is *much* faster than creating the empty table
-- and using insert..select to populate

SELECT statement_timestamp(), 'Fixing up component tables, rename columns' as msg;
ALTER TABLE archive_rpm_components RENAME image_id TO archive_id;
ALTER TABLE archive_components RENAME archive_id TO component_id;
ALTER TABLE archive_components RENAME image_id TO archive_id;
ALTER TABLE archive_rpm_components ALTER COLUMN rpm_id SET NOT NULL;
ALTER TABLE archive_rpm_components ALTER COLUMN archive_id SET NOT NULL;
ALTER TABLE archive_components ALTER COLUMN component_id SET NOT NULL;
ALTER TABLE archive_components ALTER COLUMN archive_id SET NOT NULL;

SELECT statement_timestamp(), 'Fixing up component tables, adding constraints' as msg;
ALTER TABLE archive_rpm_components ADD CONSTRAINT archive_rpm_components_archive_id_fkey FOREIGN KEY (archive_id) REFERENCES archiveinfo(id);
ALTER TABLE archive_rpm_components ADD CONSTRAINT archive_rpm_components_rpm_id_fkey FOREIGN KEY (rpm_id) REFERENCES rpminfo(id);
ALTER TABLE archive_rpm_components ADD CONSTRAINT archive_rpm_components_archive_id_rpm_id_key UNIQUE (archive_id, rpm_id);
ALTER TABLE archive_components ADD CONSTRAINT archive_components_archive_id_fkey FOREIGN KEY (archive_id) REFERENCES archiveinfo(id);
ALTER TABLE archive_components ADD CONSTRAINT archive_components_component_id_fkey FOREIGN KEY (component_id) REFERENCES archiveinfo(id);
ALTER TABLE archive_components ADD CONSTRAINT archive_components_archive_id_component_id_key UNIQUE (archive_id, component_id);

SELECT statement_timestamp(), 'Adding component table indexes' as msg;
CREATE INDEX rpm_components_idx on archive_rpm_components(rpm_id);
CREATE INDEX archive_components_idx on archive_components(component_id);


-- image_listing and image_archive_listing are no longer used


COMMIT;

