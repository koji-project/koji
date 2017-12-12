Koji 1.15 Release Notes
=======================

Migrating from the last release
-------------------------------

For details on migrating see :doc:`migrating_to_1.15`


Client Changes
--------------


Display License Info
^^^^^^^^^^^^^^^^^^^^

| PR: https://pagure.io/koji/pull-request/686


The `rpminfo` command now displays the `License` field from the rpm.


Support keytabs for GSSAPI authentication
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

| PR: https://pagure.io/koji/pull-request/708

Previously keytabs were only supported by the older kerberos auth method, which
is not supported on Python 3. Now the gssapi method supports them as well.


Add krb_canon_host option
^^^^^^^^^^^^^^^^^^^^^^^^^

| PR: https://pagure.io/koji/pull-request/653

Adds a new option `krb_canon_host` that tells Koji clients to get the dns canonical hostname for kerberos auth.
The existing `krb_rdns` option was an attempt to solve the same sort of issue, but caused problems for some network configurations.


The watch-task return code ignores sub-task failures
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

| PR: https://pagure.io/koji/pull-request/703

Previously, the watch-task command would return a non-zero exit status
if any subtask failed, even if this did not cause the parent task to fail.

Now that we have cases where subtasks are optional, this no longer makes sense,
so the exit code of the watch-task command is based solely on the results of
the top level tasks it is asked to watch.


Unify runroot CLI interface
^^^^^^^^^^^^^^^^^^^^^^^^^^^

| PR: https://pagure.io/koji/pull-request/633

The `runroot` command now supports options similar to the various build commands. These new
options are:


.. code-block:: text

  --nowait              Do not wait on task
  --watch               Watch task instead of printing runroot.log
  --quiet               Do not print the task information


New args for watch-logs command
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

| PR: https://pagure.io/koji/pull-request/625

The `watch-logs` command now supports the following new options:

.. code-block:: text

  --mine      Watch logs for all your tasks
  --follow    Follow spawned child tasks


Web UI changes
--------------

Show components for all archives
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

| PR: https://pagure.io/koji/pull-request/610

Previously, the Web UI only displayed component lists for image builds.
However, new build types can also have component lists.

Now the interface will display components for any archive that has them.


Display License Info
^^^^^^^^^^^^^^^^^^^^

| PR: https://pagure.io/koji/pull-request/686


The `rpminfo` page now displays the `License` field from the rpm.


Show suid bit in web UI
^^^^^^^^^^^^^^^^^^^^^^^

| PR: https://pagure.io/koji/pull-request/617

The web UI will now display the setuid bit when displaying rpm/archive file contents.


Builder changes
---------------

Use alternate tmpdir in mock chroots
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

| PR: https://pagure.io/koji/pull-request/602


Recent versions of mock (1.4+) default to use_nspawn=True, which results
in /tmp being a fresh tmpfs mount on every run. This means the /tmp
directory no longer persists outside of the mock invocation.

Now, the builder will use /builddir/tmp instead of /tmp for persistent data.


Store git commit hash in build.source
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

| PR: https://pagure.io/koji/pull-request/674

A build in Koji can be triggered from an scm url in a variety of
formats, for example:

    - git://pkgs.fedoraproject.org/<namespec>/<package>?#<git hash>
    - git://pkgs.fedoraproject.org/<namespec>/<package>?#<branch>
    - git://pkgs.fedoraproject.org/<namespec>/<package>

Previously, this source url was not properly stored for rpm builds. It
appeared in the task parameters, but the build.source field remained blank.
If a symbolic git ref (e.g. HEAD) was given in the url, the underlying
sha1 value was only recorded in the task logs.

With this change:

    * the scm url is stored in build.source
    * for git, the ref portion is resolved to its sha1 hash
    * the original scm url is saved in build.extra



System changes
--------------

Volume policy support
^^^^^^^^^^^^^^^^^^^^^

| PR: https://pagure.io/koji/pull-request/622

Koji has for many years had the ability to split its storage across multiple
volumes. However, there is no automatic process for placing builds onto
volumes other than the primary. To do so often requires a lot of manual work
from an admin.

This feature:

    * adds a volume policy check to the key import pathways
    * adds an applyVolumePolicy call to apply the policy to existing builds

The hub consults the volume policy at various points to
determine where a build should live. This allows admins to make rules like:

    all kernel builds go to the volume named kstore
    all builds built from the epel-7-build tag go to the volume named epel7
    all builds from the osbs content generator go to the volume named osbs

The default policy would places all builds on the default volume.

See also: :doc:`volumes`

messagebus plugin changes
^^^^^^^^^^^^^^^^^^^^^^^^^

| PR: https://pagure.io/koji/pull-request/537

There are two notable changes to the messagebus plugin this release.


Deferred sending
""""""""""""""""


Similar to the current behavior of the protonmsg plugin. Messages are queued
up during hub calls and only sent out during the ``postCommit`` callback.

This avoids sending messages about failed calls, which can be confusing to
message consumers (e.g. build state change messages about a build that does
not exist because it failed to import).

Test mode
"""""""""

The plugin now looks for a boolean ``test_mode`` option. If it is true, then
the messages are still queued up, but not actually sent. This makes it
possible to enable the plugin in test environments without having to set up a
separate message bus.


No notifications for disabled users or hosts
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

| PR: https://pagure.io/koji/pull-request/615


Koji will no longer send out email notifications to disabled users or
to users corresponding to a host.


Protonmsg plugin changes
^^^^^^^^^^^^^^^^^^^^^^^^

protonmsg: include the arch in the headers of rpm sign messages

| PR: https://pagure.io/koji/pull-request/657
| PR: https://pagure.io/koji/pull-request/651

There are two changes to how the protonmsg plugin handles rpmsign events:

    1. The arch of the rpm is included in messages
    2. The message are omitted when the sigkey is empty



Replace pycurl with requests
^^^^^^^^^^^^^^^^^^^^^^^^^^^^

| PR: https://pagure.io/koji/pull-request/601

All uses of the pycurl library have been replaced with calls
to python-requests, so pycurl is no longer required.


drop importBuildInPlace call
^^^^^^^^^^^^^^^^^^^^^^^^^^^^

| PR: https://pagure.io/koji/pull-request/606

The deprecated ``importBuildInPlace`` call has been dropped.

This call was an artifact of a particular bootstrap event that happened a long
time ago. It was never not really documented or recommended for use.


