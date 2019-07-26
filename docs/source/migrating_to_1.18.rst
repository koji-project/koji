Migrating to Koji 1.18
======================

..
  reStructured Text formatted

You should consider the following changes when migrating to 1.18:

DB Updates
----------

This release has a few schema changes:

    * Several new indexes to speed operations
    * A ``cg_id`` field has been added to the ``build`` table
    * A new ``build_reservations`` table
    * A new ``build_notifications_block`` table
    * Updates to the data in the ``archivetypes`` table

As in previous releases, we provide a migration script that updates the
database.

::

    # psql koji koji  </usr/share/doc/koji/docs/schema-upgrade-1.17-1.18.sql


Other changes
-------------

There are numerous other changes in 1.18 that should not have a direct impact
on migration. For details see:
:doc:`release_notes_1.18`
