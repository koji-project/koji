Koji 1.17.0 Release notes
=========================


Migrating from Koji 1.16
------------------------

For details on migrating see :doc:`../migrations/migrating_to_1.17`



Security Fixes
--------------

**CVE-2018-1002161 - SQL injection in multiple remote calls**

| PR: https://pagure.io/koji/pull-request/1274

This release includes the fix for :doc:`../CVEs/CVE-2018-1002161`


Client Changes
--------------

**Volume id option for livemedia and livecd tasks**

| PR: https://pagure.io/koji/pull-request/1227

The ``spin-livecd`` and ``spin-livemedia`` commands now accept a ``--volid``
argument to specify the volume id for the media. If unspecified, the
volume id is chosen via the same heuristic as before.

Volume ids must be 32 characters or less.



**Build order preserved by clone-tag**

| PR: https://pagure.io/koji/pull-request/1014

This is an improvement to the ``clone-tag`` command. Previously, when the
command was used without the ``--latest-only`` option, it could get the
ordering of builds wrong in the destination tag. Now, the order will
match the source tag.



**Configurable authentication timeout**

| PR: https://pagure.io/koji/pull-request/1172

Previously, the network timeout during authentication was hard coded to
60 seconds. It is now configurable via the ``auth_timeout`` configuration
option.


**Additional information from list-channels command**

| PR: https://pagure.io/koji/pull-request/940

The ``list-channels`` command now shows three separate host counts for
each channel:

- the number of enabled hosts in the channel
- the number of ready hosts in the channel
- the number of disabled hosts in the channel


**The free-task command requires at least one task-id**

| PR: https://pagure.io/koji/pull-request/1045

Previously this command was a no-op when given no arguments. Now it will return an
error.



Library Changes
---------------

**Drop encode_int function**

| PR: https://pagure.io/koji/pull-request/852

This is a follow up to the large integer support that we added in version 1.14

See also: :doc:`release_notes_1.14`

The ``encode_int`` function is no longer used
and has been dropped from the library.

Because we no longer call ``encode_int``, the hub will now always use i8 tags
when returning large integers, rather than returning them as strings in some
cases.


**Use custom Kerberos context with krb_login**

| PR: https://pagure.io/koji/pull-request/1187

Clients can now pass in their own Kerberos context to
``ClientSession.krb_login()`` using
the ``ctx`` parameter. This is intended for multi-threaded clients.


**Custom keyboard interrupt handling in watch_tasks**

| PR: https://pagure.io/koji/pull-request/981

The new ``ki_handler`` option for the ``koji_cli.lib.watch_tasks()`` function
allows other cli tools to set their own handler for keyboard interrupts.
If specified, the value should be callable and will be called when a
keyboard interrupt is encountered.
If unspecified, the original behavior is retained.


**_unique_path() -> unique_path**

| PR: https://pagure.io/koji/pull-request/980

The ``_unique_path`` function is deprecated. It has been replaced
by ``unique_path``.


Web UI Changes
--------------

**Additional info on builders in channelinfo page**

| PR: https://pagure.io/koji/pull-request/989

The channelinfo page now shows enabled/ready status for each host and a count
for each.



Builder Changes
---------------

**Builder task_avail_delay check**

| PR: https://pagure.io/koji/pull-request/1176

This delay works around a deficiency in task scheduling. The default
delay is 300 seconds and can be adjusted with the ``task_avail_delay``
option to kojid. However, it is unlikely that admins will need to
adjust this setting.

Despite the name, this does not introduce any new delay compared to the
old behavior. The setting controls how long a host will wait before taking
a task in a given channel-arch "bin" when that host has an available
capacity lower than the median for that bin. Previously, such hosts
could wait forever.



System Changes
--------------


**Python 3 Support**

| PR: https://pagure.io/koji/pull-request/1117
| PR: https://pagure.io/koji/pull-request/891
| PR: https://pagure.io/koji/pull-request/921
| PR: https://pagure.io/koji/pull-request/1184
| PR: https://pagure.io/koji/pull-request/1019
| PR: https://pagure.io/koji/pull-request/685
| ...and many fixes

Support for Python 3 has been extended to all components of Koji. Including:

- Hub
- Builder
- Web UI
- Utils



**No more messagebus plugin**

| PR: https://pagure.io/koji/pull-request/1043

The messagebus plugin has been dropped. The protonmsg plugin is still
available.



**Simple mode for mergerepos**

| PR: https://pagure.io/koji/pull-request/1066

External repos now have a ``merge_mode`` option. Valid values are
either ``koji`` (the old way) or ``simple`` (a new alternative). This
option can be set with the ``--mode`` option to the ``add-external-repo``
or ``edit-external-repo`` commands.

When an external repo is merged with simple mode, a number of the complex
filters that Koji normally applies are skipped. This mode still honors
the block list from Koji and ignores duplicate NVRAs, but otherwise
it simply merges the repo in.

Multiple merge modes cannot be combined in a single tag. If a tag
has two external repos with different modes, then the repo will
fail to generate.


**Avoid "unknown task" errors in Kojira**

| PR: https://pagure.io/koji/pull-request/1175

This is a bug fix for a minor race condition in Kojira that could cause
errors in the log and redundant repo regens.



**Full filename display for kojifiles directory indexes**

| PR: https://pagure.io/koji/pull-request/1156

This is simply a change to the default httpd configuration for serving
/mnt/koji. It adds ``NameWidth=*`` to ``IndexOptions`` so that long filenames
are fully displayed.



**Broader support for target/source/scratch tests in channel policy**

| PR: https://pagure.io/koji/pull-request/962

It is now possible to write channel policy rules based on
build target, source, and scratch options for task types other
than ``build``.



**Longer Build Target names**

| PR: https://pagure.io/koji/pull-request/925

Build target names can now be up to 256 characters, the same length
restriction as for tag names.
