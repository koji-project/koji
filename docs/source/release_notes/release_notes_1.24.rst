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

**support download-build --type=remote-sources**

| PR: https://pagure.io/koji/pull-request/2608

This wasn't possible via CLI before. Extensions for downloading additional artifact type.

**hide import-sig --write option**

| PR: https://pagure.io/koji/pull-request/2654

Option is not used anymore. We're hiding it from the user.

**return error if add/remove-tag-inheritance can't be applied**

Previously only a warning was printed but return code implied no problems. Now
it is returning an error-code so it has better problem visibility in scripts.

| PR: https://pagure.io/koji/pull-request/2605

**raise NotImplementedError with btype name**

| PR: https://pagure.io/koji/pull-request/2610

More verbose error when downloading unsupported archives.

**list-tasks --after/--before/--all**

| PR: https://pagure.io/koji/pull-request/2566

New options for list-tasks. Formerly only running tasks could have been
displayed. Now also closed tasks can be displayed with ``--all`` and
``--after``/``--before`` options. Anyway, use it wisely - returning all tasks
can hurt the hub's performance.

**list-hosts can display description/comment**

| PR: https://pagure.io/koji/pull-request/2562

``--comment`` and ``--description`` options could be used to display additional
info in listing command. They are not enabled by default.

**allow removal of unused external repo even with --alltags**

| PR: https://pagure.io/koji/pull-request/2560

Fixed confusing behaviour when if ``--altags`` was used when removing external
repo repo itself wasn't deleted.

**history query by key**

| PR: https://pagure.io/koji/pull-request/2589

Additional filter option ``--xkey`` for list-history limiting history records
only for given extra key.


Library Changes
---------------
**better print with debug_xmlrpc**

| PR: https://pagure.io/koji/pull-request/2598

Fix of py3 migration regression. Even printable data were base64-encoded. If it
is a printable unicode string it is printed directly as in py2 version.

API Changes
-----------
**readFullInheritance stops/jumps deprecation**

| PR: https://pagure.io/koji/pull-request/2655

Deprecation of unused options.

**backward compatible hub call**

| PR: https://pagure.io/koji/pull-request/2649

**fix nightly getNextRelease format**

| PR: https://pagure.io/koji/pull-request/2630

Additional format allowed for ``getNextRelease`` - ``{str}.{str}.{id}``.

**[listBuilds] add nvr glob pattern support**

| PR: https://pagure.io/koji/pull-request/2555

``listBuilds`` now can have ``pattern`` glob option which is used in same way
like in ``search`` call.

Builder Changes
---------------
**Add option to use repos from kickstart for livemedia builds**

| PR: https://pagure.io/koji/pull-request/2571

``--ksrepo`` option for livemedia task. If specified, repos in kickstart are not
overriden by koji.

**Add nomacboot option for spin-livemedia**

| PR: https://pagure.io/koji/pull-request/2540

``--nomacboot`` option could be passed to livemedia-creator.

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

In some mod_wsgi configuration hub can raise error because of non-default
encoding usage when opening text files. This was now unified to force UTF-8
everywhere.

**Lower default multicall batch values**

| PR: https://pagure.io/koji/pull-request/2644

In high-load environments long-running transactions can lead even to db
deadlocks. We suggest to use lower batches for multicalls and lowered all
default we currently have in the code. Rule of thumb is that everything running
longer than two minutes should be split into smaller batches. Anyway, you'll
always need to think about transaction consistency in the particular usecase.

**require gssapi-requests 1.22**

| PR: https://pagure.io/koji/pull-request/2584

Older versions of library have a bug which break the gsaapi login for builders.
Upgrading to this versions solves the problem.

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
expect that external repo has all the architectures as the tag has. New option
can define that external repo contain only subset of tag's architectures.
Multiple external repos with different architectures can then be attached to the
tag. This behaviour can be tuned by ``--arches`` option in ``add-external-repo``
and ``edit-external-repo`` commands.

**remove deprecated --ca option**

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

For higher accessibilit we've changed a bit colors corresponding to task and
build states. We've also added more informative icons to taskinfo page.

**display VCS/DistURL rpm tags**

| PR: https://pagure.io/koji/pull-request/2683

Buildinfo and rpminfo pages now display also VCS and DistURL tags if they are
present in rpm (srpm for buildinfo page).

Plugins
-------
**handle plugins and generator results in count and countAndFilterResults**

| PR: https://pagure.io/koji/pull-request/2633

These functions couldn't have been used for methods provided by plugins and
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

We've moved checking running ``newRepo`` tasks to different place. Now, number
of running tasks should be more close to set capacity as kojira will check
finished tasks just before spawning new ones, so estimation should be better.

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

