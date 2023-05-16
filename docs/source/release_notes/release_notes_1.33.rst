
Koji 1.32.0 Release notes
=========================

All changes can be found in `the roadmap <https://pagure.io/koji/roadmap/1.32/>`_.
Most important changes are listed here.

Migrating from Koji 1.31/1.31.1
-------------------------------

For details on migrating see :doc:`../migrations/migrating_to_1.32`

Security Fixes
--------------

None

Client Changes
--------------
**Let "--principal=" works for users using multiple TGT's**

| PR: https://pagure.io/koji/pull-request/3686

CLI now allows specifying ``--principal`` even if keytab is not used for
authentication.

**Add repoID in listBuildroots and create repoinfo command**

| PR: https://pagure.io/koji/pull-request/3707

New ``repoinfo`` command is available which will display information previously
available only via combination of API calls.

**Add component/built archives in list-buildroot**

| PR: https://pagure.io/koji/pull-request/3769

Only RPMs were dislayed before while web UI listed also additional types. This
is now on par.

**list-tagged: Only check for build dir when --sigs is given**

| PR: https://pagure.io/koji/pull-request/3720

With ``--paths`` and without ``--sigs`` it should be possible to list paths
even without real access to koji storage.

**download-build: Preserve build artefacts last modification time**

| PR: https://pagure.io/koji/pull-request/3712
| PR: https://pagure.io/koji/pull-request/3727

When files are downloaded mtime is set to corresponding mtime on koji storage.

**Cancel error msg**

| PR: https://pagure.io/koji/pull-request/3716
| PR: https://pagure.io/koji/pull-request/3746

More informative messages when ``cancel`` is used. E.g. when it is called
against non-existent build it will raise an error instead of just returning
``False``.

API Changes
-----------
**tagNotification: user_id is int when get_user is used**

| PR: https://pagure.io/koji/pull-request/3780

``tagNotification`` now uses "nicer" variant when it passes only ``user_id``
instead of full userinfo dictionary.

**Remove Host.getTask method**

| PR: https://pagure.io/koji/pull-request/3784

Final removal of deprecated and unused builder-only method.

System Changes
--------------
**Only pad header lengths for signature headers**

| PR: https://pagure.io/koji/pull-request/3690

In some cases incorrect signature header lengths were reported. There is no
impact on koji functions but anyone using the library could have seen these
distorted values.

**Avoid noisy chained tracebacks when converting Faults**

| PR: https://pagure.io/koji/pull-request/3800

Python 3 added chained tracebacks which can be really noisy. We're now
displaying just relevant part.

**createTag raises error when perm ID isn't exists**

| PR: https://pagure.io/koji/pull-request/3803

Postgres error replaced with more standard koji exception.

**Add renewal session timeout**

| PR: https://pagure.io/koji/pull-request/3760

It is a followup of behaviour added in previous release. Sessions could expire
if they exist too long. Anyway, first patch implemented the behaviour itself,
now we're adding also hub option ``SessionRenewalTimeout``. After this timeout
session holder needs to reauthenticate (0 could be set for disabling this).

**Unify behavior when result is empty in get_maven/image/win/build**

| PR: https://pagure.io/koji/pull-request/3754

Error is raised in all cases now.

**RawHeader improvements**

| PR: https://pagure.io/koji/pull-request/3703

For users of koji library there are some more improvements to ``RawHeader``
which can now e.g. display signature headers better.

**Build image from uploaded kickstart**

| PR: https://pagure.io/koji/pull-request/3729

Previously, only scratch builds were allowed to be built from local kickstarts.
Anyway, as this file is stored in the build, it is safe to do it also for
non-scratch content. As a side-effect ``build_rpm`` policy is now consulted for
image builds.

**Add more logging to rmtree**

| PR: https://pagure.io/koji/pull-request/3756

Additional logging was added to library function to better debug garbage
collector issues.

**New scheduler work**

| PR: https://pagure.io/koji/pull-request/3678
| PR: https://pagure.io/koji/pull-request/3819
| PR: https://pagure.io/koji/pull-request/3820

During next release or two we're bringing first phase of new scheduler (moving
scheduling logic from builders to hub). Some support functions can be already
merged.

 * ``db/auth.py`` was moved to kojihub module as it is hub only code.
 * We're now tracking builder update time in host table
 * ``db_lock()`` "silent" nowait locking to not flood hub logs

Kojira
------
**Prioritize awaited repos**

| PR: https://pagure.io/koji/pull-request/3798

Any tag which has corresponding ``waitrepo`` task is given slightly higher
priority. It is useful mainly for MBS, but also chainbuilds should be a bit
faster.

Plugins
-------
**Kiwi: Import koji archive types**

| PR: https://pagure.io/koji/pull-request/3775

For new users it was confusing to manually add required archive types, so they
are now prepopulated.

**Sidetag: Editing extra and allowed list for rpm macros**

| PR: https://pagure.io/koji/pull-request/3674
| PR: https://pagure.io/koji/pull-request/3701

New ``extra`` options ``sidetag_debuginfo_allowed`` and ``sidetag_rpm_macros_allowed`` could be set up in parent tags. Sidetags derived from such tags can alter these extra settings.

VM
--
**vm: Retry libvirt connection**

| PR: https://pagure.io/koji/pull-request/3679

In case libvirt dies or is restarted, ``kojivmd`` will pick the new connection
without restart needed.

Content Generators
------------------
**Allow reimports into failed/cancelled builds**

| PR: https://pagure.io/koji/pull-request/3777

Similarly to regular builds, CGs now can reuse failed or cancelled builds.

**Save task_id correctly also in CGInitBuild**

| PR: https://pagure.io/koji/pull-request/3751

Last release introduced CG's ability to store relevant ``task_id`` in
buildinfo. Nevertheless, there was not consistent behaviour with and without
using build reservations. This is now fixed.

Utilities
---------
**koji-gc: fail on additional arguments**

| PR: https://pagure.io/koji/pull-request/3687

Simple update to fail if some unrecognized options are supplied.

Documentation
-------------
**kiwi: Remove tech-preview warning**

| PR: https://pagure.io/koji/pull-request/3816

Kiwi is production-ready now and interface shouldn't change in near future.

**Emphasize new build_from_scm hub policy**

| PR: https://pagure.io/koji/pull-request/3778

**Fix doc links**

| PR: https://pagure.io/koji/pull-request/3691

Devtools and tests
------------------

**Tests**

| PR: https://pagure.io/koji/pull-request/3722
| PR: https://pagure.io/koji/pull-request/3738
| PR: https://pagure.io/koji/pull-request/3747
| PR: https://pagure.io/koji/pull-request/3752
| PR: https://pagure.io/koji/pull-request/3771
| PR: https://pagure.io/koji/pull-request/3773
| PR: https://pagure.io/koji/pull-request/3781
| PR: https://pagure.io/koji/pull-request/3791
| PR: https://pagure.io/koji/pull-request/3799

**Use fakehub as a user**

| PR: https://pagure.io/koji/pull-request/3804

``--user`` option for ``fakehub``

**fakehub --pdb option**

| PR: https://pagure.io/koji/pull-request/3783

Drop into debugger on error.
