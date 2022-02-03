Koji 1.28.0 Release notes
=========================

All changes can be found in `the roadmap <https://pagure.io/koji/roadmap/1.28/>`_.
Most important changes are listed here.


Migrating from Koji 1.27/1.27.1
-------------------------------

For details on migrating see :doc:`../migrations/migrating_to_1.28`


Security Fixes
--------------

None


Client Changes
--------------
**Deprecated --paths option in list-buildroot**

| PR: https://pagure.io/koji/pull-request/3105

This option doesn't have any effect, so it should be removed in the near future.

**Remove rename-channel CLI and use editChannel in renameChannel**

| PR: https://pagure.io/koji/pull-request/3108

As we've extended ``edit-channel`` command this one is a redundant now. Same can
be achieved with ``edit-channel --name``. 

**mock-config: if topdir option is used, remove topurl**

| PR: https://pagure.io/koji/pull-request/3146

``--topdir`` option is treated as a superior to ``--topurl``. Specifying both
doesn't have semantical value, so we're overriding the second one.


API Changes
-----------
**Deprecated force option in groupPackageListRemove call**

| PR: https://pagure.io/koji/pull-request/3145

``force`` doesn't affect the call and as such can be confusing. User could
expect something which is not really happening (e.g. overriding some locks).
We're going to remove this option in near future.

**Deprecated remove-channel CLI and removeChannel API**

| PR: https://pagure.io/koji/pull-request/3158

``edit-channel`` and ``editChannel`` can do the same now.

**listPackages has now default with_blocked=True**

| PR: https://pagure.io/koji/pull-request/3196

It is more a regression fix and returning to original behaviour with this new
option.


Builder Changes
---------------
**AuthExpire returns code 1 in kojid**

| PR: https://pagure.io/koji/pull-request/3119

For automation of ``kojid`` restarts it is useful to retun exit code instead of
raising an exception.

System Changes
--------------
**Add limits on name values**

| PR: https://pagure.io/koji/pull-request/3028

Historically we were not casting any limits on names used throughout the koji.
We've trusted admins to create meaningful names. Nevertheless, some automation
tools are now having permissions which allow them to create tags, targets, etc.
As we're not able to control their code, we've introduced name templates which
can be used to limit which characters (via regexps) can be part of names. For
details see the documentation for hub options ``RegexNameInternal``,
``RegexUserName`` and ``MaxNameLengthInternal``.

**RLIMIT_OFILE alias for RLIMIT_NOFILE**

| PR: https://pagure.io/koji/pull-request/3116

``RLIMIT_OFILE`` is an old deprecated name, so we're using it as an alias for
now.

**Deprecated hub option DisableGSSAPIProxyDNFallback**

| PR: https://pagure.io/koji/pull-request/3117

Option doesn't affect anything anymore.

**Centralize name/id lookup clauses**

| PR: https://pagure.io/koji/pull-request/3123

Code improvement to make SQL layer more consistent.

**only raise error when authtype is not proxyauthtype**

| PR: https://pagure.io/koji/pull-request/3164

Fixing regression for webUIs having same authentication mechanism as user.

**Add description for permissions**

| PR: https://pagure.io/koji/pull-request/3214

All permissions now can have description visible via ``list-permissions``, so
they can be documented inside the koji not in external docs.

**Provide meaningful message when importing image files fails**

| PR: https://pagure.io/koji/pull-request/3223

More verbose error message for file types non-existent in the db.

**Allow password in SCM url with new builder option**

| PR: https://pagure.io/koji/pull-request/3212

Token/password can now be part of SCM url when submitting the build. Note, that
this will be visible everywhere and should be used only with caution (public
tokens). Otherwise, it can quite easily leak passwords. For the same reason this
behaviour must be explicitly allowed via ``allow_password_in_scm_url`` kojid
option.

**lib: refactor variables in is_conn_err()**

| PR: https://pagure.io/koji/pull-request/3204

Simple code cleanup

Web
---
**Rpminfo/fileinfo/imageinfo/archiveinfo page shows human-readable filesize**

| PR: https://pagure.io/koji/pull-request/3137

**Taginfo page shows packages with/without blocked**

| PR: https://pagure.io/koji/pull-request/3159

**Show total builds and add two more date options**

| PR: https://pagure.io/koji/pull-request/3215

Buildsbystatus web page is showing a bit more information now.


Plugins
-------
**protonmsg: allow users to specify router-specific topic prefixes**

| PR: https://pagure.io/koji/pull-request/3168

**kiwi**

Kiwi plugin for building images based on XML description files was extended and
refactored a bit, so it is now almost production-ready. We expect that in one or
two releases we can flip it to first-class plugin.

**kiwi: implant releasever into kiwi description**

| PR: https://pagure.io/koji/pull-request/3205

**kiwi: save modified .kiwi files per arch**

| PR: https://pagure.io/koji/pull-request/3211

Documentation
-------------
**Explain IMA signing vs usual RPM signing**

| PR: https://pagure.io/koji/pull-request/3206

**Improve multicall documentation**

| PR: https://pagure.io/koji/pull-request/3226

**Additional explanations for RPM signatures**

| PR: https://pagure.io/koji/pull-request/3218

**Link to koji overview video**

| PR: https://pagure.io/koji/pull-request/3195

**Drop RHEL6 references**

| PR: https://pagure.io/koji/pull-request/3177
