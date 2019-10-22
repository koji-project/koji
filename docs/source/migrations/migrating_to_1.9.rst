Migrating to Koji 1.9
=====================

.. reStructured Text formatted

The 1.9 release of Koji includes a few changes that you should consider when
migrating.

DB Updates
----------

ImageFactory support introduced some new archive types. These have been added to
the ``archivetypes`` table. The inaccurate ``vmx`` entry has been removed.

As in previous releases, we provide a migration script that updates the
database.

::

    # psql koji koji  </usr/share/doc/koji-1.9.0/docs/schema-upgrade-1.8-1.9.sql


Command line changes
--------------------

The command line interface handles configuration files a little differently. Old
configs should work just fine, but now there are new options and enhancements.

In addition to the main configuration files, the koji cli now checks for
``/etc/koji.conf.d`` and ``~/.koji/config.d`` directories and loads any
``*.conf`` files contained within. Also if the user specifies a directory with
the ``-c/--config`` option, then that directory will be processed similarly.

The command line supports a new ``-p/--profile`` option to select alternate
configuration profiles without having to link or rename the koji executable.

The new ``image-build`` command is used to generate images using ImageFactory.
The older spin-appliance command is now deprecated.

The ``mock-config`` command no longer requires a name argument. You can still
specify one
if you want to override the default choice. It also supports new options. The
``--latest`` option causes the resulting mock config to reference the
``latest`` repo (a varying symlink). The ``--target`` option allows generating
the config from a target name.

Other command line changes include:
* a new ``download-logs`` command
* the ``list-groups`` command now accepts event args
* the ``taginfo`` command now reports the list of comps groups for the tag
* the fast upload feature is now used automatically if the server supports it

Other Configuration changes
---------------------------

There are also some minor configuration changes in other parts of Koji.

In ``kojid`` the time limit for rpm builds is now configurable via the
``rpmbuild_timeout`` setting in ``kojid.conf``. The default is 24 hours.

The ``koji-gc`` tool supports two new configuration options. The ``krbservice``
option allows you to specify the kerberos service for authentication, and the
``email_domain`` option allows you to specify the email domain for sending gc
notices.

The messagebus hub plugin now supports ``timeout`` and ``heartbeat`` options
for the message bus connection.


RPC API Changes
---------------

Most of these changes are extensions, though some of the host-only call
changes are incompatible.

The ``tagHistory`` call accepts a new named boolean option (``active``) to
select only active/inactive entries. It also now reports the additional fields
``maven_build_id`` and ``win_build_id`` if builds are maven or win builds
respectively.

New rpc calls: ``buildImageOz``, ``host.completeImageBuild``, and
``host.evalPolicy``.

The host-only calls ``host.moveImageBuildToScratch`` and ``host.importImage``
no longer accept the ``rpm_results`` argument. The rpm results can be embedded
in the regular ``results`` argument.
