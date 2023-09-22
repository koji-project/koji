-- upgrade script to migrate the Koji database schema
-- from version 1.33 to 1.34

BEGIN;

    -- scheduler tables
    CREATE TABLE scheduler_task_runs (
            id SERIAL NOT NULL PRIMARY KEY,
            task_id INTEGER REFERENCES task (id) NOT NULL,
            host_id INTEGER REFERENCES host (id) NOT NULL,
            active BOOLEAN NOT NULL DEFAULT TRUE,
            create_time TIMESTAMPTZ NOT NULL DEFAULT NOW()
    ) WITHOUT OIDS;
    CREATE INDEX scheduler_task_runs_task ON scheduler_task_runs(task_id);
    CREATE INDEX scheduler_task_runs_host ON scheduler_task_runs(host_id);
    CREATE INDEX scheduler_task_runs_create_time ON scheduler_task_runs(create_time);


    CREATE TABLE scheduler_host_data (
            host_id INTEGER REFERENCES host (id) PRIMARY KEY,
            data JSONB
    ) WITHOUT OIDS;


    CREATE TABLE scheduler_sys_data (
            name TEXT NOT NULL PRIMARY KEY,
            data JSONB
    ) WITHOUT OIDS;


    CREATE TABLE scheduler_task_refusals (
            id SERIAL NOT NULL PRIMARY KEY,
            task_id INTEGER REFERENCES task (id) NOT NULL,
            host_id INTEGER REFERENCES host (id) NOT NULL,
            by_host BOOLEAN NOT NULL,
            soft BOOLEAN NOT NULL DEFAULT FALSE,
            msg TEXT,
            time TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            UNIQUE (task_id, host_id)
    ) WITHOUT OIDS;


    CREATE TABLE scheduler_log_messages (
            id SERIAL NOT NULL PRIMARY KEY,
            task_id INTEGER REFERENCES task (id),
            host_id INTEGER REFERENCES host (id),
            msg_time TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            msg TEXT NOT NULL
    ) WITHOUT OIDS;

    INSERT INTO locks(name) VALUES('scheduler');

    -- draft builds
    INSERT INTO permissions (name, description) VALUES ('draft-promoter', 'The permission required in the default "draft_promotion" hub policy rule to promote draft build.');

    ALTER TABLE build ADD COLUMN draft BOOLEAN NOT NULL DEFAULT 'false';
    ALTER TABLE build ADD CONSTRAINT draft_for_rpminfo UNIQUE (id, draft);
    ALTER TABLE build ADD CONSTRAINT draft_release_sane CHECK
        ((draft AND release ~ ('^.*#draft_' || id::TEXT || '$'))
        OR NOT draft);

    ALTER TABLE rpminfo ADD COLUMN draft BOOLEAN;
    ALTER TABLE rpminfo DROP CONSTRAINT rpminfo_build_id_fkey;
    ALTER TABLE rpminfo ADD CONSTRAINT rpminfo_build_id_draft_fkey
        FOREIGN KEY (build_id, draft) REFERENCES build(id, draft)
        ON UPDATE CASCADE;
    ALTER TABLE rpminfo DROP CONSTRAINT rpminfo_unique_nvra;
    ALTER TABLE rpminfo ADD CONSTRAINT build_id_draft_external_repo_id_sane
        CHECK ((draft IS NULL AND build_id IS NULL AND external_repo_id <> 0)
            OR (draft IS NOT NULL AND build_id IS NOT NULL AND external_repo_id = 0));
    CREATE UNIQUE INDEX rpminfo_unique_nvra_not_draft
        ON rpminfo(name,version,release,arch,external_repo_id)
        WHERE draft IS NOT TRUE;

COMMIT;
