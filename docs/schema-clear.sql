
-- vim:noet:sw=8

BEGIN;

SELECT 'About to DELETE ALL DATA in koji database' as WARNING;
SELECT pg_sleep(5);

DROP TABLE IF EXISTS win_archives;
DROP TABLE IF EXISTS buildroot_archives;
DROP TABLE IF EXISTS image_archive_listing;
DROP TABLE IF EXISTS image_listing;
DROP TABLE IF EXISTS image_archives;
DROP TABLE IF EXISTS maven_archives;
DROP TABLE IF EXISTS archiveinfo;
DROP TABLE IF EXISTS archivetypes;
DROP TABLE IF EXISTS win_builds;
DROP TABLE IF EXISTS maven_builds;
DROP TABLE IF EXISTS build_notifications;
DROP TABLE IF EXISTS buildroot_listing;
DROP TABLE IF EXISTS rpmsigs;
DROP TABLE IF EXISTS rpminfo;
DROP TABLE IF EXISTS group_package_listing;
DROP TABLE IF EXISTS group_req_listing;
DROP TABLE IF EXISTS group_config;
DROP TABLE IF EXISTS groups;
DROP TABLE IF EXISTS tag_packages;
DROP TABLE IF EXISTS tag_listing;
DROP TABLE IF EXISTS image_builds;
DROP TABLE IF EXISTS buildroot_tools_info;
DROP TABLE IF EXISTS standard_buildroot;
DROP TABLE IF EXISTS buildroot;
DROP TABLE IF EXISTS cg_users;
DROP TABLE IF EXISTS content_generator;
DROP TABLE IF EXISTS tag_external_repos;
DROP TABLE IF EXISTS external_repo_config;
DROP TABLE IF EXISTS external_repo;
DROP TABLE IF EXISTS repo;
DROP TABLE IF EXISTS build_target_config;
DROP TABLE IF EXISTS build_target;
DROP TABLE IF EXISTS tag_updates;
DROP TABLE IF EXISTS tag_extra;
DROP TABLE IF EXISTS tag_config;
DROP TABLE IF EXISTS tag_inheritance;
DROP TABLE IF EXISTS tag;
DROP TABLE IF EXISTS build;
DROP TABLE IF EXISTS volume;
DROP TABLE IF EXISTS package;
DROP TABLE IF EXISTS task;
DROP TABLE IF EXISTS host_channels;
DROP TABLE IF EXISTS host;
DROP TABLE IF EXISTS channels;
DROP TABLE IF EXISTS sessions;
DROP TABLE IF EXISTS user_groups;
DROP TABLE IF EXISTS user_perms;
DROP TABLE IF EXISTS permissions;
DROP TABLE IF EXISTS users;
DROP TABLE IF EXISTS event_labels;
DROP TABLE IF EXISTS events;

DROP FUNCTION IF EXISTS get_event();
DROP FUNCTION IF EXISTS get_event_time(INTEGER);


SELECT 'About to commit table drops' as WARNING;
SELECT pg_sleep(5);

COMMIT;
