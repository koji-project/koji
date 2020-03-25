-- upgrade script to migrate the Koji database schema
-- from version 1.20 to 1.21


BEGIN;

-- make better events
ALTER TABLE events ALTER COLUMN time SET NOT NULL;
ALTER TABLE events ALTER COLUMN time SET DEFAULT clock_timestamp();

CREATE OR REPLACE FUNCTION get_event() RETURNS INTEGER AS '
    INSERT INTO events (time) VALUES (clock_timestamp());
    SELECT currval(''events_id_seq'')::INTEGER;
' LANGUAGE SQL;

-- merge_mode can not be null
UPDATE tag_external_repos SET merge_mode = 'koji' WHERE merge_mode is NULL;
ALTER TABLE tag_external_repos ALTER COLUMN merge_mode SET NOT NULL;

COMMIT;
