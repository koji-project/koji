Migrating to Koji 1.16
======================

..
  reStructured Text formatted

You should consider the following changes when migrating to 1.16:

DB Updates
----------

This release has schema changes to support tracking history for hosts.

    * new table: ``host_config``
    * some fields from the ``host`` table have moved to ``host_config``
    * the ``host_channels`` table now has versioning data like the other
      versioned tables

As in previous releases, we provide a migration script that updates the
database.

::

    # psql koji koji  </usr/share/doc/koji/docs/schema-upgrade-1.15-1.16.sql


Other changes
-------------

There are numerous other changes in 1.16 that should not have a direct impact
on migration. For details see:
:doc:`../release_notes/release_notes_1.16`
