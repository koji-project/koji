Migrating to Koji 1.20
======================

You should consider the following changes when migrating to 1.20:

DB Updates
----------

There are no big database schema changes in this release. There is only cleanup
of potentially not `dropped old constraint <https://pagure.io/koji/issue/1789>`_.

As in previous releases, we provide a migration script that updates the
database.

::

    # psql koji koji < /usr/share/doc/koji/docs/schema-upgrade-1.19-1.20.sql


Other changes
-------------

There are numerous other changes in 1.20 that should not have a direct impact on
migration. For details see: :doc:`../release_notes/release_notes_1.20`
