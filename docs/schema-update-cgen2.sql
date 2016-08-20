BEGIN;

-- New tables

SELECT statement_timestamp(), 'Creating new tables' as msg;

CREATE TABLE btype (
        id SERIAL NOT NULL PRIMARY KEY,
        name TEXT UNIQUE NOT NULL
) WITHOUT OIDS;

CREATE TABLE build_types (
        build_id INTEGER NOT NULL REFERENCES build(id),
        btype_id INTEGER NOT NULL REFERENCES btype(id),
        PRIMARY KEY (build_id, btype_id)
) WITHOUT OIDS;

-- predefined build types

SELECT statement_timestamp(), 'Adding predefined build types' as msg;
INSERT INTO btype(name) VALUES ('rpm');
INSERT INTO btype(name) VALUES ('maven');
INSERT INTO btype(name) VALUES ('win');
INSERT INTO btype(name) VALUES ('image');


COMMIT;

