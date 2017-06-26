Migrating to Koji 1.13
======================

..
  reStructured Text formatted

The 1.13 release of Koji includes a several changes that you should consider when
migrating.

DB Updates
----------

We have increased the length limit for tag names and there is a minor schema
change to support this.

As in previous releases, we provide a migration script that updates the
database.

::

    # psql koji koji  </usr/share/doc/koji/docs/schema-upgrade-1.12-1.13.sql


Command line changes
--------------------

For full details see the release notes.

New commands: ``list-channels``, ``hostinfo``

The ``restart-hosts`` command takes several new options and now defaults to
a 24 hour timeout.


Packaging changes
-----------------

Because the CLI and base library now support both python2 and python3, the core libs
and most of the cli code have moved to separate packages for each major Python
version:

    * python2-koji
    * python3-koji

The main koji package still contains the (now much smaller) koji script.

The CLI now also supports plugins, and two commands (runroot and
save-failed-tree) have moved to the ``python[23]-koji-cli-plugins`` subpackages.


Configuration
-------------

The ``allowed_scms`` option supports a new syntax. See the release notes for details.
