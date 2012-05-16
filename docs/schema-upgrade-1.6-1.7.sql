BEGIN;

CREATE TABLE volume (
        id SERIAL NOT NULL PRIMARY KEY,
        name TEXT UNIQUE NOT NULL
) WITHOUT OIDS;

INSERT INTO volume (id, name) VALUES (0, 'DEFAULT');

ALTER TABLE build ADD COLUMN volume_id INTEGER REFERENCES volume (id);
UPDATE build SET volume_id = 0;
ALTER TABLE build ALTER COLUMN volume_id SET NOT NULL;

CREATE TABLE tag_updates (
        id SERIAL NOT NULL PRIMARY KEY,
        tag_id INTEGER NOT NULL REFERENCES tag(id),
        update_event INTEGER NOT NULL REFERENCES events(id) DEFAULT get_event(),
        updater_id INTEGER NOT NULL REFERENCES users(id),
        update_type INTEGER NOT NULL
) WITHOUT OIDS;

CREATE INDEX tag_updates_by_tag ON tag_updates (tag_id);
CREATE INDEX tag_updates_by_event ON tag_updates (update_event);

COMMIT;
