Migrating to Koji 1.35
======================

You should consider the following changes when migrating to 1.35:

DB Updates
----------

Changes for new repo handling introduced a few new tables.

As in previous releases, we provide a migration script that updates the database.

::

    # psql koji koji < /usr/share/doc/koji/docs/schema-upgrade-1.34-1.35.sql


Other changes
-------------

There are numerous other changes in 1.35 that should not have a direct impact
on migration. For details see: :doc:`../release_notes/release_notes_1.35`
