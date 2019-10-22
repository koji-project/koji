Migrating to Koji 1.12
======================

..
  reStructured Text formatted

The 1.12 release of Koji includes a several changes that you should consider when
migrating.

DB Updates
----------

There is a minor update to support the dist-repos feature:
    * The ``repo`` table now has a ``dist`` column

Additionally, the schema explicitly adds the ``image`` permission to the
permissions table, correcting an old oversight.

As in previous releases, we provide a migration script that updates the
database.

::

    # psql koji koji  </usr/share/doc/koji/docs/schema-upgrade-1.11-1.12.sql


Command line changes
--------------------

The ``import-sig`` command now now supports a ``--write`` option to immediately
write out a signed copy.

The ``write-signed-rpm`` command previously (and confusingly) only accepted
nvrs as arguments (i.e. builds not rpms). Now it accepts either nvras or nvrs
(rpms or builds).

The ``clone-tag`` command has been refactored. It supports many more options
and should execute much faster than before.

The new ``dist-repo`` command creates rpm repos suitable for distribution.

The new ``save-failed-tree`` command allows the a task owner (or admin)
to download information from the buildroot of a failed build. This feature
requires the ``save_failed_tree`` plugin to be enabled on the hub and builders.


Configuration
-------------

The only configuration changes are for the ``save-failed-tree`` plugins (hub
and builder). Each has its own configuration file. See :doc:`../plugins`

The hub accepts a new ``CheckClientIP`` option (default True) to indicate
whether authentication credentials should be tied to the client's IP address.
(For some proxy setups, this may need to be set to False).


RPC API Changes
---------------

New rpc calls:

``listPackagesSimple``
    handles a limited subset of the
    functionality provided by the ``listPackages`` call

``distRepo``
    triggers generation of a distribution repo

Changes to calls:
    * repo related calls (e.g. ``repoInfo`` now include a boolean ``dist``
      field
    * the ``editTag2`` call can now remove tag_extra data if the
      ``remove_extra`` keyword argument is used
    * the listTaskOutput call supports a new ``all_volumes`` keyword argument.
      If true, the results are extended to deal with files in same relative paths
      on different volumes.
    * the ``getTaskResult`` call takes an optional boolean ``raise_fault``
      argument
    * the ``taskWaitResults`` call takes an optional ``canfail`` argument
      to indicate subtasks which can fail without raising an exception
