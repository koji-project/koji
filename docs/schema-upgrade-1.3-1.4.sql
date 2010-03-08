-- upgrade script to migrate the Koji database schema
-- from version 1.3 to 1.4

BEGIN;

-- First the simple stuff. A pair of new host fields.
ALTER TABLE host ADD COLUMN description TEXT;
ALTER TABLE host ADD COLUMN comment TEXT;


-- The rest updates all the versioned tables to track who did what

-- One issue with this is that we need to provide creator/revoker data
-- for existing rows. Our approach is to create a disabled user to use
-- for this named 'nobody'. The temporary function is merely a convenient
-- way to reference the user we create.
INSERT INTO users (name, status, usertype) VALUES ('nobody', 1, 0);
CREATE FUNCTION pg_temp.user() returns INTEGER as $$ select id from users where name='nobody' $$ language SQL;
-- If you would like to use an existing user instead, then:
--   1. comment out the users insert
--   2. edit the temporary function to look for the alternate user name

SELECT 'Updating table user_perms';

ALTER TABLE user_perms ADD COLUMN creator_id INTEGER REFERENCES users(id);
ALTER TABLE user_perms ADD COLUMN revoker_id INTEGER REFERENCES users(id);

UPDATE user_perms SET creator_id=pg_temp.user() WHERE creator_id IS NULL;
UPDATE user_perms SET revoker_id=pg_temp.user() WHERE revoker_id IS NULL AND revoke_event IS NOT NULL;

ALTER TABLE user_perms ALTER COLUMN creator_id SET NOT NULL;
ALTER TABLE user_perms DROP CONSTRAINT active_revoke_sane;
ALTER TABLE user_perms ADD CONSTRAINT active_revoke_sane CHECK (
    (active IS NULL AND revoke_event IS NOT NULL AND revoker_id IS NOT NULL)
    OR (active IS NOT NULL AND revoke_event IS NULL AND revoker_id IS NULL));


SELECT 'Updating table user_groups';

ALTER TABLE user_groups ADD COLUMN creator_id INTEGER REFERENCES users(id);
ALTER TABLE user_groups ADD COLUMN revoker_id INTEGER REFERENCES users(id);

UPDATE user_groups SET creator_id=pg_temp.user() WHERE creator_id IS NULL;
UPDATE user_groups SET revoker_id=pg_temp.user() WHERE revoker_id IS NULL AND revoke_event IS NOT NULL;

ALTER TABLE user_groups ALTER COLUMN creator_id SET NOT NULL;
ALTER TABLE user_groups DROP CONSTRAINT active_revoke_sane;
ALTER TABLE user_groups ADD CONSTRAINT active_revoke_sane CHECK (
    (active IS NULL AND revoke_event IS NOT NULL AND revoker_id IS NOT NULL)
    OR (active IS NOT NULL AND revoke_event IS NULL AND revoker_id IS NULL));


SELECT 'Updating table tag_inheritance';

ALTER TABLE tag_inheritance ADD COLUMN creator_id INTEGER REFERENCES users(id);
ALTER TABLE tag_inheritance ADD COLUMN revoker_id INTEGER REFERENCES users(id);

UPDATE tag_inheritance SET creator_id=pg_temp.user() WHERE creator_id IS NULL;
UPDATE tag_inheritance SET revoker_id=pg_temp.user() WHERE revoker_id IS NULL AND revoke_event IS NOT NULL;

ALTER TABLE tag_inheritance ALTER COLUMN creator_id SET NOT NULL;
ALTER TABLE tag_inheritance DROP CONSTRAINT active_revoke_sane;
ALTER TABLE tag_inheritance ADD CONSTRAINT active_revoke_sane CHECK (
    (active IS NULL AND revoke_event IS NOT NULL AND revoker_id IS NOT NULL)
    OR (active IS NOT NULL AND revoke_event IS NULL AND revoker_id IS NULL));


SELECT 'Updating table tag_config';

ALTER TABLE tag_config ADD COLUMN creator_id INTEGER REFERENCES users(id);
ALTER TABLE tag_config ADD COLUMN revoker_id INTEGER REFERENCES users(id);

UPDATE tag_config SET creator_id=pg_temp.user() WHERE creator_id IS NULL;
UPDATE tag_config SET revoker_id=pg_temp.user() WHERE revoker_id IS NULL AND revoke_event IS NOT NULL;

ALTER TABLE tag_config ALTER COLUMN creator_id SET NOT NULL;
ALTER TABLE tag_config DROP CONSTRAINT active_revoke_sane;
ALTER TABLE tag_config ADD CONSTRAINT active_revoke_sane CHECK (
    (active IS NULL AND revoke_event IS NOT NULL AND revoker_id IS NOT NULL)
    OR (active IS NOT NULL AND revoke_event IS NULL AND revoker_id IS NULL));


SELECT 'Updating table build_target_config';

ALTER TABLE build_target_config ADD COLUMN creator_id INTEGER REFERENCES users(id);
ALTER TABLE build_target_config ADD COLUMN revoker_id INTEGER REFERENCES users(id);

UPDATE build_target_config SET creator_id=pg_temp.user() WHERE creator_id IS NULL;
UPDATE build_target_config SET revoker_id=pg_temp.user() WHERE revoker_id IS NULL AND revoke_event IS NOT NULL;

ALTER TABLE build_target_config ALTER COLUMN creator_id SET NOT NULL;
ALTER TABLE build_target_config DROP CONSTRAINT active_revoke_sane;
ALTER TABLE build_target_config ADD CONSTRAINT active_revoke_sane CHECK (
    (active IS NULL AND revoke_event IS NOT NULL AND revoker_id IS NOT NULL)
    OR (active IS NOT NULL AND revoke_event IS NULL AND revoker_id IS NULL));


SELECT 'Updating table external_repo_config';

ALTER TABLE external_repo_config ADD COLUMN creator_id INTEGER REFERENCES users(id);
ALTER TABLE external_repo_config ADD COLUMN revoker_id INTEGER REFERENCES users(id);

UPDATE external_repo_config SET creator_id=pg_temp.user() WHERE creator_id IS NULL;
UPDATE external_repo_config SET revoker_id=pg_temp.user() WHERE revoker_id IS NULL AND revoke_event IS NOT NULL;

ALTER TABLE external_repo_config ALTER COLUMN creator_id SET NOT NULL;
ALTER TABLE external_repo_config DROP CONSTRAINT active_revoke_sane;
ALTER TABLE external_repo_config ADD CONSTRAINT active_revoke_sane CHECK (
    (active IS NULL AND revoke_event IS NOT NULL AND revoker_id IS NOT NULL)
    OR (active IS NOT NULL AND revoke_event IS NULL AND revoker_id IS NULL));


SELECT 'Updating table tag_external_repos';

ALTER TABLE tag_external_repos ADD COLUMN creator_id INTEGER REFERENCES users(id);
ALTER TABLE tag_external_repos ADD COLUMN revoker_id INTEGER REFERENCES users(id);

UPDATE tag_external_repos SET creator_id=pg_temp.user() WHERE creator_id IS NULL;
UPDATE tag_external_repos SET revoker_id=pg_temp.user() WHERE revoker_id IS NULL AND revoke_event IS NOT NULL;

ALTER TABLE tag_external_repos ALTER COLUMN creator_id SET NOT NULL;
ALTER TABLE tag_external_repos DROP CONSTRAINT active_revoke_sane;
ALTER TABLE tag_external_repos ADD CONSTRAINT active_revoke_sane CHECK (
    (active IS NULL AND revoke_event IS NOT NULL AND revoker_id IS NOT NULL)
    OR (active IS NOT NULL AND revoke_event IS NULL AND revoker_id IS NULL));


SELECT 'Updating table tag_listing';

ALTER TABLE tag_listing ADD COLUMN creator_id INTEGER REFERENCES users(id);
ALTER TABLE tag_listing ADD COLUMN revoker_id INTEGER REFERENCES users(id);

UPDATE tag_listing SET creator_id=pg_temp.user() WHERE creator_id IS NULL;
UPDATE tag_listing SET revoker_id=pg_temp.user() WHERE revoker_id IS NULL AND revoke_event IS NOT NULL;

ALTER TABLE tag_listing ALTER COLUMN creator_id SET NOT NULL;
ALTER TABLE tag_listing DROP CONSTRAINT active_revoke_sane;
ALTER TABLE tag_listing ADD CONSTRAINT active_revoke_sane CHECK (
    (active IS NULL AND revoke_event IS NOT NULL AND revoker_id IS NOT NULL)
    OR (active IS NOT NULL AND revoke_event IS NULL AND revoker_id IS NULL));


SELECT 'Updating table tag_packages';

ALTER TABLE tag_packages ADD COLUMN creator_id INTEGER REFERENCES users(id);
ALTER TABLE tag_packages ADD COLUMN revoker_id INTEGER REFERENCES users(id);

UPDATE tag_packages SET creator_id=pg_temp.user() WHERE creator_id IS NULL;
UPDATE tag_packages SET revoker_id=pg_temp.user() WHERE revoker_id IS NULL AND revoke_event IS NOT NULL;

ALTER TABLE tag_packages ALTER COLUMN creator_id SET NOT NULL;
ALTER TABLE tag_packages DROP CONSTRAINT active_revoke_sane;
ALTER TABLE tag_packages ADD CONSTRAINT active_revoke_sane CHECK (
    (active IS NULL AND revoke_event IS NOT NULL AND revoker_id IS NOT NULL)
    OR (active IS NOT NULL AND revoke_event IS NULL AND revoker_id IS NULL));


SELECT 'Updating table group_config';

ALTER TABLE group_config ADD COLUMN creator_id INTEGER REFERENCES users(id);
ALTER TABLE group_config ADD COLUMN revoker_id INTEGER REFERENCES users(id);

UPDATE group_config SET creator_id=pg_temp.user() WHERE creator_id IS NULL;
UPDATE group_config SET revoker_id=pg_temp.user() WHERE revoker_id IS NULL AND revoke_event IS NOT NULL;

ALTER TABLE group_config ALTER COLUMN creator_id SET NOT NULL;
ALTER TABLE group_config DROP CONSTRAINT active_revoke_sane;
ALTER TABLE group_config ADD CONSTRAINT active_revoke_sane CHECK (
    (active IS NULL AND revoke_event IS NOT NULL AND revoker_id IS NOT NULL)
    OR (active IS NOT NULL AND revoke_event IS NULL AND revoker_id IS NULL));


SELECT 'Updating table group_req_listing';

ALTER TABLE group_req_listing ADD COLUMN creator_id INTEGER REFERENCES users(id);
ALTER TABLE group_req_listing ADD COLUMN revoker_id INTEGER REFERENCES users(id);

UPDATE group_req_listing SET creator_id=pg_temp.user() WHERE creator_id IS NULL;
UPDATE group_req_listing SET revoker_id=pg_temp.user() WHERE revoker_id IS NULL AND revoke_event IS NOT NULL;

ALTER TABLE group_req_listing ALTER COLUMN creator_id SET NOT NULL;
ALTER TABLE group_req_listing DROP CONSTRAINT active_revoke_sane;
ALTER TABLE group_req_listing ADD CONSTRAINT active_revoke_sane CHECK (
    (active IS NULL AND revoke_event IS NOT NULL AND revoker_id IS NOT NULL)
    OR (active IS NOT NULL AND revoke_event IS NULL AND revoker_id IS NULL));


SELECT 'Updating table group_package_listing';

ALTER TABLE group_package_listing ADD COLUMN creator_id INTEGER REFERENCES users(id);
ALTER TABLE group_package_listing ADD COLUMN revoker_id INTEGER REFERENCES users(id);

UPDATE group_package_listing SET creator_id=pg_temp.user() WHERE creator_id IS NULL;
UPDATE group_package_listing SET revoker_id=pg_temp.user() WHERE revoker_id IS NULL AND revoke_event IS NOT NULL;

ALTER TABLE group_package_listing ALTER COLUMN creator_id SET NOT NULL;
ALTER TABLE group_package_listing DROP CONSTRAINT active_revoke_sane;
ALTER TABLE group_package_listing ADD CONSTRAINT active_revoke_sane CHECK (
    (active IS NULL AND revoke_event IS NOT NULL AND revoker_id IS NOT NULL)
    OR (active IS NOT NULL AND revoke_event IS NULL AND revoker_id IS NULL));

COMMIT;
