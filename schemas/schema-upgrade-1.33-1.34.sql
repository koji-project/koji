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
COMMIT;
