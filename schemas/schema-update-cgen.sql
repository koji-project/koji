-- PLEASE READ
-- This was an interim schema update script for changes introduced after
-- 1.10.1.
-- You probably want schema-upgrade-1.10-1.11.sql instead of this


BEGIN;

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
ALTER TABLE standard_buildroot ADD CONSTRAINT brfk FOREIGN KEY (buildroot_id) REFERENCES buildroot(id);
ALTER TABLE standard_buildroot ADD CONSTRAINT hfk FOREIGN KEY (host_id) REFERENCES host(id);
ALTER TABLE standard_buildroot ADD CONSTRAINT rfk FOREIGN KEY (repo_id) REFERENCES repo(id);
ALTER TABLE standard_buildroot ADD CONSTRAINT tfk FOREIGN KEY (task_id) REFERENCES task(id);
ALTER TABLE standard_buildroot ADD CONSTRAINT efk FOREIGN KEY (create_event) REFERENCES events(id) ;
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

COMMIT;

