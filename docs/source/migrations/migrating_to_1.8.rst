Migrating to Koji 1.8
=====================

.. reStructured Text formatted

The 1.8 release of Koji refactors how images (livecd and appliance) are stored
in the database and on disc. These changes will require a little extra work
when updating.

There have also been some changes to the command line.

Finally, kojira accepts some new options.

DB Schema Updates
-----------------

Previous to 1.8, images were stored in separately from other builds, both in
the database and on disc. The new schema adds new tables: ``image_builds``,
``image_listing``, and ``image_archives``.

The following tables are now obsolete: ``imageinfo`` and ``imageinfo_listing``.
However you should not drop these tables until you have migrated your image
data.

As in previous releases, we provide a migration script that updates the
database.

::

    # psql koji koji  </usr/share/doc/koji-1.8.0/docs/schema-upgrade-1.7-1.8.sql

Note that the SQL script does not (and can not) automatically migrate your old
image data to the new tables. After applying the schema changes, you can
migrate old images using the ``migrateImage`` hub call. This method is necessary
because the new schema requires each image to have a name, version, and release
value. The values for name and version cannot be automatically guessed.


Migrating your old images
-------------------------

If you have old images, you can migrate them to the new system using the
``migrateImage`` hub call. This call requires admin privilege and must also be
enabled with the ``EnableImageMigration`` configuration option in ``hub.conf``.

The signature of the call is:

::

    migrateImage(old_image_id, name, version)

This call can made from the command line:

::

    # koji call migrateImage 45 my_livecd 1.1


Cleaning up
-----------

After you have migrated any necessary images to the new system, you may want to
remove the old database tables and filesystem directories. This step is
*optional*. If you want to leave the old data around, it will not affect Koji.

Before you take any of the following actions, please *make sure* that you have
migrated any desired images.

Removing the old data is simply a matter of dropping tables and deleting files.

::

    koji=> DROP TABLE imageinfo_listing;
    koji=> DROP TABLE imageinfo;
    # rm -rf /mnt/koji/images


Command line changes
--------------------

For clarity and consistency, all of the ``-pkg`` commands have been renamed to
``-build`` commands.

::

    latest-pkg -> latest-build
    move-pkg -> move-build
    tag-pkg -> tag-build
    untag-pkg -> untag-build

For backwards compatibility, the old commands names are also recognized.

A new command has been added, ``remove-pkg``.

Several commands have been modified to support images.

The ``spin-livecd`` and ``spin-appliance`` commands now require additional
arguments. These arguments specify the name and version to use for the image.


New kojira options
------------------

The following options are new to kojira:

::

    max_delete_processes
    max_repo_tasks_maven

Previously, kojira ran as a single process and repo deletions could potentially
slow things down (particularly for Maven-enabled repos). Now kojira spawns
a separate process to handle these deletions. The ``max_delete_processes``
determines how many such processes it will launch at one time.

When Maven-enabled repos are in use, they can potentially take a very long time
to regenerate. If a number of these pile up it can severely slow down
regeneration of non-Maven repos. The ``max_repo_tasks_maven`` limits how many
Maven repos kojira will attempt to regenerate at once.

Also the following kojira option has been removed:

::

    prune_batch_size
