Migrating to Koji 1.35
======================

You should consider the following changes when migrating to 1.35:

DB Updates
----------

Changes for new repo handling introduced a few new tables.

As in previous releases, we provide a migration script that updates the database.

::

    # psql koji koji < /usr/share/doc/koji/docs/schema-upgrade-1.34-1.35.sql


Repo Generation
---------------

The way that Koji handles repo generation has changed significantly.
For full details, please see the release notes and :doc:`../repo_generation`.

The following kojira configuration options are no longer used and have no analog
in the new system:

* ``queue_file``
* ``ignore_tags``
* ``no_repo_effective_age``
* ``repo_tasks_limit``

We recommend you remove these settings from ``kojira.conf``.
Kojira will warn at startup if they are present.

Additionally, these kojira configuration options have moved into the hub config:

* ``max_repo_tasks`` -> ``MaxRepoTasks``
* ``max_repo_tasks_maven`` -> ``MaxRepoTasksMaven``
* ``debuginfo_tags`` -> ``DebuginfoTags``
* ``source_tags`` -> ``SourceTags``
* ``separate_source_tags`` -> ``SeparateSourceTags``

Admins that relied on these kojira options should now set the corresponding hub options and remove
the old kojira ones.
For the latter three, note that there are now other ways to control these repo options.

Finally, if you have systems outside of Koji that rely on Koji keeping particular tag repos up to
date, you may need to take extra steps to ensure regeneration.
If the tag sees regular build use within Koji, then that might trigger regens often enough.
If not, there are two options:

* set ``repo.auto=True`` for the tag in question
* have the external system create a repo request via the api

Again, for full details, please see the release notes and :doc:`../repo_generation`.


Other changes
-------------

There are numerous other changes in 1.35 that should not have a direct impact
on migration. For details see: :doc:`../release_notes/release_notes_1.35`
