Koji 1.23.0 Release notes
=========================

All changes can be found at `pagure <https://pagure.io/koji/roadmap/1.23/>`_.
Most important changes are listed here.


Migrating from Koji 1.22/1.22.1
-------------------------------

For details on migrating see :doc:`../migrations/migrating_to_1.23`


Security Fixes
--------------

None


Client Changes
--------------

**cli: clone-tag fails on failed multicalls**

| PR: https://pagure.io/koji/pull-request/2464

Previously some errors could have been hidden which could have led to missing
content in target tag. Now we are failing on any error.

**improved download_file**

| PR: https://pagure.io/koji/pull-request/2395
| PR: https://pagure.io/koji/pull-request/2461
| PR: https://pagure.io/koji/pull-request/2471

In the last version we've introduced unified ``download_file`` method which also
checks downloaded content. There are minor updates improving this function
especially in reaction to errors.

**cli: add --task and --source options to list-builds command**

| PR: https://pagure.io/koji/pull-request/2458

Builds now can be queried via ``task`` or ``source`` fields.

**show log urls for failed tasks**

| PR: https://pagure.io/koji/pull-request/2505

When watching for task progress, failed tasks will also display links to
relevant logs.

**load plugins also from /usr/lib64**

| PR: https://pagure.io/koji/pull-request/2525

Fix of the bug which missed plugins in /usr/lib64 prefix.

**clone-tag --config clones also extra info**

| PR: https://pagure.io/koji/pull-request/2472

Formerly cloning skipped extra values. Nevertheless, extra values are becoming
important part of config, so from now we are cloning also those.

Library Changes
---------------

**getRPMHeaders now fetch all headers by default**

| PR: https://pagure.io/koji/pull-request/2388

Simple change of library function default behaviour.

API Changes
-----------

**lowercase sigkeys during import/query where needed**

| PR: https://pagure.io/koji/pull-request/2459

Case of signature hashes is properly ignored.

**tagChangedSince reacts on changes in extra**

| PR: https://pagure.io/koji/pull-request/2439

It is probably mostly used by kojira, but it can be of some interest to
automation scripts.

**getAverageBuildDuration sliding window**

| PR: https://pagure.io/koji/pull-request/2421

``getAverageBuildDuration`` returned average for all package builds. Old data
could be irrelevant to new version of packages, so age in months can now be
specified to limit data from which average is computed.

**getBuildConfig returns inheritance history**

| PR: https://pagure.io/koji/pull-request/2493

Additional option return inheritance chain for extra values and architectures.
This behaviour is meant to be used with next change.

**blocking inherited extra**

| PR: https://pagure.io/koji/pull-request/2495

Inherited tag extra fields could have been overriden but not removed. Now it can
be done via CLIs ``edit-tag`` or ``editTag2`` respectively which has new
``block_extra`` option.

**deprecate getGlobalInheritance**

| PR: https://pagure.io/koji/pull-request/2407

It should be replaced by ``readFullInheritance`` which is more general and
properly reflects various inheritance options. Call will be completely removed
in koji 1.25.

**remove deprecated list-tag-history / tagHistory**

| PR: https://pagure.io/koji/pull-request/2405

Final removal.

**Remove deprecated host.getTask call**

| PR: https://pagure.io/koji/pull-request/2406

Final removal.


Builder Changes
---------------

**builder: configurable TTL for buildroots**

| PR: https://pagure.io/koji/pull-request/2485

Buildroots were cleaned from builder after hard-coded amount of time. Basic
cleanup was done after two minutes and completely removed after a day. Now both
options are configurable as ``buildroot_basic_cleanup_delay`` and
``buildroot_final_cleanup_delay``.

**livemedia-creator: pass --nomacboot on non-x86_64**

| PR: https://pagure.io/koji/pull-request/2373

Additional option was needed for booting on non-x86_64 archs.

**builder: handle btrfs subvolumes in ApplianceTask**

| PR: https://pagure.io/koji/pull-request/2365

BTRFS needed special handling in ``ApplianceTask`` to work.

**kojid: fix extra-boot-args option**

| PR: https://pagure.io/koji/pull-request/2452

Bug which prevented proper usage of ``bootloader --append`` in kickstarts.

**kojid: waitrepo on deleted tag**

| PR: https://pagure.io/koji/pull-request/2417

If tag was deleted during ``waitrepo`` task, it waited until long timeout. Now
it can fail immediately.

System Changes
--------------

**dropping python 2.6 / RHEL6 / yum support**

| PR: https://pagure.io/koji/pull-request/2490

One of the most important changes is dropping support for older python. We still
support python 2.7 for builder (other components are python 3 only). It
effectively means ending support for RHEL/CentOS 6 builders. In the same moment
we are dropping yum support (it was used only with dist-repos) as RHEL7 and
newer have full dnf stack.

**report versions of components**

| PR: https://pagure.io/koji/pull-request/2438

There is a new API call ``getVersion`` (don't confuse with ``getAPIVersion``)
which returns version of hub being connected to. Similarly, basic library
provides ``koji.__version__`` field.

Plugins
-------

**proton: persistent message queue**

| PR: https://pagure.io/koji/pull-request/2441

As qpid (or other amqps broker) can be unreachable for longer periods of time
we've implemented local db queue, so no messages are lost. This behaviour needs
to be turned on - check the documentation.

Utilities Changes
-----------------

Kojira
......

**parallel rmtree**

| PR: https://pagure.io/koji/pull-request/2443

Deleting old repos is now done in parallel.


Documentation
-------------

**PostgreSQL requirements for partitioning**

| PR: https://pagure.io/koji/pull-request/2508


**release process**

| PR: https://pagure.io/koji/pull-request/2462


**more info about permission system**

| PR: https://pagure.io/koji/pull-request/2415


**setting rpm macros for build tags**

| PR: https://pagure.io/koji/pull-request/2410

**livecd/livemedia updates**

| PR: https://pagure.io/koji/pull-request/2500
