Koji 1.27.0 Release notes
=========================

All changes can be found in `the roadmap <https://pagure.io/koji/roadmap/1.27/>`_.
Most important changes are listed here.


Migrating from Koji 1.26/1.26.1
-------------------------------

For details on migrating see :doc:`../migrations/migrating_to_1.27`


Security Fixes
--------------

None


Client Changes
--------------
**set-task-priority permission error fix**

| PR: https://pagure.io/koji/pull-request/2999

CLI confusingly reported "closed task" even in case when user was "just" missing
the admin permission.

**Honour --force-auth for anonymous commands**

| PR: https://pagure.io/koji/pull-request/3010

This option was not respected in some cases.

**Propagate error in write-signed-copies**

| PR: https://pagure.io/koji/pull-request/3020
| PR: https://pagure.io/koji/pull-request/3093
| PR: https://pagure.io/koji/pull-request/3107

Due to speedup changes some errors could have been hidden. Now we're catching
them all and displaying properly in write-signed-copies command.

**Be tolerant of stops/jumps kwargs in list-tag-inheritance**

| PR: https://pagure.io/koji/pull-request/3055

Older client can emit errors when used against a newer hub as it could use
already deprecated options. We're now more tolerant to these.

**Dist-repo with write-signed-rpm option**

| PR: https://pagure.io/koji/pull-request/3058

New option for dist-repo --write-signed-rpms. As there could be
garbage-collected signed copies, dist-repo can fail and these rpms must be
manually reconstructed. This new option will allow user with `sign` permission
to prepare required rpms to be ready for the ``distRepo`` task.

**call --json default option set up to str**

| PR: https://pagure.io/koji/pull-request/3066


Bugfix for converting some datetime values to proper json when using ``call``
command.

**Add option for UTC time in list-history**

| PR: https://pagure.io/koji/pull-request/3090

``list-history`` now accepts ``--utc`` option which will display dates in UTC
instead of local timezone.

API Changes
-----------
**listBuilds/list-builds filtering via CG**

| PR: https://pagure.io/koji/pull-request/3009
| PR: https://pagure.io/koji/pull-request/3111

API call ``listBuilds`` (and its CLI counterpart) now accepts ``cgID``
(``--cg``) option which adds another filter based on content generator type.

**Deprecate taskReport**

| PR: https://pagure.io/koji/pull-request/3036

This call will be removed in the future.

**queryRPMSigs accepts RPM ID, NVRA and dict**

| PR: https://pagure.io/koji/pull-request/3064

To be aligned with other calls, ``queryRPMSigs`` now accepts all rpm ID
specifications (integer ID, NVRA string or NVRA dict)

**Deprecate koji.listFaults**

| PR: https://pagure.io/koji/pull-request/3082

Another candidate for removal

**Deprecated force option in groupReqListRemove call**

| PR: https://pagure.io/koji/pull-request/3089

And another one

**getBuildType: ensure id exists in buildinfo dict**

| PR: https://pagure.io/koji/pull-request/3092

More robust handling of input (NVR dict is sufficient now)

**Add strict option to listTagged, listTaggedRPMS, listTaggedArchives**

| PR: https://pagure.io/koji/pull-request/3095

For better differentiation between empty results for correct inputs and wrong
inputs (non-existing tag, etc.) ``strict`` option was added to these calls.

Builder Changes
---------------
**Import guestfs before dnf**

| PR: https://pagure.io/koji/pull-request/2993

Linking conflicts between json-parsing libraries used by guestfs and dnf led us
to include a small hack. Now it should be again possible to build docker images
via ``oz``.

**Better error messages for Task.lock()**

| PR: https://pagure.io/koji/pull-request/3007

Improved error logging related to multiple builders competing in task
allocation.

**Restart kojid and kojira services automatically**

| PR: https://pagure.io/koji/pull-request/3040

``systemd`` services were updated to automatically restart on failure with one
minute delay.

**Retry get_next_release to avoid race condition**

| PR: https://pagure.io/koji/pull-request/3103

In rare cases there was still race condition with starting image/maven builds
with same auto-incremented release. This should fix this behaviour completely.

System Changes
--------------
**Honour taginfo option in policy_get_build_tags**

| PR: https://pagure.io/koji/pull-request/2989

Deleted buildtags can break some policies. As these are more frequent these days
(via sidetag usage patterns) we have also hit this problem. It should be fixed
now.

**Fix scripts for koji pkg and drop utils from py2**

| PR: https://pagure.io/koji/pull-request/3002

Packaging fixes for regression. ``koji-utils`` are py3-only.

**Create symlink before import**

| PR: https://pagure.io/koji/pull-request/3004

Windows builds were not properly handling importing builds back to hub if volume
policy put the build to non-default volume.

**Speedup untagged_builds query**

| PR: https://pagure.io/koji/pull-request/3005

``untagged_builds`` call is used by garbage collection and it is now about 100%
faster. It doesn't matter that much to GC itself as it needn't to be
particularly fast but other queries/users are not blocked by this query lock.

**Support packages that are head-signed**

| PR: https://pagure.io/koji/pull-request/3012

DSA and RSA header signatures (RPMv4 scheme) support.

**Tasks respect disabled channels**

| PR: https://pagure.io/koji/pull-request/3030
| PR: https://pagure.io/koji/pull-request/3124

In last release option to "disable" channel was introduced. Anyway, tasks were
happily requesting those channels and were never executed as no builder picked
them. Now they fail immediately if the channel is disabled/non-existent in the
moment of task creation.

**Check spec_url for wrapperRPM task source policy test**

| PR: https://pagure.io/koji/pull-request/3047

``wrapperRPM`` tasks now properly propagate data for ``source`` policy test.

**Allow user on git://, git+http://, git+https://, and git+rsync:// scheme**

| PR: https://pagure.io/koji/pull-request/3067

We've not propagated username (or token) to builder. As this data are already
visible in task it doesn't make sense to conceal them on the builder. There are
legitimate cases when token is used, so we are now propagating it without
restriction.

**Logging warning messages about deleteBuild or deletedRPMSig**

| PR: https://pagure.io/koji/pull-request/3076

Last release introduced ``deleteRPMSig`` API call. It is the second call which
irrecoverably destroys build data so it should be better logged. We're now
capturing more data in the logs (especially the user).

**Remove translation stub functions**

| PR: https://pagure.io/koji/pull-request/3077

We've never used the i18n ``_`` call and we don't plan to introduce any
translation. So, we've decided to remove these stubs to make code a bit more
readable and consistent.

**Add specfile log to wrapperRPM**

| PR: https://pagure.io/koji/pull-request/3078

As specfile in ``wrapperRPM`` is modified from template it is nice to store this
file in similar way to modified kickstarts in oz tasks.

Web
---
**Allow kojiweb to proxy users obtained via different mechanisms**

| PR: https://pagure.io/koji/pull-request/3008

New ``proxyauthtype`` option is introduced to ``gssapi_login`` and ``ssl_login``
methods. It allows user1 (typically web interface) to proxy another user2 (via
standard ``proxyuser`` option) with different authentication mechanism than
user1. E.g. user is authenticated to webui by gssapi, while webui itself
authenticates via SSL certificate.

Utilities
---------

Kojira
......
**Don't throw exception when auth fails**

| PR: https://pagure.io/koji/pull-request/3099

More proper exit when authentication fails to not trigger abrt.

**Implement ignore_other_volumes option**

| PR: https://pagure.io/koji/pull-request/3126

Option to forbid kojira to delete repos on non-default volumes.


Documentation
-------------
**Some documentation updates**
| PR: https://pagure.io/koji/pull-request/2994
| PR: https://pagure.io/koji/pull-request/2995
| PR: https://pagure.io/koji/pull-request/2996
| PR: https://pagure.io/koji/pull-request/2997
| PR: https://pagure.io/koji/pull-request/3000
| PR: https://pagure.io/koji/pull-request/3013
| PR: https://pagure.io/koji/pull-request/3023
| PR: https://pagure.io/koji/pull-request/3029
| PR: https://pagure.io/koji/pull-request/3038
| PR: https://pagure.io/koji/pull-request/3051
| PR: https://pagure.io/koji/pull-request/3062
| PR: https://pagure.io/koji/pull-request/3070
| PR: https://pagure.io/koji/pull-request/3085
| PR: https://pagure.io/koji/pull-request/3086
| PR: https://pagure.io/koji/pull-request/3096
| PR: https://pagure.io/koji/pull-request/3102
| PR: https://pagure.io/koji/pull-request/3021
| PR: https://pagure.io/koji/pull-request/3026

**New tests**
| PR: https://pagure.io/koji/pull-request/3027
| PR: https://pagure.io/koji/pull-request/3037
| PR: https://pagure.io/koji/pull-request/3056
| PR: https://pagure.io/koji/pull-request/3075

**Basic security checks with bandit**

| PR: https://pagure.io/koji/pull-request/3043
