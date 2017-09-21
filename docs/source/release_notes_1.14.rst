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


Normalize paths for scms
^^^^^^^^^^^^^^^^^^^^^^^^

| PR: https://pagure.io/koji/pull-request/591


For many years, kojid has supported the ``allowed_scms`` option
(see: :ref:`scm-config`) for controlling which scms can be used for building.
In 1.13.0, Koji added the ability to explicitly block a host:path pattern.

Unfortunately, 1.13.0 did not normalize the path before checking the pattern,
making it possible for users to use equivalent paths to route around the
block patterns.

Now, Koji will normalize these paths before the allowed_scms check.


Graceful reload
^^^^^^^^^^^^^^^

| PR: https://pagure.io/koji/pull-request/565


For a long time kojid handled the USR1 signal by initiating a graceful restart.
This change exposes that in the systemd service config (and the init script
on older platforms).

Now, ``service kojid reload`` will trigger the same sort of restart that the
``restart-hosts`` command accomplishes, but only for the build host you run it
on. When this happens, kojid will:

    * stop taking new tasks
    * wait for current tasks to finish
    * restart itself once all its tasks are completed


Friendlier runroot configuration
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

| PR: https://pagure.io/koji/pull-request/539
| PR: https://pagure.io/koji/pull-request/528

Two changes make it easier to write a configuration for runroot.

The ``path_subs`` configuration for the builder runroot plugin is now more
forgiving about whitespace:

    * leading and trailing whitespace is ignored for each line
    * blank lines are ignored

The ``[pathNN]`` sections are no longer required to have sequential numbers.
Previously, the plugin expected a sequence like ``[path0]``, ``[path1]``,
``[path2]``, etc, and would stop looking for entries if the next number
was missing. Now, any set of distinct numbers is valid and all ``[pathNN]``
sections will be processed.


Custom Lorax templates
^^^^^^^^^^^^^^^^^^^^^^

| PR: https://pagure.io/koji/pull-request/419

Koji now supports custom Lorax templates for the ``spin-livemedia`` command.
The command accepts two new options:

.. code-block:: text

      --lorax_url=URL       The URL to the SCM containing any custom lorax
                            templates that are to be used to override the default
                            templates.
      --lorax_dir=DIR       The relative path to the lorax templates directory
                            within the checkout of "lorax_url".


The Lorax templates must come from an SCM, and the ``allowed_scms`` rules
apply.

When these options are used, the templates will be fetched and an appropriate
``--lorax-templates`` option will be passed to the underlying livemedia-creator
command.



System changes
--------------

TODO
