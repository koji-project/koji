Migrating to Koji 1.10
======================

.. reStructured Text formatted

The 1.10 release of Koji includes a few changes that you should consider when
migrating.

DB Updates
----------

The new ``tag_extra`` table tracks extra data for tags.

There is a new entry in the ``channels`` table and some additions and updates to
the ``archivetypes`` table.

As in previous releases, we provide a migration script that updates the
database.

::

    # psql koji koji  </usr/share/doc/koji-1.10.0/docs/schema-upgrade-1.9-1.10.sql


Command line changes
--------------------

A few commands support new arguments

``maven-build``
    * ``--ini``     : Pass build parameters via a .ini file
    * ``--section`` : Get build parameters from this section of the .ini

``wrapper-rpm``
    * ``--ini``     : Pass build parameters via a .ini file
    * ``--section`` : Get build parameters from this section of the .ini

``import``
    * ``--link``    : Attempt to hardlink instead of uploading

``list-tagged``
    * ``--latest-n``: Only show the latest N builds/rpms

``list-history``
    * ``--watch``   : Monitor history data

``edit-tag``
    * ``--extra``   : Set tag extra option

``list-tasks``
    * ``--user``    : Only tasks for this user
    * ``--arch``    : Only tasks for this architecture
    * ``--method``  : Only tasks of this method
    * ``--channel`` : Only tasks in this channel
    * ``--host``    : Only tasks for this host

``download-build``
    * ``--task-id`` : Interpret id as a task id

And there are three new commands

* ``image-build-indirection``
* ``maven-chain``
* ``runroot``


Other Configuration changes
---------------------------

The Koji web interface can now treat ``extra-footer.html`` as a Cheetah
template. This behavior can be enabled by setting the ``LiteralFooter`` option
to ``False`` in the kojiweb config.


RPC API Changes
---------------

The ``readTaggedBuilds`` and ``readTaggedRPMS`` now treat an integer value for
the optional latest argument differently. Before it was simply treated as a
boolean flag, which if true caused the call to return only the latest build for
each package. Now, if the value is a positive integer N, it will return the N
latest builds for each package. The behavior is unchanged for other values.

New rpc calls: ``chainMaven``, ``buildImageIndirection``, and ``mergeScratch``
