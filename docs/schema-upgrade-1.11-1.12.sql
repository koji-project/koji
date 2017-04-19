BEGIN;

-- from schema-update-dist-repos.sql

INSERT INTO permissions (name) VALUES ('image');

ALTER TABLE repo ADD COLUMN dist BOOLEAN;
ALTER TABLE repo ALTER COLUMN dist SET DEFAULT 'false';
UPDATE repo SET dist = 'false';

COMMIT;
