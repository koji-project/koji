-- upgrade script to migrate the Koji database schema
-- from version 1.29 to 1.30


BEGIN;

-- clean some unused old indices if they still exist
-- https://pagure.io/koji/issue/3160
DROP INDEX IF EXISTS image_listing_archives;
DROP INDEX IF EXISTS image_listing_rpms;
DROP INDEX IF EXISTS imageinfo_listing_rpms;

COMMIT;
