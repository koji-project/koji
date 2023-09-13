-- PLEASE READ
-- This was an interim schema update script for changes introduced after
-- 1.10.1.
-- You probably want schema-upgrade-1.10-1.11.sql instead of this


BEGIN;

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

