Koji 1.24.0 Release notes
=========================

All changes can be found at `pagure <https://pagure.io/koji/roadmap/1.24/>`_.
Most important changes are listed here.


Migrating from Koji 1.23/1.23.1
-------------------------------

For details on migrating see :doc:`../migrations/migrating_to_1.24`


Security Fixes
--------------

None


Client Changes
--------------

**support download-build \-\-type=remote-sources**

| PR: https://pagure.io/koji/pull-request/2608

This wasn't possible via CLI before. The command has been extended for
downloading this additional artifact type.

**hide import-sig \-\-write option**

| PR: https://pagure.io/koji/pull-request/2654

This option is not used anymore. We're hiding it from the user.

**return error if add/remove-tag-inheritance can't be applied**

Previously only a warning was printed but return code implied no problems. Now
it is returning an error-code so it has better problem visibility in scripts.

| PR: https://pagure.io/koji/pull-request/2605

**raise NotImplementedError with btype name**

| PR: https://pagure.io/koji/pull-request/2610

More verbose error when downloading unsupported archives.

**list-tasks \-\-after/\-\-before/\-\-all**

| PR: https://pagure.io/koji/pull-request/2566

New options for list-tasks. Formerly only running tasks could be
displayed. Now closed tasks can also be displayed with ``--all`` and
``--after``/``--before`` options. Use it wisely -- querying all tasks
can hurt the hub's performance.

**list-hosts can display description/comment**

| PR: https://pagure.io/koji/pull-request/2562

The new ``--comment`` and ``--description`` options can be used to display
additional info in host list.

**allow removal of unused external repo even with \-\-alltags**

| PR: https://pagure.io/koji/pull-request/2560

Fixed confusing behaviour for ``koji remove-external-repo --alltags``
when the given external repo is not associated with any tags.

**history query by extra key**

| PR: https://pagure.io/koji/pull-request/2589

The additional filter option ``--xkey`` for list-history limits the results to
history records that affected the given extra key for some tag.


Library Changes
---------------
**better print with debug_xmlrpc**

| PR: https://pagure.io/koji/pull-request/2598

This fixes an unfortunate display bug introduced by the python3 migration.
The ``--debug-xmlrpc`` feature shows details of the xmlrpc calls to the hub,
but most of the data was shown base64-encoded, regardless of whether it was
printable. Now the client will only result to base64 when it is necessary.

API Changes
-----------
**readFullInheritance stops/jumps deprecation**

| PR: https://pagure.io/koji/pull-request/2655

Deprecation of unused options.

**fix nightly getNextRelease format**

| PR: https://pagure.io/koji/pull-request/2630

Additional format allowed for ``getNextRelease`` - ``{str}.{str}.{id}``.

**[listBuilds] add nvr glob pattern support**

| PR: https://pagure.io/koji/pull-request/2555

The ``list-builds`` command now accepts a ``--pattern`` option that
filters the NVRs using the given glob pattern.

The underlying ``listBuilds`` api call on the hub now accepts a ``pattern``
argument that applies the filtration.

Builder Changes
---------------
**Add option to use repos from kickstart for livemedia builds**

| PR: https://pagure.io/koji/pull-request/2571

The new ``--ksrepo`` option tells the builder to not override the repos
given in the kickstart files for livemedia builds.

**Add nomacboot option for spin-livemedia**

| PR: https://pagure.io/koji/pull-request/2540

The new ``--nomacboot`` option is passed through to livemedia-creator.

System Changes
--------------

**make policy test thread safe**

| PR: https://pagure.io/koji/pull-request/2651


**spec: pythonic provides**

| PR: https://pagure.io/koji/pull-request/2667

Spec file now provides python3dist(koji) provides.

**requires python[23]-requests-gssapi for rhel[78]**

| PR: https://pagure.io/koji/pull-request/2664

**explicit encoding for text file operations**

| PR: https://pagure.io/koji/pull-request/2647

In some mod_wsgi configurations, the hub can raise an error because of non-default
encoding when opening text files. The code has been modified to force UTF-8
everywhere.

**Lower default multicall batch values**

| PR: https://pagure.io/koji/pull-request/2644

In high-load environments long-running transactions can lead even to db
deadlocks. We suggest using lower batches for multicalls and have lowered the
default batch sizes we currently have in the code.

If individual multicalls are running longer than a minute or two, we recommend
splitting them into smaller batches.

**require gssapi-requests 1.22**

| PR: https://pagure.io/koji/pull-request/2584

Older versions of library have a bug which breaks the gsaapi login for builders.
Upgrading to this version solves the problem.

**limit CGImport to allow only one CG per import**

| PR: https://pagure.io/koji/pull-request/2574

We've found that nobody is using the option to include multiple CGs output in
one CG import. It makes things easier if we limit it directly to one CG per
import. In such case we know which CG generated which build and policies can
work with this value, etc.

**external repos can have specified arch list**

| PR: https://pagure.io/koji/pull-request/2564
| PR: https://pagure.io/koji/pull-request/2682

Some external repositories can have split architectures (e.g. primary
architectures in one repo and secondary in the second). On the other hand tags
expect that external repo has all the architectures as the tag has.
We've added a new option to tell Koji that an external repo only contains a
subset of tag's architectures.
Multiple external repos with different architectures can then be attached to the
tag. This behaviour can be tuned by ``--arches`` option in ``add-external-repo``
and ``edit-external-repo`` commands.

**remove deprecated \-\-ca option**

| PR: https://pagure.io/koji/pull-request/2529

Formerly deprecated ``--ca`` option is finally removed for all executables.

Web
---

**return correct content-length**

| PR: https://pagure.io/koji/pull-request/2639

Regressions for py3 code - ``Content-Length`` header was erroneously computed so
some browsers fetched incomplete page. It is not visible in most cases (as final
html tags are corrupted and added by the browser) but in some cases it could
led to broken web page.

**order methods by name in select box**

| PR: https://pagure.io/koji/pull-request/2559

With growing number of task types it makes more sense to order them
alphabetically these days compared to previous *importance* ordering.

**more accessible task colors/icons**

| PR: https://pagure.io/koji/pull-request/2653

For higher accessibility we've slightly changed the colors corresponding to task and
build states. We've also added more informative icons to the taskinfo page.

**display VCS/DistURL rpm tags**

| PR: https://pagure.io/koji/pull-request/2683

The buildinfo and rpminfo pages now display also VCS and DistURL tags if they are
present in rpm (srpm for buildinfo page).

Plugins
-------
**handle plugins and generator results in count and countAndFilterResults**

| PR: https://pagure.io/koji/pull-request/2633

These functions couldn't be used for methods provided by plugins or
methods which returned generators. This is now fixed.

**plugin hooks for repo modification**

| PR: https://pagure.io/koji/pull-request/2637

New ``postCreateRepo`` and ``postCreateDistRepo`` plugin hooks were introduced
on builder. They can be used to modify repodata with intent to allow sign the
repodata by plugins but it can be used for additional repodata modification.

Utilities
---------

Kojira
......

**move checkTasks near its usage**

| PR: https://pagure.io/koji/pull-request/2140

We've moved checking running ``newRepo`` tasks to different place. Now, the number
of running tasks should be closer to set capacity as kojira will check
finished tasks just before spawning new ones.

Documentation
-------------
**mention the final destination for new dist-repos**

| PR: https://pagure.io/koji/pull-request/2621

**link to tag2distrepo hub plugin**

| PR: https://pagure.io/koji/pull-request/2617

**types param for content generators**

| PR: https://pagure.io/koji/pull-request/2609

**remove global SSLVerifyClient option**

| PR: https://pagure.io/koji/pull-request/2627

