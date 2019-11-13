-- upgrade script to migrate the Koji database schema
-- from version 1.19 to 1.20


BEGIN;

-- drop potential very old constraint (https://pagure.io/koji/issue/1789)
ALTER TABLE host_channels DROP CONSTRAINT IF EXISTS host_channels_host_id_key;

COMMIT;
