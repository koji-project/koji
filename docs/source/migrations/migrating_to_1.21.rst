Migrating to Koji 1.21
======================

You should consider the following changes when migrating to 1.21:

DB Updates
----------

There are no big database schema changes in this release.

We've updated table with events and ``get_event()`` function to better handle
timeline (`PR#2068 <https://pagure.io/koji/pull-request/2068>`_) and set default
merge mode for external repos (`PR#2051 <https://pagure.io/koji/pull-request/2051>`_)

As in previous releases, we provide a migration script that updates the
database.

::

    # psql koji koji < /usr/share/doc/koji/docs/schema-upgrade-1.20-1.21.sql


Other changes
-------------

There are numerous other changes in 1.21 that should not have a direct impact on
migration. For details see: :doc:`../release_notes/release_notes_1.21`
