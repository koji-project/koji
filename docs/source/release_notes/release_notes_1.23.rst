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

In the previous version we introduced unified ``download_file`` method which also
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

**clone-tag --config also clones extra info**

| PR: https://pagure.io/koji/pull-request/2472

Formerly cloning skipped extra values. Nevertheless, extra values are becoming
an important part of config, so from now we are cloning them.

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

Because of this, kojira will now correctly regenerate repos when tag extra
values change.

**getAverageBuildDuration sliding window**

| PR: https://pagure.io/koji/pull-request/2421

The ``getAverageBuildDuration`` hub call returned an average for all builds for
the given package.
However, old data could be irrelevant to new versions of packages.
Now the call offers an ``age`` option to limit the query (specified as number
of months).

The koji builder daemon now uses this option with a value of 6 months when
adjusting the weight of ``buildArch`` tasks.

**getBuildConfig returns inheritance history**

| PR: https://pagure.io/koji/pull-request/2493

Additional option return inheritance chain for extra values and architectures.
This behaviour is meant to be used with next change.

**blocking inherited extra**

| PR: https://pagure.io/koji/pull-request/2495

Inherited tag extra fields could have been overridden but not removed. Now it can
be done via CLIs ``edit-tag`` or ``editTag2`` respectively which has a new
``block_extra`` option.

**deprecate getGlobalInheritance**

| PR: https://pagure.io/koji/pull-request/2407

This call was never used in Koji.
Clients should instead use the ``readFullInheritance`` call.
The ``getGlobalInheritance`` call will be completely removed in Koji 1.25.

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

Previously these times were hard coded.
The ``buildroot_basic_cleanup_delay`` setting controls how long the builder will
wait before basic cleanup of the buildroot (removing most content but leaving
the directory). The default value is two minutes.
The ``buildroot_final_cleanup_delay`` setting controls how long the build will
wait before final cleanup of the buildroot (removing the rest).
The default value is one day.
Both values are specified in seconds.

For historical context on why there are two separate delays, see
`this bug <https://bugzilla.redhat.com/show_bug.cgi?id=192153>`.

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

Previously, if a tag was deleted while a ``waitrepo`` task was watching it, the
task would not notice and wait until the timeout expired.
Now it will fail when it detects that the tag has been deleted.

System Changes
--------------

**dropping python 2.6 / RHEL6 / yum support**

| PR: https://pagure.io/koji/pull-request/2490


One of the most significant changes in this release is dropping support for
older python versions.
Koji no longer supports python 2.6, and only supports python 2.7 for the
builder and cli.

This effectively means ending support for RHEL/CentOS 6 builders.
We are dropping yum support (it was used only with dist-repos) as RHEL7 and
newer have full dnf stack.

**report versions of components**

| PR: https://pagure.io/koji/pull-request/2438

There is a new hub API call named ``getVersion`` (don't confuse with
``getAPIVersion``) which returns the version of Koji that the hub is running.
Similarly, the ``koji`` library provides its version in ``koji.__version__``.

Plugins
-------

**proton: persistent message queue**

| PR: https://pagure.io/koji/pull-request/2441

As qpid (or other amqps broker) can be unreachable for long periods of time
we've implemented a fallback queue in the database to avoid lost messages.
This behaviour needs to be enabled - see
:ref:`the documentation <protonmsg-config>`.

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
