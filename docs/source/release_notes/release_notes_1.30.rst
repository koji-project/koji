
Koji 1.30.0 Release notes
=========================

All changes can be found in `the roadmap <https://pagure.io/koji/roadmap/1.30/>`_.
Most important changes are listed here.


Migrating from Koji 1.29/1.29.1
-------------------------------

For details on migrating see :doc:`../migrations/migrating_to_1.30`


Security Fixes
--------------

None

Client Changes
--------------
**Remove --paths option from list-buildroot**

| PR: https://pagure.io/koji/pull-request/3352

This option was not used and was deprecated. Now it was removed.

**list-channels with specific arch**

| PR: https://pagure.io/koji/pull-request/3363

New filtering ``--arch`` option.

**download-task retry download file**

| PR: https://pagure.io/koji/pull-request/3385

Additional place where we retry download in case of temporary network issues.

**Add a utility function to watch builds**

| PR: https://pagure.io/koji/pull-request/3406

For CLI plugin development we've separated ``wait_repo`` function to library.

**Rewritten download-task**

| PR: https://pagure.io/koji/pull-request/3425
| PR: https://pagure.io/koji/pull-request/3430
| PR: https://pagure.io/koji/pull-request/3438
| PR: https://pagure.io/koji/pull-request/3459
| PR: https://pagure.io/koji/pull-request/3462

``download-task`` command was rewritten to solve some long-standing issues. E.g.
downloading image scratch builds or some conflicting files. Command should be
backward-compatible but allows additional options like ``--dir-per-arch`` and
additional filtering.

API Changes
-----------
**Remove force option from groupPackageListRemove hub call**

| PR: https://pagure.io/koji/pull-request/3354

Deprecated unused option was finally removed.

**Remove deprecated remove-channel/removeChannel**

| PR: https://pagure.io/koji/pull-request/3357

Same here - same functionality is available via ``disable-channel/editChannel``.

**Use compression_type in addArchiveType**

| PR: https://pagure.io/koji/pull-request/3391

Archive files had available listing for some specific extensions (zip, tar).
Other archives couldn't been displayed even if they had the same compression
format (e.g. jar which is hidden zip). Explicitly specifying compression type
via ``addArchiveType`` allows also these other types to be inspected.

Library Changes
---------------
**Fix rpm_hdr_size file closing**

| PR: https://pagure.io/koji/pull-request/3423

Simple fix for potential file descriptor leak in user scripts.

**Authtype as enum and getSessionInfo prints authtype name**

| PR: https://pagure.io/koji/pull-request/3437

``koji.AUTHTYPE_*`` were converted to enum like other ``koji.*`` constants. It
unifies the usage + prints human-readable strings instead of numeric IDs.

**parse_arches allows string and list of arches**

| PR: https://pagure.io/koji/pull-request/3440

Utility conversion function now accepts more types than before.

System Changes
--------------
**Server-side clonetag**

| PR: https://pagure.io/koji/pull-request/3308

Major rehaul of ``clone-tag`` command. It was completely removed from CLI-side
and everything happens at hub now. It is immensely faster in real workload (for
big tags from hours to seconds). Nevertheless, we've lost some functionality -
typically verbose mode is no more possible as everything happens in one
transaction now, so there is almost no text output. We believe it is worth the
speed improvements. There are also very minor semantical changes (e.g. event ids
for separate steps) which shouldn't be noticed by vast majority of users.

If target tag doesn't exist, things are even more faster as we don't need to
check what is there, etc.

New API calls related to this behaviour are now available: ``massTag``, ``snapshotTag``,
``snapshotTagModify``. Especially ``massTag`` could be used by many admins as it
is basically batch call of ``tagBuildBypass`` ('tag' permission needed) dropping
need of ``tagBuildBypass`` multicall overhead.

Note, that this is breaking change. If you use new client with older hub, you'll
not be able to run clone-tag command at all. In such a case we would recommend
temporarily using older client (1.29.1 - e.g. installed via pip if it is not
available as rpm)

**Drop old indices**

| PR: https://pagure.io/koji/pull-request/3359

Few unused old indices could still exists in some deployments. Migration script
will drop them.

**Correct getAverageDuration values for most GC builds**

| PR: https://pagure.io/koji/pull-request/3402
| PR: https://pagure.io/koji/pull-request/3457

``getAverageDuration`` was not making much sense for packages which had also
imported content. Now we ignore zero times for imported content getting better
estimation of real koji builds.

**Consistence pre/postPackageListChange sequence**

| PR: https://pagure.io/koji/pull-request/3403

If ``packageListAdd`` ended with no action because package is already in the
list, only ``prePackageListChange`` callback was run. In such case no callback
should be run.

**Check release/version format in cg_import**

| PR: https://pagure.io/koji/pull-request/3422

Failed builds could have had non-sense in release/version. It was never true for
completed builds as koji wouldn't allow such build to finish. Anyway, it was
confusing to see such items in failed builds list, so we've denied it from the
beginning.

**Expect dict for chainmaven builds**

| PR: https://pagure.io/koji/pull-request/3444

Regression fix for ``chainMaven`` API call which was refusing correct input from
1.29.

Builder Changes
---------------
**Catch koji.AuthError and bail out**

| PR: https://pagure.io/koji/pull-request/3364

kojid and kojira now fail on authentication errors and don't try forever.
Anyway, daemons will be restarted via systemd (possibly loading updated
certificates, keytabs, ...) so it could help in some situations.

**Don't propagate SIGHUP ignore to child processes**

| PR: https://pagure.io/koji/pull-request/3404

Some packages are testing SIGHUP behaviour (e.g. cpython) in their test suite.
Previously we've been blocking SIGHUP in child processes (mock), so it needed
some care from packagers. There is no need to do that, so we've dropped this
behaviour.

**Beautify logged commands issued by koji**

| PR: https://pagure.io/koji/pull-request/3405

In few cases (e.g. createrepo) koji logs very long command lines. They are now
wrapped to 80 characters for easier log reading.

**Don't crash in _checkImageState if there's no image.os_plugin**

| PR: https://pagure.io/koji/pull-request/3445

In some cases ImageFactory tried to tear down the VM even in case there wasn't
right code/plugin for that.

Web Changes
-----------
**archivelist and rpmlist raise error when imageID is unknown**

| PR: https://pagure.io/koji/pull-request/3382

Don't crash on non-existing IDs.

**Set SameSite and Set-Cookie2**

| PR: https://pagure.io/koji/pull-request/3390

We've added these http headers to increase the security.

**Convert data to string in escapeHTML first**

| PR: https://pagure.io/koji/pull-request/3450

Better rendering of some non-textual (int, datetime) values.

Plugin Changes
--------------
**proton: save messages when connection fails**

| PR: https://pagure.io/koji/pull-request/3360

Further improvement of handling message bus issues. Some types of errors were
not treated as a connection problem (DNS resolution) thus losing messages.

**kiwi: fix arches check**

| PR: https://pagure.io/koji/pull-request/3428

Regression fix.

Documentation
-------------
**Increase unit tests**

| PR: https://pagure.io/koji/pull-request/3380
| PR: https://pagure.io/koji/pull-request/3383

