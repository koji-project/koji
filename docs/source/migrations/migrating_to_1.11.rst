Migrating to Koji 1.11
======================

.. reStructured Text formatted

The 1.11 release of Koji includes a several changes that you should consider when
migrating.

DB Updates
----------

There are a number of new tables and columns to support content generators. Here is a summary:
    * The ``btype`` table tracks the known btypes [LINK] in the system
    * The ``build_types`` table links builds to their btype(s)
    * The ``content_generator`` table tracks the known content generators in the system
    * The ``cg_users`` table tracks which users have access to which content generators
    * The ``buildroot`` table now tracks more generic buildroots
    * The ``standard_buildroot`` table tracks data for "normal" koji buildroots
    * Several tables now have an ``extra`` column that stores json data
    * There are several new entries in the ``archivetypes`` table
    * The ``image_listing`` table has been replace by the more general ``archive_rpm_components`` table
    * The new ``archive_components`` complements this and tracks non-rpm components

As in previous releases, we provide a migration script that updates the
database.

::

    # psql koji koji  </usr/share/doc/koji-1.11.0/docs/schema-upgrade-1.10-1.11.sql

Note: prior to this release, we had some interim update scripts:
    * schema-update-cgen.sql
    * schema-update-cgen2.sql

Most users should not need these scripts. The new schema upgrade script includes
those changes.


Command line changes
--------------------

The ``help`` command now shows a categorized list of commands.

The ``hello`` command now reports the authentication type.

Several commands support new arguments. Here are the notable changes:

``add-tag``
    * ``--extra``       : Set an extra option for tag at creation

``watch-task``
    * Supports several new task selection options

``download-build``
    * ``--rpm``         : Used to download a particular rpm by name

``runroot``
    * ``--new-chroot``  : Run command with the --new-chroot (systemd-nspawn) option to mock


And there are five new commands

* ``assign-task``
* ``import-cg``
* ``grant-cg-access``
* ``revoke-cg-access``
* ``spin-livemedia``


Client configuration options
----------------------------

The command line and several other tools support the following new configuration options:
    * ``use_old_ssl``   : Use the old ssl code instead of python-requests
    * ``no_ssl_verify``   : Disable certificate verification for https connections
    * ``upload_blocksize`` : Override the blocksize for uploads

The ``ca`` option is deprecated and no longer required for ssl authentication (``serverca`` is still required).

Even if not using ssl authentication, the ``serverca`` option, if specified, is used to verify the certificate of the
server.


Other Configuration changes
---------------------------

The Koji web interface supports the following new configuration options:
    * ``KrbRDNS``       : Use the fqdn of the server when authenticating via kerberos
    * ``LoginDisabled`` : Hide the login link at the top of the page


RPC API Changes
---------------

New rpc calls:
    * ``CGImport``      : Used by content generators
    * ``getBuildType``  : Returns typeinfo for a build
    * ``listBTypes``    : List the known btypes for the system
    * ``addBType``      : Adds a new btype
    * ``grantCGAccess`` : Grants a user content generator access
    * ``revokeCGAccess`` : Revokes content generator access

Changes to calls
    * Several information calls now return additional fields
    * ``getRPMDeps`` returns optional deps
    * ``listTasks`` supports new selection options
    * ``getLoggedInUser`` includes an authtype field
