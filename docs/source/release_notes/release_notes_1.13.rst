Koji 1.13 Release Notes
=======================

Migrating from Koji 1.12
------------------------

For details on migrating see :doc:`../migrations/migrating_to_1.13`


Client Changes
--------------

Python 3 client support
^^^^^^^^^^^^^^^^^^^^^^^

| PR: https://pagure.io/koji/pull-request/417

The koji command and core library now support Python 3 (as well as 2). The
default spec now produces both `python2-koji` and `python3-koji`
subpackages. The `koji` package still contains the (now much smaller)
``/usr/bin/koji`` file.

Some older features are not supported by the Python 3 client

    * the `use_old_ssl` option is not supported, python-requests must be used
    * the old kerberos auth mechanism is not supported, use gssapi instead

CLI Plugins
^^^^^^^^^^^

| PR: https://pagure.io/koji/pull-request/199

The command line interface now has basic plugin support. The primary use case
is for plugins to be able to add new subcommands.
For details see: :ref:`plugin-cli-command`

list-channels CLI command
^^^^^^^^^^^^^^^^^^^^^^^^^

| PR: https://pagure.io/koji/pull-request/442

The new `list-channels` command lists the known channels for the system.

.. code-block:: text

    Usage: koji list-channels
    (Specify the --help global option for a list of other help options)

    Options:
      -h, --help  show this help message and exit
      --quiet     Do not print header information

hostinfo CLI command
^^^^^^^^^^^^^^^^^^^^

| PR: https://pagure.io/koji/pull-request/399
| Issue: https://pagure.io/koji/issue/364

The new ``hostinfo`` command shows basic information about a build host,
similar to the web interface.

.. code-block:: text

    Usage: koji hostinfo [options] <hostname> [<hostname> ...]
    (Specify the --help global option for a list of other help options)

    Options:
      -h, --help  show this help message and exit

Enhancements to restart-hosts
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

| PR: https://pagure.io/koji/pull-request/472

The `restart-hosts` command is used by admins to safely restart the build hosts
after a configuration change.

Because multiple restarts can conflict, the command will now exit with a error
if a restart is already underway (can be overridden with --force).

There are now options to limit the restart to a given channel or arch.

The command now has a timeout option, which defaults to 24hrs.

User-Agent header
^^^^^^^^^^^^^^^^^

| PR: https://pagure.io/koji/pull-request/393
| Issue: https://pagure.io/koji/issue/392

Previously the Koji client library reported a confusingly out-of-date value
in the ``User-Agent`` header. Now it simply reports the major version.

raise error on non-existing profile
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

| PR: https://pagure.io/koji/pull-request/375
| Issue: https://pagure.io/koji/issue/370

If the requested client profile is not configured, the library will raise an
error, rather than proceeding with default values.

See also: :doc:`../profiles`


Changes to the Web interface
----------------------------

Build Log Display
^^^^^^^^^^^^^^^^^

| PR: https://pagure.io/koji/pull-request/471

The build info pages now display the log files for a build (instead of linking
directly to the directory on the download server). This works for all builds,
including those imported by content generators.


Builder changes
---------------

Configuring mock chroot behavior
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

| PR: https://pagure.io/koji/pull-request/400
| Issue: https://pagure.io/koji/issue/398

Koji now supports using mock's --new-chroot option on a per-tag basis.
For details see: :ref:`tuning-mock-per-tag`

pre/postSCMCheckout callbacks
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

The callback interface is used by plugins to hook into various Koji operations.
With this release we have added callbacks in the builder daemon for before and
after source checkout: ``preSCMCheckout`` and ``postSCMCheckout``.

Extended allowed_scms format
^^^^^^^^^^^^^^^^^^^^^^^^^^^^

| PR: https://pagure.io/koji/pull-request/421

The allowed_scms option now accepts entries like:

::

    !host:repository

to explicitly block a host:repository pattern.

See also: :ref:`scm-config`


System changes
--------------

mod_auth_gssapi required
^^^^^^^^^^^^^^^^^^^^^^^^

| PR: https://pagure.io/koji/pull-request/444

On modern platforms, both koji-hub and koji-web now require
mod_auth_gssapi instead of mod_auth_kerb.


Longer tag names
^^^^^^^^^^^^^^^^

| PR: https://pagure.io/koji/pull-request/388
| Issue: https://pagure.io/koji/issue/369

Previously, tag names were limited to 50 characters. They are now limited
to 256 characters.
