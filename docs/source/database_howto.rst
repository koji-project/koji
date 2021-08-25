Database Howto
==============

For small to middle-sized deployments you should be ok with standard
distribution settings. Anyway, for larger one, it can start to be
problematic to deal with specific indices, disk space allocation, etc.
This section contains some useful practices to deal with such
problems.

Partitions
----------

Some tables - especially ``buildroot_listings`` and ``tasks`` can grow
in time and start to be problematic during backups, etc. One of the
solutions is to use partitioning feature of postgres.

It simply says, that one big table can be split to smaller ones (even
ending in different storages) while it is still transparent to
application. What could be tricky, is by which ranges tables should be
split. It is relatively easy for ``buildroot_listings``, where we
almost always query by ``buildroot_id``.

It has three steps - first is to backup your db and turn hub offline.

.. note::
    SQL syntax used here (PARTITION BY) is in Postgres from version 10.  Same
    behaviour can be made to work even with older releases but needs a bit of
    additional code to replace it.

Second is creating trigger, which will be used when new buildroot is
created and will ensure that potential new partition is created:

.. code-block:: plpgsql

  -- create_partition_and_insert trigger will be called anytime
  -- new buildroot is inserted to buildroot table. In such case,
  -- it is checked if it falls to existing partition or if new one needs to be created
  CREATE OR REPLACE FUNCTION create_partition_and_insert() RETURNS trigger AS
  $$
  DECLARE
    partition_start INTEGER;
    partition_end INTEGER;
    partition_size INTEGER;
    partition TEXT;
  BEGIN
    -- you can set it to any reasonable size, but it must be same
    -- number as later in buildroot_listing_partition
    partition_size = 1000000;
    partition_start := DIV(NEW.id, partition_size) * partition_size;
    partition_end := partition_start + partition_size;
    partition := 'buildroot_listing_' || partition_start || '_' || partition_end - 1;
    IF NOT EXISTS(SELECT relname FROM pg_class WHERE relname=partition) THEN
      EXECUTE 'CREATE TABLE ' || partition || ' PARTITION OF buildroot_listing_partition FOR VALUES FROM (' || partition_start ||') TO (' || partition_end || ')';
      EXECUTE 'CREATE UNIQUE INDEX ' || partition || '_broot_rpm ON ' || partition || '(buildroot_id, rpm_id)';
      RAISE NOTICE 'A partition % has been created', partition;
    END IF;
    RETURN NULL;
  END;
  $$
  LANGUAGE plpgsql VOLATILE
  COST 100;

  CREATE TRIGGER testing_partition_insert_trigger
  BEFORE INSERT ON buildroot
  FOR EACH ROW EXECUTE PROCEDURE create_partition_and_insert();


The third one is one-time code, which will be used for converting
existing tables.

.. code-block:: plpgsql

  -- temporary table for partitioning, will be populated and in the end renamed to buildroot_listing
  CREATE TABLE buildroot_listing_partition (
      buildroot_id INTEGER NOT NULL,
      rpm_id INTEGER NOT NULL,
      is_update BOOLEAN NOT NULL DEFAULT FALSE
  ) PARTITION BY RANGE (buildroot_id);


  CREATE OR REPLACE FUNCTION partition_buildroot_listing() RETURNS integer AS
  $$
  DECLARE
    partition TEXT;
    partition_start INTEGER;
    partition_end INTEGER;
    partition_count INTEGER;
    partition_size INTEGER;
  BEGIN
    -- same number as in create_partition_and_insert
    partition_size = 1000000;
    SELECT DIV(MAX(id), partition_size)  FROM buildroot INTO partition_count;
    RAISE NOTICE 'Will create % partitions', partition_count;

    -- create partitions
    FOR i IN 0..partition_count LOOP
      partition_start = i * partition_size;
      partition_end = partition_start + partition_size;
      partition := 'buildroot_listing_' || partition_start || '_' || partition_end - 1;
      EXECUTE 'CREATE TABLE ' || partition || ' PARTITION OF buildroot_listing_partition FOR VALUES FROM (' || partition_start ||') TO (' || partition_end || ')';
      RAISE NOTICE 'A partition % has been created', partition;
    END LOOP;

    -- copy data
    INSERT INTO buildroot_listing_partition SELECT * FROM buildroot_listing;
    RAISE NOTICE 'Data were copied from buildroot_listing to buildroot_listing_partition';

    DROP TABLE buildroot_listing;
    RAISE NOTICE 'Original buildroot_listing dropped';

    ALTER TABLE buildroot_listing_partition RENAME TO buildroot_listing;
    RAISE NOTICE 'buildroot_listing_partition renamed back to buildroot_listing';

    -- create indices after copy
    FOR i IN 0..partition_count LOOP
      partition_start = i * partition_size;
      partition_end = partition_start + partition_size;
      partition := 'buildroot_listing_' || partition_start || '_' || partition_end - 1;
      EXECUTE 'CREATE UNIQUE INDEX ' || partition || '_broot_rpm ON ' || partition || '(buildroot_id, rpm_id)';
      RAISE NOTICE 'A partition index has been created %', partition;
    END LOOP;

    RETURN 1;
  END;
  $$
  LANGUAGE plpgsql;

  -- run conversion function
  BEGIN;
    SELECT partition_buildroot_listing();
    DROP FUNCTION partition_buildroot_listing();
  COMMIT;

Using SSL with PostgreSQL
-------------------------

The basic :doc:`Koji server walkthrough <server_howto>` and sample
configuration files instruct users to use plaintext TCP/IP connections to the
postgresql server. This is not a good practice, and it is more secure to use
SSL. You'll need to configure the postgresql server to accept SSL connections,
and then configure the Koji Hub to only use a trusted SSL connection.

Enabling SSL on the PostgreSQL server
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Edit ``/var/lib/pgsql/data/postgresql.conf``:

 * Enable SSL with ``ssl = on``
 * The ``listen_addresses`` option cannot be empty. ``listen_addresses = '*'``
   will make postgres listen on every network interface (simpler), or you can
   restrict it to only certain network interfaces.

Create two files:

 * ``/var/lib/pgsql/data/server.crt`` - This is the public signed certificate.
   It should include the full chain (including the CA and any intermediates).
 * ``/var/lib/pgsql/data/server.key`` - The private key.

Set the ownership appropriately::

  chown postgres:postgres /var/lib/pgsql/data/server.{crt,key}
  chmod 0600 /var/lib/pgsql/data/server.key

Restart postgresql for the new settings to take effect::

  systemctl restart postgresql

Configuring the Koji hub to use SSL to Postgres
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Once you've enabled SSL on the PostgreSQL server, you can test it with the
CLI::

  psql 'postgresql://koji:example_password@db.example.com/koji?sslmode=verify-full&sslrootcert=/etc/pki/tls/certs/ca-bundle.trust.crt'

You should be able to list tables, run queries, etc.

Edit ``/etc/koji-hub/hub.conf`` to use this connection string::

  DBConnectionString = postgresql://koji:example_password@kojidev.example.com/koji?sslmode=verify-full&sslrootcert=/etc/pki/tls/certs/ca-bundle.trust.crt

Restart the hub and verify the new ``DBConnectionString`` is working::

  systemctl restart httpd

  koji hello
