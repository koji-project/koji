Storage Volumes
===============


Introduction
------------

Since version 1.7.0, Koji has had the ability to store builds on
multiple volumes.

Each build in Koji has a volume field that indicates which volume it is
stored on. The default volume is named ``DEFAULT`` and corresponds to the
original paths under ``/mnt/koji`` that predate this feature.

Additional volumes correspond to paths under
``/mnt/koji/vol/NAME`` (where NAME is the name of the volume). All builds
associated with such a volume will be stored under this directory.
The expectation is that this directory will map to a different file system.


.. hint::
    | If ``koji-1.13.0-1`` is on the DEFAULT volume, its path will be:
    | /mnt/koji/packages/koji/1.13.0/1

    | If ``koji-1.13.0-1`` is on the volume named "test", its path will be:
    | /mnt/koji/vol/test/packages/koji/1.13.0/1


Constructing the path
---------------------

If you are using the Koji python api, things should **just work**.

::

    >>> import koji
    >>> mykoji = koji.get_profile_module('mykoji')
    >>> opts = mykoji.grab_session_options(mykoji.config)
    >>> session = mykoji.ClientSession(mykoji.config.server, opts)
    >>> binfo = session.getBuild('test-1-1')
    >>> binfo['volume_name']
    'DEFAULT'
    >>> mykoji.pathinfo.build(binfo)
    '/mnt/koji/packages/test/1/1'
    >>> binfo = session.getBuild('fake-1.0-21')
    >>> binfo['volume_name']
    'vol3'
    >>> mykoji.pathinfo.build(binfo)
    '/mnt/koji/vol/vol3/packages/fake/1.0/21'

If you are constructing these paths yourself, then you may need to do
a little work.

    * Look for volume information in build data. Hub calls that return build
      data include ``volume_name`` and ``volume_id`` fields in their return.
    * If the volume is ``DEFAULT``, then the path is the "normal" path.
    * Otherwise, you need to insert ``/vol/<volume_name>`` after the
      top directory (normally /mnt/koji).


Symlinks on default volume
--------------------------

For backwards compatibility, Koji maintains symlinks on the default volume
for builds on other volumes.

::

    $ file /mnt/koji/packages/fake/1.0/21
    /mnt/koji/packages/fake/1.0/21: symbolic link to ../../../vol/vol3/packages/fake/1.0/21


Adding a new volume
-------------------

The new volume directory should initially contain a packages/
subdirectory, and the permissions should be the same as the default
packages directory.

Assuming you do use a mount for a vol/NAME directory, you will want to
ensure that the same mounts are created on all systems that interface with
``/mnt/koji``,  such as builders that run createrepo tasks, hosts running
kojira or similar maintenance, and any hosts that rely on the topdir option
rather than the topurl option.

Once you have the directory set up, you can tell Koji about it by
running ``koji add-volume NAME``. This call will fail if the hub can't find
the directory.

Moving builds onto other volumes
--------------------------------

By default, all builds live on the DEFAULT volume.

An admin can move a build to a different volume by using the
``koji set-build-volume`` command, or by using the underlying
``changeBuildVolume`` api call.

Moving a build across volumes will cause kojira to trigger repo
regenerations, if appropriate. When the new volume is not DEFAULT, Koji will
create a relative symlink to the new build directory on the default
volume. Moving builds across volumes may immediately break repos (until
the regen occurs), so use caution.

Consider the following example:

::

    # mypkg-1.1-20 initially on default volume
    $ file /mnt/koji/packages/mypkg/1.1/20
    /mnt/koji/packages/mypkg/1.1/20: directory

    # move it to test volume
    $ koji set-build-volume test mypkg-1.1-20
    $ file /mnt/koji/vol/test/packages/mypkg/1.1/20
    /mnt/koji/vol/test/packages/mypkg/1.1/20: directory

    # original location is now a symlink
    $ file /mnt/koji/packages/mypkg/1.1/20
    /mnt/koji/packages/mypkg/1.1/20: symbolic link to ../../../vol/test/packages/mypkg/1.1/20


Using the volume in policy checks
---------------------------------

Policies involving builds (e.g. gc policy, tag policy), can test a
build's volume with the ``volume`` test. This is a pattern match
test against the volume name.

Setting a volume policy
-----------------------

The Koji 1.14.0 release adds the ability to set a volume policy on the hub.
This policy is used at import time to determine which volume the build should
be assigned to. This provides a systematic way to distribute builds
across multiple volumes without manual intervention.

There is relatively limited data available to the volume policy. Tests that are
expected to work include:

- user based tests (the user performing the build or running the import)
- package based tests (e.g. ``is_new_package`` or ``package``)
- cg match tests
- the buildtag test

The action value for the volume policy should be simply the name of the volume
to use.

The default volume policy is ``all :: DEFAULT``.

If the volume policy contains errors, or does not return a result, then the
DEFAULT volume is used.

For more information about Koji policies see:
:doc:`Defining hub policies <defining_hub_policies>`


CLI commands
------------

``add-volume``
    adds a new volume (directory must already be set up)
``list-volumes``
    prints a list of known volumes
``set-build-volume``
    moves a build to different volume


API calls
---------

``addVolume(name, strict=True)``
    Add a new storage volume in the database

``applyVolumePolicy(build, strict=False)``
    Apply the volume policy to a given build

``changeBuildVolume(build, volume, strict=True)``
    Move a build to a different storage volume

``getVolume(volume, strict=False)``
    Lookup the given volume

``listVolumes()``
    List storage volumes

``removeVolume(volume)``
    Remove unused storage volume from the database
