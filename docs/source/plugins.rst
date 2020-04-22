=======
Plugins
=======

Following plugins are available in default koji installation.

Runroot
=======

Plugin for running any command in buildroot.

Save Failed Tree
================

In some cases developers want to investigate exact environment in which their
build failed. Reconstructing this environment via mock needn't end with
exactly same structure (due to builder settings, etc.). In such case this
plugin can be used to retrieve tarball with complete mock tree.

Additional feature is that some paths from buildroot can be left out from
tarball. Feature can be configured via
`/etc/kojid/plugins/save_failed_tree.conf` file. Currently only field
filters.paths is used and it consists of globs (standard python's fnmatch is
used) separated by whitespaces.

.. code-block:: ini

  [filters]
  paths = /etc/*.keytab /tmp/secret_data

.. warning::
  For security reasons, currently all ``/tmp/krb5cc*`` and ``/etc/*.keytab``
  files are removed from tarball. If we found some other dangerous pieces,
  they can be added to this blacklist.

Special task method is created for achieving this which is called
``SaveFailedTree``. This task can be created via CLI:
``koji save-failed-tree <taskID>``. Additional options are:

.. option:: --full

   directs koji to create tarball with complete tree.

.. option:: --nowait

   exit immediately after creating task

.. option:: --quiet

   don't print any information to output

After task finishes, one can find the tarball on relevant task web page (URL
will be printed to stdout until ``--quiet`` is used.

Plugin allow to save trees only for tasks defined in config
``/etc/koji-hub/plugins/save_failed_tree.conf``. Option
``allowed_methods`` contains list of comma-delimited names of tasks. Default
configuration contains line: ``allowed_methods = buildArch``. Anybody
is allowed to create this type of task (and download tarball).

.. warning::
  Don't forget that this type of task can generate huge amount of data, so use
  it wisely.

TODO
----
 * Separate volume/directory on hub
 * garbage collector + policy for retaining generated tarballs

Sidetag
=======

Sidetag plugin is originally work of Mikolaj Izdebski and was pulled into base
koji due to easier integration with rest of the code.

It is used for managing `sidetags` which are light-weight short-lived build tags
for developer's use. Sidetag creation is governed by hub's policy.

Hub
---

Example for `/etc/koji-hub/hub.conf`:

.. code-block:: ini

    PluginPath = /usr/lib/koji-hub-plugins
    Plugins = sidetag_hub

    [policy]
    sidetag =
        # allow maximum of 10 sidetags per user for f30-build tag
        tag f30-build && compare number_of_tags <= 10 :: allow
        # forbid everything else
        all :: deny

    package_list =
        # allow blocking for owners in their sidetags
        match action block && is_sidetag_owner :: allow
        all :: deny

There are two special policy tests `is_sidetag` and `is_sidetag_owner` with
expectable behaviour.

Now Sidetag Koji plugin should be installed.  To verify that, run
`koji list-api` command -- it should now display `createSideTag`
as one of available API calls.

Plugin has also its own configuration file
``/etc/koji-hub/plugins/sidetag.conf`` which for now contains the only boolean
option ``remove_empty``. If it is set, sidetag is automatically deleted when
last package is untagged from there.

CLI
---

For convenient handling, also CLI part is provided. Typical session would look
like:

.. code-block:: shell

   $ koji add-sidetag f30-build --wait
   f30-build-side-123456
   Successfully waited 1:36 for a new f30-build-side-123456 repo

   $ koji remove-sidetag f30-build-side-123456

API
---
And in scripts, you can use following calls:

.. code-block:: python

    import koji
    ks = koji.ClientSession('https://koji.fedoraproject.org/kojihub')
    ks.gssapi_login()
    ks.createSideTag('f30-build')
