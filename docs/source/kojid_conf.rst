kojid.conf Options
------------------
kojid.conf is standard .ini-like configuration file. Its main section is
called ``[kojid]`` and contains following options. They are split by function
to section but can occur anywhere in ``[kojid]`` section in config file.

General
^^^^^^^
.. glossary::
   chroot_tmpdir=/chroot_tmpdir
      The temporary directory in buildroot. It is advised to not use ``/tmp``
      as it is bound in mock and its content would change in random moments
      during the build process.

   keepalive=True
      noop - it is still allowed in config file for backward compatibility.

   log_level=None
      Set logging level to one of the standard level names in Python's logging
      module. Valid values are: CRITICAL, ERROR, WARNING, INFO, and DEBUG.
      The default log level is WARNING.

   maxjobs=10
      The maximum number of jobs that kojid will handle at a time. This
      serves as a backup to the capacity check and prevents a tremendous
      number of low weight jobs from piling up.

   max_retries=120
      Set the maximum number of times that an individual hub call can be
      retried.

   minspace=8192
      The minimum amount of free space (in MBs) required for each build root.
      If this amount of space is not available, no new jobs will be taken.

   no_ssl_verify=False
      Turn off SSL verification for https calls. It is strongly advised to
      not turn off this verification.

   offline_retry=True
      The hub returns a special error code when it is placed in offline
      mode or when the database is unavailable. This setting controls
      whether calls should be retried in these cases.

   offline_retry_interval=120
      Controls the wait time for retrying hub calls when the hub reports
      as offline. Such calls are only retried if the offline_retry setting
      is set to True. The value is in seconds.

   pkgurl=None
      Obsoleted, use ``topurl`` instead.

   plugin=''
   plugins=''
      Space-separated list of builder plugins which should be enabled. By
      default no plugins are used. For list of available plugins check
      :doc:`this page <plugins>`. Both spellings plugin/plugins are allowed
      in config, but don't mix them as order is not binding.

   pluginpath=/usr/lib/koji-builder-plugins
      Colon-separated list of directories to check for builder plugins.
      They are not used by default, use ``plugins`` to enable them.

   retry_interval=60
      If there is an unsuccessful call to hub, this is how many seconds to
      wait before trying new call.

   server=http://hub.example.com/kojihub
      The URL for the koji xmlrpc server.

   sleeptime=15
      The number of seconds to sleep between checking for new tasks.

   topurl=http://hub.example.com/kojifiles
      The URL where the main Koji volume can be accessed. The builder uses
      this url for most file access.

   topdir=/mnt/koji
      The location where the main Koji volume is mounted. This mount is
      mainly used during createrepo tasks, and should be read-only.

   use_fast_upload=True
      Enables faster uploading (bypassing XMLRPC overhead). Changing it makes
      sense only in weird combination of very old hub and newer builders.

   workdir=/tmp/koji
      The directory root for temporary storage on builder.

Building
^^^^^^^^
.. glossary::
   allowed_scms=scm.example.com:/cvs/example git.example.org:/example svn.example.org:/users/\*:no
      Controls which source control systems the builder will accept. It is a
      space-separated list of entries in one of the following forms:

      .. code::

          hostname:path[:use_common[:source_cmd]]
          !hostname:path


      Incorrectly-formatted tuples will be ignored.

      If ``use_common`` is not present, kojid will attempt to checkout a ``common/``
      directory from the repository.  If ``use_common`` is set to ``no``, ``off``, ``false``, or ``0``,
      it will not attempt to checkout a ``common/`` directory.

      ``source_cmd`` is a shell command (args separated with commas instead of spaces)
      to run before building the srpm. It is generally used to retrieve source
      files from a remote location.  If no ``source_cmd`` is specified, ``make sources``
      is run by default.

      The second form (``!hostname:path``) is used to explicitly block a host:path
      pattern. In particular, it provides the option to block specific subtrees of
      a host, but allow from it otherwise. This explicit block syntax was added in
      version 1.13.0.


   build_arch_can_fail=False
      If set to ``True``, failing subtask will not automatically cancel other siblings.

   createrepo_skip_stat=True
      If set to ``True``, append ``--skip-stat`` to all createrepo commands.

   createrepo_update=True
      Recycle old repodata (if they exist) in createrepo.

   failed_buildroot_lifetime=14400
      Failed tasks leave buildroot content on disk for debugging purposes.
      They are removed after 4 hours by default. This value is specified
      in seconds.

   literal_task_arches=''
      Space-separated list of globs (``fnmatch``) for architectures which
      will not be converted to canonical archs when choosing builder.

   log_timestamps=False
      If set to ``True`` additional logs with timestamps will get created and
      uploaded to hub. It could be useful for debugging purposes, but creates
      twice as many log files.

   maven_repo_ignore='\*.md5 \*.sha1 maven-metadata\*.xml _maven.repositories resolver-status.properties \*.lastUpdated'
      Space-separated globs of repo files which should be ignored when
      gathering maven result artifacts.

   oz_install_timeout=7200
      Install timeout in seconds for image build. Default value is 0, which
      means using the number in ``/etc/oz/oz.cfg``. Supported since oz-0.16.0.

   use_createrepo_c=False
      Use ``createrepo_c`` rather than ``createrepo`` command. There is
      generally no reason to not use createrepo_c in modern depolyments. It
      is disabled by default only to be backward-compatible. This default
      would change in future.

   task_avail_delay=300
      [Added in 1.17.0]

      This delay works around a deficiency in task scheduling. The default
      delay is 300 seconds. It is unlikely that admins will need to adjust
      this setting.

      Despite the name, this does not introduce any new delay compared to the
      old behavior. The setting controls how long a host will wait before
      taking a task in a given channel-arch “bin” when that host has an
      available capacity lower than the median for that bin. Previously, such
      hosts could wait forever.

   timeout=None
      This value is used for waiting on all xmlrpc calls to hub. By default
      there is no timeout set.

   xz_options=-z6T0
      Image builds with ``raw-xz`` type will use this setting when compressing
      the image. Default value is compromise between speed and resource usage.
      Only one option (not space-separated) is allowed here for now.

RPM Builds
^^^^^^^^^^
.. glossary::
   distribution=Koji
      The distribution to use in rpm headers. Value is propagated via macros
      to rpmbuild.

   packager=Koji
      The packager to use in rpm headers. Value is propagated via macros to
      rpmbuild.

   support_rpm_source_layout=True
      Originally, when building an SRPM from source control, Koji expected
      the contents to be flattened (e.g. the spec and sources files directly
      in the checkout directory). When this option is enabled (the default),
      Koji will also accept these contents in separate ``SPECS`` and
      ``SOURCES`` directories.

   vendor=Koji
      The vendor to use in rpm headers. Value is propagated via macros to
      rpmbuild.

Mock
^^^^
.. glossary::
   mockdir=/var/lib/mock
      The directory root for mock.

   mockhost=koji-linux-gnu
      The _host string to use in mock.

   mockuser=kojibuilder
      The user to run as when performing builds. Note, that user must exist on
      the build host and must have permission to use mock.

   rpmbuild_timeout=86400
      Timeout for build duration (24 hours). Propagated to mock, not
      controlled by koji directly.

   yum_proxy=None
      Address of proxy server which will be passed via mock to yum.

Notifications
^^^^^^^^^^^^^
.. glossary::
   admin_emails=''
      Space-separated list of addresses for sending logs.

   from_addr=Koji Build System <buildsys@example.com>
      The From address used when sending email notifications.

   smtphost=example.com
      The mail host to use for sending email notifications.

Kerberos Authentication
^^^^^^^^^^^^^^^^^^^^^^^
.. glossary::
   ccache=/var/tmp/kojid.ccache
      Credentials cache used for krbV login.

   host_principal_format=compile/\%s\@EXAMPLE.COM
      The format of the principal used by the build hosts.
      The %s will be replaced by the FQDN of the host.

   keytab=/etc/kojid/kojid.keytab
      Location of the keytab.


SSL Authentication
^^^^^^^^^^^^^^^^^^
.. glossary::
   ca=''
      noop, obsoleted, will be removed soon.

   cert=/etc/kojid/client.crt
      Client certificate.

   serverca=/etc/kojid/serverca.crt
      This specifies the CA (or CA bundle) that the builder should use to
      verify the ssl connection to the hub. If the default value of
      ``/etc/kojid/serverca.crt`` exists, then that file is used.
      Otherwise the default system bundle is used.


Insecure Authentication Options
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

These options are only intended for simple development environments
and should never be used in production.
Please use Kerberos or SSL authentication instead.

.. glossary::
   user=None
       Username for authentication

   password=None
       Clear-text password (I've told you.)
