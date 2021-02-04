Migrating to Koji 1.24
======================

You should consider the following changes when migrating to 1.24:

DB Updates
----------

This release includes one minor schema change.

As we now can have architectures defined for individual external repos, we need
to reflect it in db. (see `PR#2564
<https://pagure.io/koji/pull-request/2564>`_).

As in previous releases, we provide a migration script that updates the database.

::

    # psql koji koji < /usr/share/doc/koji/docs/schema-upgrade-1.23-1.24.sql


Other changes
-------------

There are numerous other changes in 1.24 that should not have a direct impact on migration. For
details see: :doc:`../release_notes/release_notes_1.24`
