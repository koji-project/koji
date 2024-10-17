Migrating to Koji 1.34
======================

You should consider the following changes when migrating to 1.34:

DB Updates
----------

There is a simple schema change adding new index.

As in previous releases, we provide a migration script that updates the database.

::

    # psql koji koji < /usr/share/koji/schema-upgrade-1.33-1.34.sql


Other changes
-------------

There are numerous other changes in 1.34 that should not have a direct impact on migration. For
details see: :doc:`../release_notes/release_notes_1.34`
