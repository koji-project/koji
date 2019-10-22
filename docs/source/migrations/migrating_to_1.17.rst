Migrating to Koji 1.17
======================

..
  reStructured Text formatted

You should consider the following changes when migrating to 1.17:

DB Updates
----------

This release some minor schema changes

    * the ``tag_external_repos`` table has a new ``merge_mode`` column
    * the ``build_target.name`` column is now a TEXT field rather than VARCHAR

As in previous releases, we provide a migration script that updates the
database.

::

    # psql koji koji  </usr/share/doc/koji/docs/schema-upgrade-1.16-1.17.sql


Other changes
-------------

There are numerous other changes in 1.17 that should not have a direct impact
on migration. For details see:
:doc:`../release_notes/release_notes_1.17`
