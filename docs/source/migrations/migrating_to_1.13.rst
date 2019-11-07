Migrating to Koji 1.13
======================

..
  reStructured Text formatted

The 1.13 release of Koji includes several changes that you should consider when
migrating.

DB Updates
----------

We have increased the length limit for tag names and there is a minor schema
change to support this.

As in previous releases, we provide a migration script that updates the
database.

::

    # psql koji koji  </usr/share/doc/koji/docs/schema-upgrade-1.12-1.13.sql


Packaging changes
-----------------

Because the CLI and base library now support both python2 and python3, the core
libs and most of the cli code have moved to separate packages for each major
Python version:

    * python2-koji
    * python3-koji

The main koji package still contains the (now much smaller) koji script, and
requires either python2-koji or python3-koji, depending on whether python3
support is enabled.

The CLI now also supports plugins, and two commands (runroot and
save-failed-tree) have moved to the `python[23]-koji-cli-plugins`
subpackages. If you need these subcommands, you may need to explicitly install
the appropriate koji-cli-plugins package.


Other changes
-------------

There are numerous other changes in 1.13 that should not have a direct impact
on migration. For details see:
:doc:`../release_notes/release_notes_1.13`
