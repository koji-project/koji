Koji 1.15 Release Notes
=======================

Updates
-------

- :doc:`Koji 1.15.1 <release_notes_1.15.1>` is a security update for Koji 1.15

Migrating from the previous release
-----------------------------------

For details on migrating see :doc:`../migrations/migrating_to_1.15`


Client Changes
--------------


Display license Info
^^^^^^^^^^^^^^^^^^^^

| PR: https://pagure.io/koji/pull-request/686


The ``rpminfo`` command now displays the ``License`` field from the rpm.


Keytabs for GSSAPI authentication
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

| PR: https://pagure.io/koji/pull-request/708

Previously keytabs were only supported by the older kerberos auth method, which
is not available on Python 3. Now the gssapi method supports them as well.


Add krb_canon_host option
^^^^^^^^^^^^^^^^^^^^^^^^^

| PR: https://pagure.io/koji/pull-request/653

This release adds a ``krb_canon_host`` option that tells Koji clients
to use the dns canonical hostname for kerberos auth.

This option allows kerberos authentication to work in situations where
the hub is accessed via a cname, but the hub's credentials are under
its canonical hostname.

If specified, this option takes precedence over the older
option named ``krb_rdns``. That option caused Koji clients to perform a
reverse name lookup for kerberos auth.

When configuring kojiweb (in web.conf), the option is named ``KrbCanonHost``.

Both options only affect the older kerberos authentication path, and not
gssapi.


Watch-task return code
^^^^^^^^^^^^^^^^^^^^^^

| PR: https://pagure.io/koji/pull-request/703

Previously, the ``watch-task`` command would return a non-zero exit status
if any subtask failed, even if this did not cause the parent task to fail.

Now that we have cases where subtasks are optional, this no longer makes sense.
The exit code is now based solely on the results of
the top level tasks it is asked to watch.


New runroot options
^^^^^^^^^^^^^^^^^^^

| PR: https://pagure.io/koji/pull-request/633

The ``runroot`` command now supports options similar to the various build commands. These new
options are:


.. code-block:: text

  --nowait              Do not wait on task
  --watch               Watch task instead of printing runroot.log
  --quiet               Do not print the task information


New watch-logs options
^^^^^^^^^^^^^^^^^^^^^^

| PR: https://pagure.io/koji/pull-request/625

The ``watch-logs`` command now supports the following new options:

.. code-block:: text

  --mine      Watch logs for all your tasks
  --follow    Follow spawned child tasks


Web UI changes
--------------

Archive component display
^^^^^^^^^^^^^^^^^^^^^^^^^

| PR: https://pagure.io/koji/pull-request/610

Previously, the web UI only displayed component lists for image builds.
However, new build types can also have component lists.

Now the interface will display components for any archive that has them.


Display license Info
^^^^^^^^^^^^^^^^^^^^

| PR: https://pagure.io/koji/pull-request/686


The ``rpminfo`` page now displays the ``License`` field from the rpm.


Show suid bit
^^^^^^^^^^^^^

| PR: https://pagure.io/koji/pull-request/617

The web UI will now display the setuid bit when displaying rpm/archive file contents.




Builder changes
---------------


Alternate tmpdir for mock chroots
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

| PR: https://pagure.io/koji/pull-request/602


Recent versions of mock (1.4+) default to ``use_nspawn=True``, which results
in /tmp being a fresh tmpfs mount on every run. This means the /tmp
directory no longer persists outside of the mock invocation.

Now, the builder will use /builddir/tmp instead of /tmp for persistent data.


Store git commit hash
^^^^^^^^^^^^^^^^^^^^^

| PR: https://pagure.io/koji/pull-request/674

In Koji, for builds from an SCM, the source is specified as an
scm url.
For git urls, the revision in that url can be anything that git
will recognize, including:

    - a sha1 ref
    - an abbreviated sha1 ref
    - a branch name
    - a tag
    - HEAD

With this change:

    * the revision is replaced with the full sha1 ref for git urls
    * the scm url is stored in build.source
    * the original scm url is saved in build.extra

Previously, this source url was not properly stored for rpm builds. It
appeared in the task parameters, but the build.source field remained blank.
If a symbolic git ref (e.g. HEAD) was given in the url, the underlying
sha1 value was only recorded in the task logs.



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

    - all kernel builds go to the volume named kstore
    - all builds built from the epel-7-build tag go to the volume named epel7
    - all builds from the osbs content generator go to the volume named osbs

The default policy places all builds on the default volume.

See also: :doc:`../volumes`

Messagebus plugin changes
^^^^^^^^^^^^^^^^^^^^^^^^^

| PR: https://pagure.io/koji/pull-request/537

There are two notable changes to the messagebus plugin this release:


Deferred sending
""""""""""""""""

Similar to the current behavior of the protonmsg plugin, messages are queued
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


Protonmsg plugin changes
^^^^^^^^^^^^^^^^^^^^^^^^

| PR: https://pagure.io/koji/pull-request/657
| PR: https://pagure.io/koji/pull-request/651

There are two changes to how the protonmsg plugin handles rpmsign events:

    1. The arch of the rpm is included in messages
    2. The message are omitted when the sigkey is empty



No notifications for disabled users or hosts
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

| PR: https://pagure.io/koji/pull-request/615


Koji will no longer send out email notifications to disabled users or
to users corresponding to a host.


Replace pycurl with requests
^^^^^^^^^^^^^^^^^^^^^^^^^^^^

| PR: https://pagure.io/koji/pull-request/601

All uses of the pycurl library have been replaced with calls
to python-requests, so pycurl is no longer required.


Drop importBuildInPlace call
^^^^^^^^^^^^^^^^^^^^^^^^^^^^

| PR: https://pagure.io/koji/pull-request/606

The deprecated ``importBuildInPlace`` call has been dropped.

This call was an artifact of a particular bootstrap event that happened a long
time ago. It was never really documented or recommended for use.
