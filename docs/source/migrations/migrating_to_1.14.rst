Migrating to Koji 1.14
======================

..
  reStructured Text formatted

You should consider the following changes when migrating to 1.14:

DB Updates
----------

The schema updates this time are minor

   * dropped unused ``log_messages`` table
   * new standard entries in the ``archivetypes`` table

As in previous releases, we provide a migration script that updates the
database.

::

    # psql koji koji  </usr/share/doc/koji/docs/schema-upgrade-1.13-1.14.sql


Dropped mod_python support
--------------------------

Koji's support for mod_python has been deprecated for many years. If you are
still relying on mod_python, you will need to switch to mod_wsgi.

See: :doc:`migrating_to_1.7`


Other changes
-------------

There are numerous other changes in 1.14 that should not have a direct impact
on migration. For details see:
:doc:`../release_notes/release_notes_1.14`
