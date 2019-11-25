-- upgrade script to migrate the Koji database schema
-- from version 1.14 to 1.16


BEGIN;

-- create host_config table
SELECT 'Creating table host_config';
CREATE TABLE host_config (
        host_id INTEGER NOT NULL REFERENCES host(id),
        arches TEXT,
        capacity FLOAT CHECK (capacity > 1) NOT NULL DEFAULT 2.0,
        description TEXT,
        comment TEXT,
        enabled BOOLEAN NOT NULL DEFAULT 'true',
-- versioned - see desc above
        create_event INTEGER NOT NULL REFERENCES events(id) DEFAULT get_event(),
        revoke_event INTEGER REFERENCES events(id),
        creator_id INTEGER NOT NULL REFERENCES users(id),
        revoker_id INTEGER REFERENCES users(id),
        active BOOLEAN DEFAULT 'true' CHECK (active),
        CONSTRAINT active_revoke_sane CHECK (
                (active IS NULL AND revoke_event IS NOT NULL AND revoker_id IS NOT NULL)
                OR (active IS NOT NULL AND revoke_event IS NULL AND revoker_id IS NULL)),
        PRIMARY KEY (create_event, host_id),
        UNIQUE (host_id, active)
) WITHOUT OIDS;
CREATE INDEX host_config_by_active_and_enabled ON host_config(active, enabled);

-- copy starting data
-- CREATE FUNCTION pg_temp.user() returns INTEGER as $$ select id from users where name='nobody' $$ language SQL;
CREATE FUNCTION pg_temp.user() returns INTEGER as $$ select 1 $$ language SQL;
-- If you would like to use an existing user instead, then:
--   1. edit the temporary function to look for the alternate user name

SELECT 'Copying data from host to host_config';
INSERT INTO host_config (host_id, arches, capacity, description, comment, enabled, creator_id)
        SELECT id, arches, capacity, description, comment, enabled, pg_temp.user() FROM host;

-- alter original table
SELECT 'Dropping moved columns';
ALTER TABLE host DROP COLUMN arches;
ALTER TABLE host DROP COLUMN capacity;
ALTER TABLE host DROP COLUMN description;
ALTER TABLE host DROP COLUMN comment;
ALTER TABLE host DROP COLUMN enabled;

-- history for host_channels
SELECT 'Adding versions to host_channels';
ALTER TABLE host_channels ADD COLUMN create_event INTEGER NOT NULL REFERENCES events(id) DEFAULT get_event();
ALTER TABLE host_channels ADD COLUMN revoke_event INTEGER REFERENCES events(id);
-- we need some default for alter table, but drop it after
ALTER TABLE host_channels ADD COLUMN creator_id INTEGER NOT NULL REFERENCES users(id) DEFAULT pg_temp.user();
ALTER TABLE host_channels ALTER COLUMN creator_id DROP DEFAULT;
ALTER TABLE host_channels ADD COLUMN revoker_id INTEGER REFERENCES users(id);
ALTER TABLE host_channels ADD COLUMN active BOOLEAN DEFAULT 'true' CHECK (active);
ALTER TABLE host_channels ADD CONSTRAINT active_revoke_sane CHECK (
                                         (active IS NULL AND revoke_event IS NOT NULL AND revoker_id IS NOT NULL)
                                         OR (active IS NOT NULL AND revoke_event IS NULL AND revoker_id IS NULL));
ALTER TABLE host_channels ADD PRIMARY KEY (create_event, host_id, channel_id);
ALTER TABLE host_channels ADD UNIQUE (host_id, channel_id, active);
ALTER TABLE host_channels DROP CONSTRAINT host_channels_host_id_channel_id_key;
-- drop potential very old constraint (https://pagure.io/koji/issue/1789)
ALTER TABLE host_channels DROP CONSTRAINT IF EXISTS host_channels_host_id_key;

COMMIT;
