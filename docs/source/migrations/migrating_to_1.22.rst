Migrating to Koji 1.22
======================

You should consider the following changes when migrating to 1.22:

DB Updates
----------

There are two minor schema changes in this release.

* we've updated all ``timestamp`` fields to ``timestamptz`` with the return value of
  ``get_event_time()`` function to avoid unexpected time offset caused by PostgreSQL timezone
  setting (`PR#2237 <https://pagure.io/koji/pull-request/2237>`_).
* we've updated the ``sessions_active_and_recent`` index for the ``session`` table for better
  performance (`PR#2334 <https://pagure.io/koji/pull-request/2334>`_)

As in previous releases, we provide a migration script that updates the database.

::

    # psql koji koji < /usr/share/doc/koji/docs/schema-upgrade-1.21-1.22.sql


Dropped python2 support of hub and web
--------------------------------------

Python 2 was `sunset <https://www.python.org/doc/sunset-python-2/>`_ on January 1, 2020.
Starting with Koji 1.22, hub and web will only support Python 3.
The CLI, builder, and utils retain Python 2 support for now.
For more information see: `PR#2218 <https://pagure.io/koji/pull-request/2218>`_

.. _migration_krbv:

Dropped krbV authentication support
-----------------------------------

We have dropped all the code related to the old python-krbV library, and are now only
providing GSSAPI auth.
For ``ClientSession`` objects, ``krb_login()`` is redirected to
``gssapi_login()`` with a printed warning.
Any code still calling ``krb_login()`` directly should be updated.

The newer gssapi authentication mechanism requires either ``python-requests-kerberos`` or
``python-requests-gssapi``.

For more information see: `PR#2244 <https://pagure.io/koji/pull-request/2244>`_ and
`PR#2280 <https://pagure.io/koji/pull-request/2280>`_

As part of this, the ``krbservice`` and ``krb_rdns`` options have been dropped.
These options were accepted in several configuration files and also as command
line options (``--krbservice`` and ``--krb-rdns``) in the cli and some utility
scripts.
In the Web UI configuration (``web.conf``), these options were named
``KrbService`` and ``KrbRDNS``.
Users and admins should remove these options from their configuration.

These options will cause an error if given on the command line.
They will also cause an error if used in the following configuration files:

* kojid.conf
* kojira.conf


Other changes
-------------

There are numerous other changes in 1.22 that should not have a direct impact on migration. For
details see: :doc:`../release_notes/release_notes_1.22`
