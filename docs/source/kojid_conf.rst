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
      noop - it is still alowed in config file for backward compatibility.

   log_level=None
      Numeric setting of standard logging levels.

   maxjobs=10
      The maximum number of jobs that kojid will handle at a time. This
      servers as a backup to the capacity check and prevents a tremendous
      number of low weight jobs from piling up.

   max_retries=120
      If hub is inaccessible, try for this many times, before kojid will die.

   minspace=8192
      The minimum amount of free space (in MBs) required for each build root.
      If such amount of space is not available, new job will not be taken.

   no_ssl_verify=False
      Turn off SSL verification for https calls. It is strongly advised to
      not turn off this verification.

   offline_retry=True
      Should builder continue to work, if server returns offline message?

   offline_retry_interval=120
      If server returned offline response (running upgrade, etc.), try after
      this many seconds.

   pkgurl=None
      Obsoleted, use ``topurl`` instead.

   plugin=''
   plugins=''
      Space-separated list of builder plugins which should be enabled. By
      default no plugins are used. For list of available plugins check
      :doc:`this page <plugins>`. Both spellings plugin/plugins are allowed
      in config, but don't mix them as order is not binding.

   pluginpath=/usr/lib/koji-builder-plugins
      Double-colon-separated list of directories, where builder plugins are.
      They are not used by default, use ``plugins`` to enable them

   retry_interval=60
      If there is unsuccessful call to hub, this is how many seconds are
      waited before trying new call.

   server=http://hub.example.com/kojihub
      The URL for the koji xmlrpc server.

   sleeptime=15
      The number of seconds to sleep between checking for new tasks.

   topdir=/mnt/koji
      The directory root where work data can be found from the koji hub.

   topurl=http://hub.example.com/kojifiles
      The URL for the file access.

   use_fast_upload=True
      Enables faster uploading (bypassing XMLRPC overload). Changing it makes
      sense only in weird combination of very old hub and newer builders.

   workdir=/tmp/koji
      The directory root for temporary storage on builder.

Building
^^^^^^^^
.. glossary::
   allowed_scms=scm.example.com:/cvs/example git.example.org:/example svn.example.org:/users/\*:no
      A space-separated list of tuples from which kojid is allowed to checkout.
      The format of those tuples is:

      .. code::

          host:repository[:use_common[:source_cmd]]

      Incorrectly-formatted tuples will be ignored.

      If ``use_common`` is not present, kojid will attempt to checkout a ``common/``
      directory from the repository.  If ``use_common`` is set to ``no``, ``off``, ``false``, or ``0``,
      it will not attempt to checkout a ``common/`` directory.

      ``source_cmd`` is a shell command (args separated with commas instead of spaces)
      to run before building the srpm. It is generally used to retrieve source
      files from a remote location.  If no ``source_cmd`` is specified, ``make sources``
      is run by default.

   build_arch_can_fail=False
      If set to ``True``, failing subtask will not automatically cancel other siblings.

   createrepo_skip_stat=True
      If set to ``True``, append ``--skip-stat`` to all createrepo commands.

   createrepo_update=True
      Recycle old repodata (if they exist) in createrepo.

   failed_buildroot_lifetime=14400
      Failed tasks leave buildroot content on disk for debugging purposes.
      They are removed after 4 hours by default.

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
      means using the number in ``/etc/oz/oz.cfg``, supported since oz-0.16.0.

   use_createrepo_c=False
      Use ``createrepo_c`` rather than ``createrepo`` command. There is
      generally no reason to not use createrepo_c in modern depolyments. It
      is disabled by default only to be backward-compatible. This default
      would change in future.

   task_avail_delay=300
      If there is more builders in same bin (combination of channel and
      arch), wait for this time before taking the task. It allows to better
      spread workload.

   timeout=None
      This value is used for waiting on all xmlrpc calls to hub. By default
      there is no timeout set.

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
      When building SRPM, directory ``SOURCES`` is expected in buildroot. If
      it is not specified or directory does not exist, fallback is
      buildroot's directory itself. Generally it is a ``--sources`` option to
      ``rpmbuild``.

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
      The user to run as when doing builds. Note, that user must exist on
      builder.

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

User Authentication
^^^^^^^^^^^^^^^^^^^
Please use Kerberos or SSL authentication instead. It is more meant as a
development authentication mode, than for real-world setting.

.. glossary::
   user=None
       Username for authentication
   password=None
       Clear-text password (I've told you.)

Kerberos Authentication
^^^^^^^^^^^^^^^^^^^^^^^
.. glossary::
   ccache=/var/tmp/kojid.ccache'
      Credentials cache used for krbV login.

   host_principal_format=compile/\%s\@EXAMPLE.COM
      The format of the principal used by the build hosts
      %s will be replaced by the FQDN of the host.

   keytab=/etc/kojid/kojid.keytab
      Location of the keytab.

   krb_canon_host=False
      Kerberos authentication needs correct hostname. If this option is
      specified, dnf resolver is used to get correct hostname. Note, that in
      such case you need additional package ``python-dns`` installed.

   krb_principal=None
      Explicit principal used for login. If it is not specified, it is
      created via ``host_principal_format``.

   krb_rdns=True
      Kerberos authentication needs correct hostname. If this option is
      specified, ``socket.getfqdn(host)`` is used to determine reverse DNS
      records. Otherwise, ``host`` is used directly. Playing with this option
      can help you in some firewalled setups.

   krbservice=host
      The service name of the principal being used by the hub.


SSL Authentication
^^^^^^^^^^^^^^^^^^
.. glossary::
   ca=''
      noop, obsoleted, will be removed soon.

   cert=/etc/kojid/client.crt
      Client certificate.

   serverca=/etc/kojid/serverca.crt
      Certificate of the CA that issued the HTTP server certificate
