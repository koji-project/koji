-- upgrade script to migrate the Koji database schema
-- from version 1.3 to 1.4

ALTER TABLE host ADD COLUMN description TEXT;
ALTER TABLE host ADD COLUMN comment TEXT;
