-- upgrade script to migrate the Koji database schema
-- from version 1.13 to 1.14

BEGIN;

-- drop unused log_messages table
DROP TABLE log_messages;

COMMIT;
