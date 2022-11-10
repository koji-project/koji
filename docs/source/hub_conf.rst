Hub Configuration Options
-------------------------
The hub can be configured via one or more ini-style configuration files.
Options below should be placed in the ``[hub]`` section of these files.

These files can also contain a ``[policy]`` section for configuring policies.
This is described in :doc:`policy <defining_hub_policies>`.

File locations
^^^^^^^^^^^^^^

By default, koji-hub will read a primary configuration file at
``/etc/koji-hub/hub.conf`` and any number of supplemental configuration
files in the ``/etc/koji-hub/hub.conf.d`` directory.
Options in the primary configuration file take precedence in case of duplication.

If needed, these locations can be changed by setting the environment variables
``koji.hub.ConfigFile`` and ``koji.hub.ConfigDir`` respectively, e.g. by using
the SetEnv directive in the httpd configuration.

A common pattern is to place policy rules and/or sensitive values in separate configuration
files.


File permissions
^^^^^^^^^^^^^^^^

Note some configuration options (e.g. database password) are sensitive values.
Our default packaging installs ``hub.conf`` with 0640 root/apache file permissions.
If you're installing some other way, we recommend that you double-check these permissions.

Basic options
^^^^^^^^^^^^^
.. glossary::
   DBName
      Type: string

      Default: ``None``

      The name of the database that the hub should connect to.

   DBHost
      Type: string

      Default: ``None``

      The hostname that the database is running on.

      Note: If your database server is running locally and you would like to connect
      via Unix socket instead of TCP, then omit the ``DBHost`` and ``DBPort`` options.
      If you set ``DBHost`` to ``localhost``, then the connection will be over TCP.

   DBPort
      Type: string

      Default: ``None``

      The port to use when connecting to the database over TCP.

   DBUser
      Type: string

      Default: ``None``

      The database user to connect as.

   DBPass
      Type: string

      Default: ``None``

      The password for connecting to the database.

      Please ensure that your hub configuration file(s) have appropriate file permissions
      before placing sensitive data in them.

   DBConnectionString
      Type: string

      Default: ``None``

      The connection string (dsn) for connecting to the database.
      This overrides the other ``DB*`` options.
      This value is passed through to psycopg2 and would typically look something like:
      ``dbname=koji user=koji host=db.example.com port=5432 password=example_password``

   KojiDir
      Type: string

      Default: ``/mnt/koji``

      This is the root directory for koji files.

The database connection can be specified either by the single ``DBConnectionString``
option, or by other individual ``DB*`` options.
If given, the ``DBConnectionString`` option takes precedence.

General authentication options
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.. glossary::
   CheckClientIP
      Type: boolean

      Default: ``True``

      Use user IP in session management.

   LoginCreatesUser
      Type: boolean

      Default: ``True``

      Whether or not to automatically create a new user from valid ssl or gssapi credentials.

GSSAPI authentication options
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

The following options control aspects of authentication when using ``mod_auth_gssapi``.

.. glossary::
   ProxyPrincipals
      Type: string

      Default: ``None``

      A comma separated list of principals that are allowed to perform proxy authentication.
      This ability is only intended for kojiweb.

   HostPrincipalFormat
      Type: string

      Default: ``None``

      This format string is used to set the principal when adding new hosts.
      The ``%s`` is expanded to the hostname.
      If a specific principal is given to the ``add-host`` command then this option
      is not used.

   AllowedKrbRealms
      Type: string

      Default: ``*``

      Allowed Kerberos Realms. The default value "*" indicates any Realm is allowed.
      This is a comma separated list.

   DisableGSSAPIProxyDNFallback
      Type: boolean

      Default: ``False``

      If True, enables backwards compatible behavior in the handling of the ``ProxyDNs``
      option.
      The default value of False is recommended.

   DisableURLSessions
      Type: boolean

      Default: ``False``

      If set to ``False``, it enables older clients to log in via session parameters
      encoded in URL. New behaviour uses header-based parameteres. This default
      will be changed in future to ``True`` effectively disabling older clients. It is
      encouraged to set it to ``True`` as soon as possible when no older clients are
      using the hub. (Added in 1.30, will be removed in 1.34)

Enabling gssapi auth also requires settings in the httpd config.

SSL client certificate auth configuration
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
If using SSL auth, these settings need to be valid and in line with other services configurations
for kojiweb to allow logins.

.. glossary::
   DNUsernameComponent
      Type: string

      Default: ``CN``

      The client username is the common name of the subject of their client certificate.

   ProxyDNs
      Type: string

      Default: ``''``

      If specified, the given DNs are allowed to perform proxy authentication.
      This ability is only intended for kojiweb.
      Multiple DNs can be separated with the vertical bar character, ``|``.

Enabling ssl auth also requires editing the httpd config (conf.d/kojihub.conf).

Notification options
^^^^^^^^^^^^^^^^^^^^
.. glossary::
   KojiWebURL
      Type: string

      Default: ``http://localhost.localdomain/koji``

      This specifies the URL address of Koji web.
      This setting affects the links that appear in notification messages.

   EmailDomain
      Type: string

      Default: ``None``

      Email domain name that koji will append to usernames when creating email notifications.

   NotifyOnSuccess
      Type: boolean

      Default: ``True``

      Whether to send the task owner and package owner email or not on success.
      This still goes to watchers.

   DisableNotifications
      Type: boolean

      Default: ``False``

      Disables all notifications

For more on notifications in Koji, see :ref:`notification-basics`

Resource limits
^^^^^^^^^^^^^^^
If configured, the following resource limits are applied by the hub at startup.
Each value defaults to ``None``, meaning no limit is applied.
If given, the value should be either a single integer or a pair of integers separated by whitespace.

If a pair of integers is given, this sets both the soft and hard limits for the resource.
If a single integer is given, only the soft limit is set.

.. glossary::
   RLIMIT_AS
      Type: string

      Default: ``None``

      This is the maximum size of the process's virtual memory (address space).
      The limit is specified in bytes, and is rounded down to the system page size.

   RLIMIT_CORE
      Type: string

      Default: ``None``

      This is the maximum size of a core file in bytes that the process may dump.
      When 0, no core dump file are created. When nonzero, larger dumps are truncated to this size.

   RLIMIT_CPU
      Type: string

      Default: ``None``

      This is a limit, in seconds, on the amount of CPU time that the process can consume.

   RLIMIT_DATA
      Type: string

      Default: ``None``

      This is the maximum size of the process's data segment (initialized data,
      uninitialized data, and heap). The limit is specified in bytes,
      and is rounded down to the system page size.

   RLIMIT_FSIZE
      Type: string

      Default: ``None``

      This is the maximum size in bytes of files that the process may create.

   RLIMIT_MEMLOCK
      Type: string

      Default: ``None``

      This is the maximum number of bytes of memory that may be  locked into RAM.
      This limit is in effect rounded down to the nearest multiple of the system page size.

   RLIMIT_NOFILE
      Type: string

      Default: ``None``

      This specifies a value one greater than the maximum file descriptor number that
      can be opened by this process.

   RLIMIT_NPROC
      Type: string

      Default: ``None``

      This is a limit on the number of extant process (or, more precisely on Linux, threads)
      for the real user ID of the  calling process.

   RLIMIT_OFILE
      Type: string

      Default: ``None``

      This specifies a value one greater than the maximum file descriptor number that
      can be opened by this process. This limit was on BSD.

   RLIMIT_RSS
      Type: string

      Default: ``None``

      This is a limit (in bytes) on the process's resident set (the number of virtual pages resident in RAM).

   RLIMIT_STACK
      Type: string

      Default: ``None``

      This is the maximum size of the process stack, in bytes.

Additionally, the following options govern resource-related behavior.

.. glossary::
   MemoryWarnThreshold
      Type: int

      Default: ``5000``

      If memory consumption rises more than this value (in kilobytes) while handling a single
      request, a warning will be emitted to the log

   MaxRequestLength
      Type: int

      Default: ``4194304``

      This sets the maximum request length that the hub will process.
      If a longer request is encountered, the hub will stop reading it and return an error.

Extended features
^^^^^^^^^^^^^^^^^
Koji includes limited support for building via Maven or under Windows.

.. glossary::
   EnableMaven
      Type: boolean

      Default: ``False``

      This option enables support for building with Maven.

   EnableWin
      Type: boolean

      Default: ``False``

      This option enables support for :doc:`Windows builds <winbuild>`.

Koji hub plugins
^^^^^^^^^^^^^^^^
The hub supports plugins, which are loaded from the ``PluginPath`` directory.

.. glossary::
   PluginPath
      Type: string

      Default: ``/usr/lib/koji-hub-plugins``

      The path where plugins are found.

   Plugins
      Type: string

      Default: ``''``

      A space-separated list of plugins to load.
      Each entry should be the name of a plugin file (without the ``.py``).
      Only plugins from the configured ``PluginPath`` can be loaded.

Koji debugging
^^^^^^^^^^^^^^
The following options are primarily intended for debugging Koji's behavior.

.. glossary::
   KojiDebug
      Type: boolean

      Default: ``False``

      If KojiDebug is on, the hub will be /very/ verbose and will report exception details to
      clients for anticipated errors (i.e. koji's own exceptions -- subclasses of koji.GenericError).

      This option is only intended for specialized debugging and should be left off in production
      environments.

   KojiTraceback
      Type: string

      Default: ``None``

      This determines how much detail about exceptions is reported to the client (via faults).
      The meaningful values are:

      * normal - a basic traceback (format_exception)
      * extended - an extended traceback (format_exc_plus)

      If left unset, the default behavior is to omit the traceback and just report the error
      class and message.

      Note: the extended traceback is intended for debugging only and should NOT be used in production,
      since it may contain sensitive information.

   LogLevel
      Type: string

      Default: ``WARNING``

      This option controls the log level the hub logs.
      Koji uses the standard Python logging module and the standard log level names.

      Setting multiple log levels for different parts of the hub code is possible.
      The option is treated as a space-separated list log level directives, which
      can be either a single log level name (sets the default log level) or a
      logger:level pair (sets the log level for the given logger namespace).

      For example, you could set:

         ``LogLevel = INFO koji.db:DEBUG``

      To see debug logging only for the db module.

   LogFormat
      Type:string

      Default: ``%(asctime)s [%(levelname)s] m=%(method)s u=%(user_name)s p=%(process)s r=%(remoteaddr)s %(name)s: %(message)s``

      This sets the log format string for log messages issued by the hub code.
      In addition to the normal values available from the logging module, the hub's log formatter provides:

      * method -- the method name for the call being processed
      * user_id -- the id of the user making the call
      * user_name -- the name of the user making the call
      * session_id -- the session_id of the call
      * callnum -- the callnum value for the session
      * remoteaddr -- the ip address and port (colon separated) that the call is coming from

Hub Policy
^^^^^^^^^^
.. glossary::
   VerbosePolicy
      Type: boolean

      Default: ``False``

      If VerbosePolicy (or KojiDebug) is on, 'policy violation' messages will report the
      policy rule which caused the denial.

   MissingPolicyOk
      Type: boolean

      Default: ``True``

      If MissingPolicyOk is on, and a given policy is not defined, the policy check will return
      'allow', otherwise such cases will result in 'deny'.

Koji outages options
^^^^^^^^^^^^^^^^^^^^
These options are intended for planned outages.

.. glossary::
   ServerOffline
      Type: boolean

      Default: ``False``

      If ServerOffline is True, the server will always report a ServerOffline fault
      (with OfflineMessage as the fault string).

   OfflineMessage
      Type: string

      Default: ``None``

      This controls the error message that is reported when ``ServerOffline`` is set.

   LockOut
      Type: boolean

      Default: ``False``

      If Lockout is True, the server will report a ServerOffline fault for most non-admin requests.

Name verification
^^^^^^^^^^^^^^^^^
Currently we have two groups for name verification:
 - internal names
 - user names

Group internal names is currently used for:
 - archive type
 - btype
 - channel
 - external repo
 - group
 - host
 - kerberos
 - permission
 - tag
 - target
 - volume

Group user names is currently used for:
 - user
 - host

Host names are listed in both groups because hosts always have an associated user entry.

.. glossary::
   MaxNameLengthInternal
      Type: string

      Default: ``256``

      Set length of internal names. By default there is allowed length set up to 256.
      When length is set up to 0, length verifying is disabled.

   RegexNameInternal
      Type: string

      Default: ``^[A-Za-z0-9/_.+-]+$``

      Set regex for verify an internal names. When regex string is empty, verifying
      is disabled.

   RegexUserName = ^[A-Za-z0-9/_.@-]+$
      Type: string

      Default: ``^[A-Za-z0-9/_.@-]+$``

      Set regex for verify a user name and kerberos. User name and kerberos have
      in default set up allowed '@' and '/' chars on top of basic name regex
      for internal names. When regex string is empty, verifying is disabled.
