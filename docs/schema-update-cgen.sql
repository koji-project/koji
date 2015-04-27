BEGIN;

-- New tables
CREATE TABLE content_generator (
       id SERIAL PRIMARY KEY,
       name TEXT
) WITHOUT OIDS;

CREATE TABLE cg_users (
       cg_id INTEGER NOT NULL REFERENCES content_generator (id),
       user_id INTEGER NOT NULL REFERENCES users (id),
       PRIMARY KEY (cg_id, user_id)
-- XXX: should we version this?
) WITHOUT OIDS;

CREATE TABLE buildroot_tools_info (
       buildroot_id INTEGER NOT NULL REFERENCES buildroot(id),
       tool TEXT NOT NULL,
       version TEXT NOT NULL,
       PRIMARY KEY (buildroot_id, tool)
) WITHOUT OIDS;

CREATE TABLE buildroot_extra_info (
       buildroot_id INTEGER NOT NULL REFERENCES buildroot(id),
       key TEXT NOT NULL,
       value TEXT NOT NULL,
       PRIMARY KEY (buildroot_id, key)
) WITHOUT OIDS;


CREATE TABLE image_archive_listing (
       image_id INTEGER NOT NULL REFERENCES image_archives(archive_id),
       archive_id INTEGER NOT NULL REFERENCES archiveinfo(id),
       UNIQUE (image_id, archive_id)
) WITHOUT OIDS;
CREATE INDEX image_listing_archives on image_archive_listing(archive_id);


CREATE TABLE standard_buildroot (
       buildroot_id INTEGER NOT NULL PRIMARY KEY REFERENCES buildroot(id),
       host_id INTEGER NOT NULL REFERENCES host(id),
       repo_id INTEGER NOT NULL REFERENCES repo (id),
       task_id INTEGER NOT NULL REFERENCES task (id),
       create_event INTEGER NOT NULL REFERENCES events(id) DEFAULT get_event(),
       retire_event INTEGER,
       state INTEGER
) WITHOUT OIDS;

-- the more complicated stuff

INSERT INTO
    standard_buildroot(buildroot_id, host_id, repo_id, task_id, create_event, retire_event, state)
SELECT id, host_id, repo_id, task_id, create_event, retire_event, state from buildroot;





