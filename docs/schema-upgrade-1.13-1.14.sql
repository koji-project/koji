-- upgrade script to migrate the Koji database schema
-- from version 1.13 to 1.14

BEGIN;

-- drop unused log_messages table
DROP TABLE log_messages;

-- add yaml and xjb file type in archivetypes
insert into archivetypes (name, description, extensions) values ('yaml', 'YAML Ain''t Markup Language', 'yaml yml');
insert into archivetypes (name, description, extensions) values ('xjb', 'JAXB(Java Architecture for XML Binding) Binding Customization File', 'xjb');

COMMIT;
