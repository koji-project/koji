-- upgrade script to migrate the Koji database schema
-- from version 1.30 to 1.31

BEGIN;
    -- index for default search method for rpms, PG11+ can benefit from new include method
    DO $$
       DECLARE version integer;
       BEGIN
           SELECT current_setting('server_version_num')::integer INTO version;
           IF version >= 110000 THEN
               EXECUTE 'CREATE INDEX rpminfo_filename ON rpminfo((name || ''-'' || version || ''-'' || release || ''.'' || arch || ''.rpm'')) INCLUDE (id);';
           ELSE
               EXECUTE 'CREATE INDEX rpminfo_filename ON rpminfo((name || ''-'' || version || ''-'' || release || ''.'' || arch || ''.rpm''));';
           END IF;
       END
    $$;
COMMIT;
