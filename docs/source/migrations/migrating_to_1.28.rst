Migrating to Koji 1.28
======================

You should consider the following changes when migrating to 1.28:

DB Updates
----------

There is a simple schema change adding descriptions to individual permissions.

As in previous releases, we provide a migration script that updates the database.

::

    # psql koji koji < /usr/share/doc/koji/docs/schema-upgrade-1.27-1.28.sql


Other changes
-------------

There are numerous other changes in 1.28 that should not have a direct impact on migration. For
details see: :doc:`../release_notes/release_notes_1.28`
