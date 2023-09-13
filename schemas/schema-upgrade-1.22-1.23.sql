-- upgrade script to migrate the Koji database schema
-- from version 1.22 to 1.23


BEGIN;

CREATE INDEX task_by_no_parent_state_method ON task(parent, state, method) WHERE parent IS NULL;

ALTER TABLE tag_extra ALTER COLUMN value DROP NOT NULL;

-- Message queue for the protonmsg plugin
CREATE TABLE proton_queue (
        id SERIAL PRIMARY KEY,
        created_ts TIMESTAMPTZ DEFAULT NOW(),
        address TEXT NOT NULL,
        props JSON NOT NULL,
        body JSON NOT NULL
) WITHOUT OIDS;


COMMIT;
