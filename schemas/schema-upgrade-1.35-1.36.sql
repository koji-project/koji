-- upgrade script to migrate the Koji database schema
-- from version 1.35 to 1.36

BEGIN;

INSERT INTO archivetypes (name, description, extensions) VALUES ('erofs', 'erofs image', 'erofs') ON CONFLICT DO NOTHING;
INSERT INTO archivetypes (name, description, extensions) VALUES ('erofs-compressed', 'Compressed erofs image', 'erofs.gz erofs.xz') ON CONFLICT DO NOTHING;
INSERT INTO archivetypes (name, description, extensions) VALUES ('squashfs', 'SquashFS image', 'squashfs') ON CONFLICT DO NOTHING;
INSERT INTO archivetypes (name, description, extensions) VALUES ('squashfs-compressed', 'Compressed SquashFS image', 'squashfs.gz squashfs.xz') ON CONFLICT DO NOTHING;

COMMIT;
