Migrating to Koji 1.25
======================

You should consider the following changes when migrating to 1.25:

DB Updates
----------

This release includes one schema change.

Each repo now contains a link to the task which was used to create it (`Issue #888
<https://pagure.io/koji/issue/888>`_)


As in previous releases, we provide a migration script that updates the database.

::

    # psql koji koji < /usr/share/doc/koji/docs/schema-upgrade-1.24-1.25.sql


Other changes
-------------

There are numerous other changes in 1.25 that should not have a direct impact on migration. For
details see: :doc:`../release_notes/release_notes_1.25`
