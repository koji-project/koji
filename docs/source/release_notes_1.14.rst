Koji 1.14 Release Notes
=======================

Migrating from Koji 1.13
------------------------

For details on migrating see :doc:`migrating_to_1.14`


Client Changes
--------------


Fail fast option for builds
^^^^^^^^^^^^^^^^^^^^^^^^^^^

| PR: https://pagure.io/koji/pull-request/432


When builders are configured with ``build_arch_can_fail = True`` then the
failure of a single buildArch task does not immediately cause the build
to fail. Instead, the remaining buildArch tasks are allowed to complete,
at which point the build will still fail.

Sometimes developers would rather a build fail immediately, so we have added
the ``--fail-fast`` option to the build command, which overrides this setting.
The option only has an effect if the builders are configured to fail slow.


Allow profiles to request a specific python version
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

| PR: https://pagure.io/koji/pull-request/566

On platforms with python3 available, the Koji client is built to execute
with the python3 binary. However, there are a few features that do not
work under python3, notably old-style (non-gssapi) Kerberos authentication.

If this issue is affecting you, you can set ``pyver=2`` in your Koji
configuration. This can be done per profile. When Koji sees this setting
at startup, it will re-execute itself under the requested python binary.


Easier for scripts to use activate_session
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

| PR: https://pagure.io/koji/pull-request/493

In Koji 1.13.0, it became possible for scripts to ``import koji_cli.lib`` and
gain access to the ``activate_session`` function that the command line tool
uses to authenticate.

In this release, this function has been made easier for scripts to use:

    * the options argument can now be a dictionary
    * less options need to be specified


New list-builds command
^^^^^^^^^^^^^^^^^^^^^^^

The command line now has a ``list-builds`` command that has similar
functionality to the builds tab of the web interface.

.. code-block:: text

    Usage: koji list-builds [options]
    (Specify the --help global option for a list of other help options)

    Options:
      -h, --help            show this help message and exit
      --package=PACKAGE     List builds for this package
      --buildid=BUILDID     List specific build from ID or nvr
      --before=BEFORE       List builds built before this time
      --after=AFTER         List builds built after this time
      --state=STATE         List builds in this state
      --type=TYPE           List builds of this type.
      --prefix=PREFIX       Only list packages starting with this prefix
      --owner=OWNER         List builds built by this owner
      --volume=VOLUME       List builds by volume ID
      -k FIELD, --sort-key=FIELD
                            Sort the list by the named field
      -r, --reverse         Print the list in reverse order
      --quiet               Do not print the header information


Exit codes for some commands
^^^^^^^^^^^^^^^^^^^^^^^^^^^^

| PR: https://pagure.io/koji/pull-request/558
| PR: https://pagure.io/koji/pull-request/559

Several more commands will now return a non-zero exit code
when an error occurs:

    * the various image building commands
    * the ``save-failed-tree`` command (provided by a plugin)


New block-group command
^^^^^^^^^^^^^^^^^^^^^^^

| PR: https://pagure.io/koji/pull-request/509

The ``block-group`` command allows admins to block package group entries
without having to resort to the ``call`` command.

.. code-block:: text

    Usage: lkoji block-group <tag> <group>
    (Specify the --help global option for a list of other help options)

    Options:
      -h, --help  show this help message and exit


Builder changes
---------------





System changes
--------------

TODO
