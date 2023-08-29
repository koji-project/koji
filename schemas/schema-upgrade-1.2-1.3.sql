-- upgrade script to migrate the Koji database schema
-- from version 1.2 to 1.3

BEGIN;

-- external yum repos
create table external_repo (
	id SERIAL NOT NULL PRIMARY KEY,
	name TEXT UNIQUE NOT NULL
);
-- fake repo id for internal stuff (needed for unique index)
INSERT INTO external_repo (id, name) VALUES (0, 'INTERNAL');

create table external_repo_config (
	external_repo_id INTEGER NOT NULL REFERENCES external_repo(id),
	url TEXT NOT NULL,
-- versioned - see earlier description of versioning
	create_event INTEGER NOT NULL REFERENCES events(id) DEFAULT get_event(),
	revoke_event INTEGER REFERENCES events(id),
	active BOOLEAN DEFAULT 'true' CHECK (active),
	CONSTRAINT active_revoke_sane CHECK (
		(active IS NULL AND revoke_event IS NOT NULL )
		OR (active IS NOT NULL AND revoke_event IS NULL )),
	PRIMARY KEY (create_event, external_repo_id),
	UNIQUE (external_repo_id, active)
) WITHOUT OIDS;

create table tag_external_repos (
	tag_id INTEGER NOT NULL REFERENCES tag(id),
	external_repo_id INTEGER NOT NULL REFERENCES external_repo(id),
	priority INTEGER NOT NULL,
-- versioned - see earlier description of versioning
	create_event INTEGER NOT NULL REFERENCES events(id) DEFAULT get_event(),
	revoke_event INTEGER REFERENCES events(id),
	active BOOLEAN DEFAULT 'true' CHECK (active),
	CONSTRAINT active_revoke_sane CHECK (
		(active IS NULL AND revoke_event IS NOT NULL )
		OR (active IS NOT NULL AND revoke_event IS NULL )),
	PRIMARY KEY (create_event, tag_id, priority),
	UNIQUE (tag_id, priority, active),
	UNIQUE (tag_id, external_repo_id, active)
);
 
-- add the new column then set the existing packages to have the INTERNAL exteranl repo id
-- then add the not null constraint 
-- then drop rpminfo_unique_nvra CONSTRAINT and add the new version
ALTER TABLE rpminfo ADD COLUMN external_repo_id INTEGER REFERENCES external_repo(id);
UPDATE rpminfo SET external_repo_id = 0;
ALTER TABLE rpminfo ALTER COLUMN external_repo_id SET NOT NULL;
ALTER TABLE rpminfo DROP CONSTRAINT rpminfo_unique_nvra;
ALTER TABLE rpminfo ADD CONSTRAINT rpminfo_unique_nvra UNIQUE (name,version,release,arch,external_repo_id);
 
GRANT SELECT ON external_repo, external_repo_config, tag_external_repos TO PUBLIC;

-- these tables are no longer included with newer koji 
-- feel free to drop them
-- DROP TABLE rpmfiles;                                                                     
-- DROP TABLE rpmdeps;  
-- DROP TABLE changelogs;
-- DROP TABLE archivefiles;

COMMIT;
