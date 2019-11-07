Koji 1.18.0 Release notes
=========================


Migrating from Koji 1.17
------------------------

For details on migrating see :doc:`../migrations/migrating_to_1.18`



Security Fixes
--------------



Client Changes
--------------

**Add option for custom cert location**

| PR: https://pagure.io/koji/pull-request/1253

The CLI now has an option for setting a custom SSL certificate, similar to the
options for Kerberos authentication.


**Load client plugins from ~/.koji/plugins**

| PR: https://pagure.io/koji/pull-request/892


This change allows users to load their own cli plugins from ``~/.koji/plugins``
or from another location by using the ``plugin_paths`` setting.


**Show load/capacity in list-channels**

| PR: https://pagure.io/koji/pull-request/1449

The ``list-channels`` display has been expanded to show overall totals for load
and capacity.


**Allow taginfo cli to use tag IDs**

| PR: https://pagure.io/koji/pull-request/1476

The ``taginfo`` command can now accept a numeric tag id on the command line.


**Add option to show channels in list-hosts**

| PR: https://pagure.io/koji/pull-request/1425

The ``list-hosts`` command will now display channel subscriptions if the
``--show-channels`` option is given.


**Remove merge option from edit-external-repo**

| PR: https://pagure.io/koji/pull-request/1499

This option was mistakenly added to the command and never did anything.
It is gone now.


**Honor mock.package_manager tag setting in mock-config cli**

| PR: https://pagure.io/koji/pull-request/1374

The ``mock-config`` command will now honor this setting just as ``kojid`` does.




Library Changes
---------------

**New multicall interface**

| PR: https://pagure.io/koji/pull-request/957

This feature implements a new and much better way to use multicall in the Koji
library.
These changes create a new implementation outside of ClientSession.
The old way will still work.

With this new implementation:

* a multicall is tracked as an instance of `MultiCallSession`
* the original session is unaffected
* multiple multicalls can be managed in parallel, if desired
* `MultiCallSession` behaves more or less like a session in multicall mode
* method calls return a `VirtualCall` instance that can later be used to access the result
* `MultiCallSession` can be used as a context manager, ensuring that the calls are executed

Usage examples can be found in the :doc:`Writing Koji Code <../writing_koji_code>`
document.




Web UI Changes
--------------

**Retain old search pattern in web ui**

| PR: https://pagure.io/koji/pull-request/1258

The search results page of the web ui now retains a search form with the
current search pre-filled.
This makes it easier for users to refine their searches.


**Display task durations in webui**

| PR: https://pagure.io/koji/pull-request/1383


The ``taskinfo`` page in the web ui now shows task durations in addition to
timestamps.



Builder Changes
---------------

**Rebuild SRPMS before building**

| PR: https://pagure.io/koji/pull-request/1462

For rpm builds from an uploaded srpm, Koji will now rebuild the srpm in the
build environment first.
This ensures that the NVR is correct for the resulting build.

The old behavior can be requested by setting ``rebuild_srpm=False`` in the tag
extra data for the build tag in question.


**User createrepo_c by default**

| PR: https://pagure.io/koji/pull-request/1278


The ``use_createrepo_c`` configuration option for ``kojid`` now defaults to True.


**Use createrepo update option even for first repo run**

| PR: https://pagure.io/koji/pull-request/1363

If there is no older repo for a tag, Koji will now attempt to find
a related repo to use ``createrepo --update`` with.
This will speed up first-time repo generations for tags that
predominantly inherit their content from another build tag.


**Scale task_avail_delay based on bin rank**

| PR: https://pagure.io/koji/pull-request/1386

This is an adjustment to Koji's decentralized scheduling algorithm.
It should result in better utilization of host capacity, particularly when
a channel has hosts that are very heterogeneous in capacity.

The meaning of the ``task_avail_delay`` setting is different now.
Within a channel-arch bin, the hosts with highest capacity will take the task
immediately, while hosts lower down will have a delay proportional to their
rank.
The "rank" here is a float between 0.0 and 1.0 used as a multiplier.
So ``task_avail_delay`` is the maximum time that any host will wait to
take a task.

Hosts with higher available capacity will be more likely to claim a
task, resulting in better utilization of the highest capacity hosts.


**Use RawConfigParser for kojid**

| PR: https://pagure.io/koji/pull-request/1544

The use of percent signs is common in ``kojid.conf`` because of the
``host_principal_format`` setting.
This causes an error in python3 if ``SafeConfigParser`` is used, so we use
``RawConfigParser`` instead.


**Handle bare merge mode**

| PR: https://pagure.io/koji/pull-request/1411
| PR: https://pagure.io/koji/pull-request/1516
| PR: https://pagure.io/koji/pull-request/1502


This feature adds a new merge mode for external repos named ``bare``.
This mode is intended for use with modularity.

Use of this mode requires createrepo_c version 0.14.0 or later on the builders
that handle the createrepo tasks.




System Changes
--------------


**API for reserving NVRs for content generators**

| PR: https://pagure.io/koji/pull-request/1464
| PR: https://pagure.io/koji/pull-request/1597
| PR: https://pagure.io/koji/pull-request/1601
| PR: https://pagure.io/koji/pull-request/1602
| PR: https://pagure.io/koji/pull-request/1606

This feature allows content generators to reserve NVRs earlier in the build
process similar to builds performed by ``kojid``. The NVR is reserved by
calling ``CGInitBuild()`` and finalized by the ``CGImport()`` call.



**Per-tag configuration of rpm macros**

| PR: https://pagure.io/koji/pull-request/898

This feature allows setting rpm macros via the tag extra field. These macros
will be added to the mock configuration for the buildroot. The system
looks for extra values of the form ``rpm.macro.NAME``.

For example, to set the dist tag for a given tag, you could use a command like:

::

    $ koji edit-tag f30-build -x rpm.macro.dist=MYDISTTAG



**Per-tag configuration for module_hotfixes setting**

| PR: https://pagure.io/koji/pull-request/1524
| PR: https://pagure.io/koji/pull-request/1578

Koji now handles the field ``mock.yum.module_hotfixes`` in the tag extra.
When set, kojid will set ``module_hotfixes=0/1`` in the yum portion of the
mock configuration for a buildroot.


**Allow users to opt out of notifications**

| PR: https://pagure.io/koji/pull-request/1417
| PR: https://pagure.io/koji/pull-request/1580

This feature lets users opt out of notifications that they would otherwise
automatically recieve, such as build and tag notifications for:

- the build owner (the user who submitted the build)
- the package owner within the given tag

These opt-outs are user controlled and can be managed with the new
``block-notification`` and ``unblock-notificiation`` commands.


**Allow hub policy to match version and release**

| PR: https://pagure.io/koji/pull-request/1513


This feature adds new policy tests to match ``version`` and ``release``.
This tests are glob pattern matches.


**Allow hub policy to match build type**

| PR: https://pagure.io/koji/pull-request/1415


Koji added btypes in version 1.11 along with content generators.
Now, all builds have one or more btypes.

This change allows policies to check the btype value using the ``buildtype`` test.



**More granular admin permissions**

| PR: https://pagure.io/koji/pull-request/1454

A number of actions that were previously admin-only are now governed by
separate permissions:

    ``host``
        This permission governs most host management operations, such as
        adding, editing, enabling/disabling, and restarting.

    ``tag``
        This permission governs adding, editing, and deleting tags.

    ``target``
        This permission governs adding, editing, and deleting targets.

Koji administrators may want to consider reducing the number of users with
full ``admin`` permission.


**Option to generate separate source repo**

| PR: https://pagure.io/koji/pull-request/1273

The (non-dist) yum repos that Koji generates for building normally don't
include srpms.
An old option allowed them to be included in some cases, but they were simply
added to each repo.
Newer options have been added that instruct Koji to include them as a separate
src repo.

In the cli, the ``regen-repo`` command now accepts a ``--separate-source``
option that triggers this behavior.

In ``kojira``, the ``separate_source_tags`` option is a list of tag patterns.
Build tags that match any of these patterns will have their repos generated
with a separate src repo.



**Add volume option for dist-repo**

| PR: https://pagure.io/koji/pull-request/1327

Dist repos can now be generated on volumes other than the main one.
Use the ``--volume`` option to the ``dist-repo`` command to do so.

Generally you want the repo to be on the same volume as the rpms it will
contain.
Dist repos hard link (same volume) or copy (different volume) their rpms into
place.
Using the appropriate volume can drastically improve the efficiency, both in
generation time and space consumption.


**Minor gc optimizations**

| PR: https://pagure.io/koji/pull-request/1337
| PR: https://pagure.io/koji/pull-request/1442
| PR: https://pagure.io/koji/pull-request/1437

This change speeds up portions of garbage collection by making the
``build_references`` check lazy by default.



**Rollback errors in multiCall**

| PR: https://pagure.io/koji/pull-request/1358

If one of the calls in a multicall raises an error, then the transaction will
be rolled back to the start of that call before Koji proceeds to the next call.
This matches the behavior of normal calls more closely.

Multicalls are still handled within single database transaction.



**Support tilde in search**

| PR: https://pagure.io/koji/pull-request/1297


The tilde character is no longer prohibited in search terms.



**Remove 'keepalive' option**

| PR: https://pagure.io/koji/pull-request/1277

The ``keepalive`` setting is no longer used anywhere in koji.
It has been removed.
