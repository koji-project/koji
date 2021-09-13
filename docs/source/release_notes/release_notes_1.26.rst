Koji 1.26.0 Release notes
=========================

All changes can be found in `the roadmap <https://pagure.io/koji/roadmap/1.26/>`_.
Most important changes are listed here.


Migrating from Koji 1.25/1.25.1
-------------------------------

For details on migrating see :doc:`../migrations/migrating_to_1.26`


Security Fixes
--------------

None


Client Changes
--------------
**New command userinfo**

| PR: https://pagure.io/koji/pull-requests/2840

Similarly to web user info page, we've added command userinfo listing basic
informations like principals, permissions and activity statistics.

**Add noverifyssl option to oz image builds**

| PR#: http://pagure.io/koji/pull-requests/2860

Image builds could want to use development repos which are not recognized by CAs
installed inside the image. In such case there is a way to add ``--noverifyssl``
into the generated kickstart. The option must be explicitly enabled on builders
which will handle those tasks.

**download-build now pre-check non-existing sigkey**

| PR: https://pagure.io/koji/pull-requests/2864

When downloading builds with specified sigkey it could have been confusing that
404 error returned for non-existing sigkeys. Raising explicit error eliminates
network suspicion.

API Changes
-----------
**Remove jump/stops options from readFullInheritance**

| PR#: http://pagure.io/koji/pull-requests/2847

These unused options were finally removed.

**listBuilds accept also package name and user name**

| PR: https://pagure.io/koji/pull-request/2867
| PR: https://pagure.io/koji/pull-request/2922

It is an extension to previously required IDs.

**Remove deprecated readGlobalInheritance**

| PR: https://pagure.io/koji/pull-request/2879

**add_rpm_sign catches IntegrityError**

| PR: https://pagure.io/koji/pull-request/2909

Better error-handling in case of insert race-condition.

**Get info for deleted tag entries**

| PR: https://pagure.io/koji/pull-request/2923

There was no simple way how to obtain information about tag which are deleted.
Extension of ``getTag``'s ``event`` option for value ``auto`` will now return
existing tag or for deleted tag - last known configuration.


Builder Changes
---------------

**Livecd handler set up release if release not given**

| PR: https://pagure.io/koji/pull-request/2877

Standard ``getNextRelease`` call is used in such case now.

**Prune user repos for image tasks**

| PR: https://pagure.io/koji/pull-request/2967

If multiple repos are specified in task, they'll get pruned. This could happen
if task is created by some automation. Using multiple repos with same url just
consumes memory of anaconda's ramdisk and can result in failed tasks.

**Use getNextRelease for scratch image builds**

| PR: https://pagure.io/koji/pull-request/2974

System Changes
--------------
**Policy test buildtag_inheritance**

| PR: https://pagure.io/koji/pull-request/2872

This new test can be used to check if tag's inheritance contains other specific
tag.

**Fix SQL condition**

| PR: https://pagure.io/koji/pull-request/2898

``listTagged`` was broken in regression from https://pagure.io/koji/pull-request/2791

**Channels can now be disabled and described**

| PR: https://pagure.io/koji/pull-request/2905
| PR: https://pagure.io/koji/pull-request/2933

**dist-repo takes inherited arch when arch is not set**

| PR: https://pagure.io/koji/pull-request/2912

If tag for ``dist-repo`` doesn't have any configured architectures, koji will
look into the inheritance chain and try to find something there.

**Extend SCM.assert_allowed with hub policy**

| PR: https://pagure.io/koji/pull-request/2951

SCM policy can be defined at the hub now. It also allow more granular policies
like allowing some SCMs for scratch builds while others also for regular ones.
This approach can be combined with the current ``kojid.conf`` ``allowed_scms``
option. See example ``kojid.conf`` for more details.

**DBConnectionString/dsn option for db connection**

| PR: https://pagure.io/koji/pull-request/2958

Alternative method for specifying DB connection is now provided via single `DSN
connection string
<https://www.postgresql.org/docs/current/libpq-connect.html#LIBPQ-CONNSTRING>`_.

**Add remove-sig CLI and deleteRPMSig hub call**

| PR: https://pagure.io/koji/pull-request/2965

The ``deleteRPMSig`` hub call removes RPM signatures from Koji. Only use this
method in extreme situations, because it goes against Koji's design of
immutable, auditable data. This call requires ``admin`` permission (``sign``
is not sufficient).

VM
--
**py3 kojikamid fixes**

| PR: https://pagure.io/koji/pull-request/2977

Python 3 port of ``kojikamid`` had a few regressions.

Web
---
**Drop download link from deleted build**

| PR: https://pagure.io/koji/pull-request/2896

It was confusing that link was there even for non-existing files.

**Fix getting tag ID for buildMaven taskinfo page.**

| PR: https://pagure.io/koji/pull-request/2900

Maven task info page was broken for some time due to wrong tag ID handling.

**Hosts page with more filters and added channel column**

| PR: https://pagure.io/koji/pull-request/2910

Simple extension for hosts list page.

**Update webUI number of tasks**

| PR: https://pagure.io/koji/pull-request/2937

As we've dropped number of results on first task info page due to speed reasons,
it is now a bit confusing for users. We've added a bit more indicative result.

Plugins
-------
**Configurable naming template for sidetags**

| PR: https://pagure.io/koji/pull-request/2894

Sidetags now can be named according to set of templates in the config. These
templates then can be used in hub policies for differentiating among the
different side tag types.

**Add btype to protonmsg**

| PR: https://pagure.io/koji/pull-request/2934
| PR: https://pagure.io/koji/pull-request/2955

Build types are now part of proton messages.


Utilities
---------

Kojira
......
**Don't fail on deleted needed tag**

| PR: https://pagure.io/koji/pull-request/2936

Deleted tags could have caused kojira's thread crash which could have been seen
only in the log but kojira still have run. Repository cleanup then could have
failed without notice.

**Do not ever clean up repositories where 'latest' points to**

| PR: https://pagure.io/koji/pull-request/2950
| PR: https://pagure.io/koji/pull-request/2970

We now skip all "latest" repos.

Sweep DB
........

**Read options from main hub config and its config dir**

| PR: https://pagure.io/koji/pull-request/2887

``koji-sweep-db`` now properly reads whole config structure, not only basic
``kojihub.conf``


Documentation
-------------
**Update irc info**

| PR: https://pagure.io/koji/pull-request/2884

**Docs for KojiHubCA/ClientCA for web**

| PR: https://pagure.io/koji/pull-request/2888

**Remove old mod_ssl instructions from server howto**

| PR: https://pagure.io/koji/pull-request/2960

**Document readTaggedRPMS method**

| PR: https://pagure.io/koji/pull-request/2971

**Add signing documentation**

| PR: https://pagure.io/koji/pull-request/2986


**"download-logs --help" fixes**

| PR: https://pagure.io/koji/pull-requests/2952

**cli: improve --config and --profile help text**

| PR: https://pagure.io/koji/pull-requests/2985


