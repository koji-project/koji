=======
Plugins
=======

Following plugins are available in default koji installation.

Runroot
=======

Plugin for running any command in buildroot. It has three parts as most of the
others (hub, builder and CLI).

Builder
-------
You enable plugin by editing ``/etc/kojid.conf`` by adding ``plugin = runroot``
there. Plugin itself has separate configuration file on each builder located at
``/etc/kojid/plugins/runroot.conf`` There is a sample configuration file
with option descriptions installed.

Hub
---
On the hub side ``Plugins = runroot_hub`` needs to be added to
``/etc/koji-hub/hub.conf``. Note, that by default policy runroot tasks are
assigned to ``runroot`` channel. As this is a plugin, we don't create it
automatically. There are three options - create channel when adding first builder
there via ``koji add-host-to-channel --new hostname runroot`` or by changing the
default channel policy according to :doc:`defining_hub_policies`. Last option is
to use ``--channel-override`` option in CLI to drive task to channel of choice.

CLI
---
CLI is looking for available plugins every run, so it if it is installed, you'll
see new command ``runroot`` with options described in its help. No config
options are needed to enable it.

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
``/etc/koji-hub/plugins/sidetag.conf`` which contains following options:

.. glossary::
   remove_empty = off
       If this is set, sidetag is automatically deleted when
       last package is untagged from there.

   allowed_suffixes =
       List of strings delimited by commas. These suffixes are then allowed to
       be requested via ``createSideTag``

   name_template = {basetag}s-side-{tag_id}d
       Python string template to be used for generation of sidetag name. It needs
       to contain both basetag/tag_id placeholders.

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

.. _protonmsg-config:

Proton messaging
================

The ``protonmsg`` plugin for the hub will, if enabled, send a wide range of
messages about Koji activity to the configured amqps message brokers.
Most callback events on the hub are translated into messages.

In order to enable this plugin, you must:

* add ``protonmsg`` to the ``Plugins`` setting in ``/etc/koji-hub/hub.conf``

* provide a configuration file for the plugin at
  ``/etc/koji-hub/plugins/protonmsg.conf``

The configuration file is ini-style format with three sections: broker,
queue and message.
The ``[broker]`` section defines how the plugin connects to the message bus.
The following fields are understood:

* ``urls`` -- a space separated list of amqps urls. Additional urls are
  treated as fallbacks. The plugin will send to the first one that accepts
  the message
* ``cert`` -- the combined client cert and key file for authenticating koji to
  the broker.
* ``cacert`` -- the CA certificate to verify the broker server TLS connection
* ``topic_prefix`` -- Koji uses this string as a prefix for all message
  topics. For example, if you choose ``topic://koji``, then Koji
  will publish messages on ``topic://koji.package.add`` when an user runs
  ``kojidev add-pkg`` etc. Use ``topic://`` prefixes for ActiveMQ brokers,
  ``/topic/`` for RabbitMQ brokers.
* ``connect_timeout`` -- the number of seconds to wait for a connection before
  timing out
* ``send_timeout`` -- the number of seconds to wait while sending a message
  before timing out

The ``[message]`` section sets parameters for how messages are formed.
Currently only one field is understood:

* ``extra_limit`` -- the maximum allowed size for ``build.extra`` fields that
  appear in messages. If the ``build.extra`` field is longer (in terms of 
  json-encoded length), then it will be omitted. The default value is ``0``
  which means no limit.

The ``[queue]`` section controls how (or if) the plugin will use the database
to queue messages when they cannot be immediately sent.
The following fields are understood:

* ``enabled`` -- if true, then the feature is enabled
* ``batch_size`` -- the maximum number of queued messages to send at one time
* ``max_age`` -- the age (in hours) at which old messages in the queue are discarded

It is important to note that the database queue is only a fallback mechanism.
The plugin will always attempt to send messages as they are issued.
Messages are only placed in the database queue when they cannot be immediately
sent on the bus (e.g. if the amqps server is offline).

Admins should consider the balance between the ``batch_size`` and
``extra_limit`` options, as both can affect the total amount of data that the
plugin could attempt to send during a single call.


Image builds using Kiwi
=======================

**This is just a tech-preview. API/usage can drastically change in upcoming
releases**

Plugin for creating images via `kiwi <http://osinside.github.io/kiwi/>`_
project. Minimal supported version of kiwi is ``kiwi-9.24.2``.

All three parts (cli/hub/builder) needs to be installed. There is currently no
configuration except allowing the plugins (name is 'kiwi' for all components).

Builders don't need to have any specific library installed (kiwi
invocation/usage is only in buildroots not on builder itself). (Temporarily
``python3-kiwi`` needs to be installed on builder for kojid to be able to parse
kiwi output. It will be changed to json in next version and this requirement
will be dropped.)

``image`` channel is the default one and ``channel`` policy can be used to
request other channel for this type of tasks as usual.

Buildtag needs to be configured by adding special group ``kiwi`` which should
contain at least ``kiwi-cli``, potentially ``jing`` for better description files
validation and any ``kiwi-systemdeps-*`` packages for requested image types. So,
most simple configuration will look like:

.. code-block:: shell

   $ koji add-group kiwi-build-tag kiwi-build
   $ koji add-group-pkg kiwi-build-tag kiwi-build kiwi-cli kiwi-systemdeps

Another thing we need to ensure is that we're building in chroot and not in
container.

.. code-block:: shell

   $ koji edit-tag kiwi-build-tag -x mock.new_chroot=False

Calling the build itself is a matter of simple CLI call:

.. code-block: shell

   $ koji kiwi-build kiwi-target git+https://my.git/image-descriptions#master my_image_path

Selecting other than default kiwi profile can be done by ``--kiwi-profile``
option. Similarly to other image tasks, alternative architecture failures can be
ignored for successful build by ``--can-fail`` option. ``--arch`` can be used to
limit build tag architectures.
