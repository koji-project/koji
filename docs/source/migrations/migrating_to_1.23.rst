Migrating to Koji 1.23
======================

You should consider the following changes when migrating to 1.23:

DB Updates
----------

There is one minor schema change in this release. We've dropped NOT NULL
restriction on tag_extra value column to allow block these values in hierarchy
(`PR#2495 <https://pagure.io/koji/pull-request/2495>`_).

As in previous releases, we provide a migration script that updates the database.

::

    # psql koji koji < /usr/share/doc/koji/docs/schema-upgrade-1.22-1.23.sql


Other changes
-------------

There are numerous other changes in 1.23 that should not have a direct impact on migration. For
details see: :doc:`../release_notes/release_notes_1.23`
