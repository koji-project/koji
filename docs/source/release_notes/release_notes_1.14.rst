Koji 1.14 Release Notes
=======================

Migrating from Koji 1.13
------------------------

For details on migrating see :doc:`../migrations/migrating_to_1.14`


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


Allow profiles to request a specific python version
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

| PR: https://pagure.io/koji/pull-request/566

On platforms with python3 available, the Koji client is built to execute
with the python3 binary. However, there are a few client features that do not
work under python3, notably old-style (non-gssapi) Kerberos authentication.

If this issue is affecting you, you can set ``pyver=2`` in your Koji
configuration. This can be done per profile. When Koji sees this setting
at startup, it will re-execute itself under the requested python binary.


New list-builds command
^^^^^^^^^^^^^^^^^^^^^^^

| PR: https://pagure.io/koji/pull-request/526

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


New block-group command
^^^^^^^^^^^^^^^^^^^^^^^

| PR: https://pagure.io/koji/pull-request/509

The ``block-group`` command allows admins to block package group entries
without having to resort to the ``call`` command.

.. code-block:: text

    Usage: koji block-group <tag> <group>
    (Specify the --help global option for a list of other help options)

    Options:
      -h, --help  show this help message and exit


Exit codes for some commands
^^^^^^^^^^^^^^^^^^^^^^^^^^^^

| PR: https://pagure.io/koji/pull-request/558
| PR: https://pagure.io/koji/pull-request/559

Several more commands will now return a non-zero exit code
when an error occurs:

    * the various image building commands
    * the ``save-failed-tree`` command (provided by a plugin)


Easier for scripts to use activate_session
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

| PR: https://pagure.io/koji/pull-request/493

In Koji 1.13.0, it became possible for scripts to ``import koji_cli.lib`` and
gain access to the ``activate_session`` function that the command line tool
uses to authenticate.

In this release, this function has been made easier for scripts to use:

    * the options argument can now be a dictionary
    * less options need to be specified


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

Now, Koji will normalize these paths before the ``allowed_scms`` check.


Graceful reload
^^^^^^^^^^^^^^^

| PR: https://pagure.io/koji/pull-request/565


For a long time kojid has handled the USR1 signal by initiating a graceful restart.
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

Two changes make it easier to write a configuration for the runroot plugin.

The ``path_subs`` option is now more forgiving about whitespace:

    * leading and trailing whitespace is ignored for each line
    * blank lines are ignored

The ``[pathNN]`` sections are no longer required to have sequential numbers.
Previously, the plugin expected a sequence like ``[path0]``, ``[path1]``,
``[path2]``, etc, and would stop looking for entries if the next number
was missing. Now, any set of distinct numbers is valid and all ``[pathNN]``
sections will be processed.


System changes
--------------

Deprecations
^^^^^^^^^^^^

| PR: https://pagure.io/koji/pull-request/554
| PR: https://pagure.io/koji/pull-request/597

The following features are deprecated and will be removed in a future release:

    * the ``importBuildInPlace`` rpc call
    * the ``use_old_ssl`` client configuration option (and the underlying
      ``koji.compatrequests`` library)


Removed calls
^^^^^^^^^^^^^

| PR: https://pagure.io/koji/pull-request/497
| PR: https://pagure.io/koji/pull-request/507

The deprecated ``buildFromCVS`` hub call has been removed. It was replaced
by the ``buildSRPMFromCVS`` call many years ago and has been deprecated since
version 1.6.0.

The ``add_db_logger`` function has been removed from the koji library, along
with the ``log_messages`` table in the db. This extraneous call has never been
used in Koji.


Dropped mod_python support
^^^^^^^^^^^^^^^^^^^^^^^^^^

| PR: https://pagure.io/koji/pull-request/508


Koji no longer supports mod_python. This option has been deprecated since
mod_wsgi support was added in version 1.7.0.

See also: :doc:`../migrations/migrating_to_1.7`


Large integer support
^^^^^^^^^^^^^^^^^^^^^

| PR: https://pagure.io/koji/pull-request/571


Koji uses xmlrpc for communications with the hub, and unfortunately the
baseline xmlrpc standard only supports 32-bit signed integers. This
results in errors when larger integers are encountered, typically
when a file is larger than 2 GiB.

Starting with version 1.14.0, Koji will emit ``i8`` tags when encoding
large integers for xmlrpc. Integers below the limit are still encoded
with the standard ``int`` tag. The only time this makes a difference
is when Koji would previously have raised an ``OverflowError``.

The ``i8`` tag comes from the
`ws-xmlrpc <https://ws.apache.org/xmlrpc/types.html>`__
spec. Python's xmlrpc decoder has
for many years accepted and understood this tag, even though its encoder
would not emit it.

Previous versions of Koji worked around such size issues by converting
large integers to strings in a few targeted places. Those targeted
workarounds have been left in place on the hub for the sake of backward
compatibility.


Test mode for protonmsg plugin
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

| PR: https://pagure.io/koji/pull-request/538

The ``protonmsg`` plugin now accepts a boolean ``test_mode`` configuration
option. When this option is enabled, the plugin will not actually
send messages, but will instead log them (at the DEBUG level).

This option allows testing environments to run with the plugin enabled, but
without requiring a message bus to be set up for that environment.


Handling of debugsource rpms
^^^^^^^^^^^^^^^^^^^^^^^^^^^^

| PR: https://pagure.io/koji/pull-request/524

Koji will now treat rpms ending in ``-debugsource`` the same way that it does
other debuginfo rpms. Such rpms are:

    * omitted from Koji's normal yum repos
    * listed separately when displaying builds
    * not downloaded by default in the ``download-build`` command


Added kojifile component type for content generators
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

| PR: https://pagure.io/koji/pull-request/506

Content generator imports now accept entries with type equal to ``kojifile``
in the component lists for buildroots and images/archives. This type provides
a more reliable way to reference archive that come from Koji.

See: :ref:`Example metadata <metadata-kojifile>`.
