Migrating to Koji 1.22
======================

You should consider the following changes when migrating to 1.22:

DB Updates
----------

There are no big database schema changes in this release.

We've updated all ``timestamp`` fields to ``timestamptz`` with the return value of
``get_event_time()`` function to avoid unexpected time offset caused by PostgreSQL timezone setting
(`PR#2237 <https://pagure.io/koji/pull-request/2237>`_) and regenerate
``sessions_active_and_recent`` index for ``session`` table for better performance (`PR#2334
<https://pagure.io/koji/pull-request/2334>`_)

As in previous releases, we provide a migration script that updates the database.

::

    # psql koji koji < /usr/share/doc/koji/docs/schema-upgrade-1.21-1.22.sql


Dropped python2 support of hub and web
--------------------------------------

As Python2 has retired since Jan 1, 2020, we are now only providing python3 hub and web since koji
1.22. CLI, builder, and utils are not impacted. (`PR#2218
<https://pagure.io/koji/pull-request/2218>`_)


Dropped krbV authentication support
-----------------------------------

As python-krbV is for python2 only, we dropped all the code related to krbV, and are now only
providing GSSAPI auth. For ``ClientSession`` object, ``krb_login()`` is redirected to
``gssapi_login()`` now, and you'd better change your client code to call the latter directly. Making
sure you have ``python-requests-kerberos`` installed on old client with koji 1.22 hub. (`PR#2244
<https://pagure.io/koji/pull-request/2244>`_)


Other changes
-------------

There are numerous other changes in 1.22 that should not have a direct impact on migration. For
details see: :doc:`../release_notes/release_notes_1.22`
