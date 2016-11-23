# schema updates for signed repo feature
# to be merged into schema upgrade script for next release

INSERT INTO permissions (name) VALUES ('image');

ALTER TABLE repo ADD COLUMN signed BOOLEAN DEFAULT 'false';

