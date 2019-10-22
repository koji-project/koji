Migrating to Koji 1.19
======================

..
  reStructured Text formatted

You should consider the following changes when migrating to 1.19:

DB Updates
----------

This release has a few schema changes:

    * A new ``tag_package_owners`` table
    * A new ``user_krb_principals`` table
    * Updates to the data in the ``archivetypes`` table
    * Updates to the data in the ``permissions`` table
    * The ``content_generator`` table now enforces unique strings in the ``names`` field

As in previous releases, we provide a migration script that updates the
database.

::

    # psql koji koji  </usr/share/doc/koji/docs/schema-upgrade-1.18-1.19.sql


Other changes
-------------

There are numerous other changes in 1.19 that should not have a direct impact
on migration. For details see:
:doc:`../release_notes/release_notes_1.19`
