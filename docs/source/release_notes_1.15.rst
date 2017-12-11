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



System changes
--------------

Deprecations
^^^^^^^^^^^^


Removed calls
^^^^^^^^^^^^^

