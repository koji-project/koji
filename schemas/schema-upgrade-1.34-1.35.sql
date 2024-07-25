-- upgrade script to migrate the Koji database schema
-- from version 1.33 to 1.34

BEGIN;

-- repos on demand
ALTER TABLE repo ADD COLUMN creation_time TIMESTAMPTZ DEFAULT NOW();
ALTER TABLE repo ADD COLUMN state_time TIMESTAMPTZ DEFAULT NOW();
ALTER TABLE repo ADD COLUMN begin_event INTEGER REFERENCES events(id);
ALTER TABLE repo ADD COLUMN end_event INTEGER REFERENCES events(id);
ALTER TABLE repo ADD COLUMN opts JSONB;
ALTER TABLE repo ADD COLUMN custom_opts JSONB;

CREATE TABLE repo_queue (
        id SERIAL NOT NULL PRIMARY KEY,
        create_time TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        owner INTEGER REFERENCES users(id) NOT NULL,
        priority INTEGER NOT NULL,
        tag_id INTEGER NOT NULL REFERENCES tag(id),
        at_event INTEGER REFERENCES events(id),
        min_event INTEGER REFERENCES events(id),
        opts JSONB NOT NULL,
        CONSTRAINT only_one_event CHECK (at_event IS NULL OR min_event IS NULL),
        update_time TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        active BOOLEAN NOT NULL DEFAULT TRUE,
        task_id INTEGER REFERENCES task(id),
        tries INTEGER NOT NULL DEFAULT 0,
        repo_id INTEGER REFERENCES repo(id),
        CONSTRAINT active_sane CHECK (NOT active OR repo_id IS NULL)
) WITHOUT OIDS;

CREATE TABLE external_repo_data (
        external_repo_id INTEGER NOT NULL REFERENCES external_repo(id),
        data JSONB,
        create_event INTEGER NOT NULL REFERENCES events(id) DEFAULT get_event(),
        revoke_event INTEGER REFERENCES events(id),
        creator_id INTEGER NOT NULL REFERENCES users(id),
        revoker_id INTEGER REFERENCES users(id),
        active BOOLEAN DEFAULT 'true' CHECK (active),
        CONSTRAINT active_revoke_sane CHECK (
                (active IS NULL AND revoke_event IS NOT NULL AND revoker_id IS NOT NULL)
                OR (active IS NOT NULL AND revoke_event IS NULL AND revoker_id IS NULL)),
        PRIMARY KEY (create_event, external_repo_id),
        UNIQUE (external_repo_id, active)
) WITHOUT OIDS;

INSERT INTO locks(name) VALUES('repo-queue');


-- new rpminfo index needed because of draft build changes
CREATE INDEX IF NOT EXISTS rpminfo_nvra
    ON rpminfo(name,version,release,arch,external_repo_id);

COMMIT;
