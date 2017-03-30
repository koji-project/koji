BEGIN;

-- from schema-update-dist-repos.sql

INSERT INTO permissions (name) VALUES ('image');

ALTER TABLE repo ADD COLUMN dist BOOLEAN DEFAULT 'false';

COMMIT;
