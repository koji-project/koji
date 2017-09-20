Migrating to Koji 1.14
======================

..
  reStructured Text formatted

The 1.14 release of Koji includes a several changes that you should consider when
migrating.

DB Updates
----------

The schema updates this time are minor

   * dropping unused `log_messages` table
   * new standard entries in the archivetypes table

As in previous releases, we provide a migration script that updates the
database.

::

    # psql koji koji  </usr/share/doc/koji/docs/schema-upgrade-1.13-1.14.sql


Other changes
-------------

There are numerous other changes in 1.14 that should not have a direct impact
on migration. For details see:
:doc:`release_notes_1.14`
