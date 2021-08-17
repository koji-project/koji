Migrating to Koji 1.26
======================

You should consider the following changes when migrating to 1.26:

DB Updates
----------

This release includes one schema change.

Channels now can have description and can be enabled/disabled. (Issues `#1711
<https://pagure.io/koji/issue/1711>`_, `#1849 <https://pagure.io/koji/issue/1849>`_
`#1851 <https://pagure.io/koji/issue/1851>`_)


As in previous releases, we provide a migration script that updates the database.

::

    # psql koji koji < /usr/share/doc/koji/docs/schema-upgrade-1.25-1.26.sql


Other changes
-------------

There are numerous other changes in 1.26 that should not have a direct impact on migration. For
details see: :doc:`../release_notes/release_notes_1.26`
