Migrating to Koji 1.23
======================

You should consider the following changes when migrating to 1.23:

DB Updates
----------

This release includes some minor schema changes.

We've dropped the ``NOT NULL`` restriction on the ``value`` column of the
``tag_extra`` table as part of the changes to allow blocking these values in
the inheritance (see `PR#2495 <https://pagure.io/koji/pull-request/2495>`_).

We've also added a new ``proton_queue`` table that is used by the ``protonmsg``
plugin when it is configured to queue messages
(see `PR#2441 <https://pagure.io/koji/pull-request/2441>`_)

Lastly, we've added a new index for the ``task`` table to improve performance
(see `PR#2419 <https://pagure.io/koji/pull-request/2419>`_)

As in previous releases, we provide a migration script that updates the database.

::

    # psql koji koji < /usr/share/doc/koji/docs/schema-upgrade-1.22-1.23.sql


Other changes
-------------

There are numerous other changes in 1.23 that should not have a direct impact on migration. For
details see: :doc:`../release_notes/release_notes_1.23`
