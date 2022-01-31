-- upgrade script to migrate the Koji database schema
-- from version 1.27 to 1.28


BEGIN;

ALTER TABLE permissions ADD COLUMN description TEXT;

UPDATE permissions set description='Full administrator access. Perform all actions.' WHERE name = 'admin';
UPDATE permissions set description='Create appliance builds - deprecated.' WHERE name = 'appliance';
UPDATE permissions set description='Create a dist-repo.' WHERE name = 'dist-repo';
UPDATE permissions set description='Add, remove, enable, disable hosts and channels.' WHERE name = 'host';
UPDATE permissions set description='Start image tasks.' WHERE name = 'image';
UPDATE permissions set description='Import image archives.' WHERE name = 'image-import';
UPDATE permissions set description='Start livecd tasks.' WHERE name = 'livecd';
UPDATE permissions set description='Import maven archives.' WHERE name = 'maven-import';
UPDATE permissions set description='Manage repos: newRepo, repoExpire, repoDelete, repoProblem.' WHERE name = 'repo';
UPDATE permissions set description='Import RPM signatures and write signed RPMs.' WHERE name = 'sign';
UPDATE permissions set description='Manage packages in tags: add, block, remove, and clone tags.' WHERE name = 'tag';
UPDATE permissions set description='Add, edit, and remove targets.' WHERE name = 'target';
UPDATE permissions set description='The default hub policy rule for "vm" requires this permission to trigger Windows builds.' WHERE name = 'win-admin';
UPDATE permissions set description='Import win archives.' WHERE name = 'win-import';

COMMIT;
