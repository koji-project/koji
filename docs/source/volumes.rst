Storage Volumes
===============

Each build now has a volume attribute that indicates which volume it is
stored on. The default volume is named 'DEFAULT' and corresponds to the
same storage paths under /mnt/koji that we have always used.

Additional volumes can be set up by creating the directory
/mnt/koji/vol/NAME (where NAME is the name of the volume). The
expectation is that this will be a mount point, but it doesn't have to be.

The new volume directory should initially contain a packages/
subdirectory, and the permissions should be the same as the default
packages directory.

Assuming you do use a mount for a vol/NAME directory, you will want to
ensure that the same mounts are created on any builders in the
createrepo group, any hosts running kojira or similar maintenance, and
any hosts that rely on the topdir option rather than the topurl option.

Once you have the directory set up, you can tell Koji about it by
running 'koji add-volume NAME' (which will fail if the hub can't find
the directory). You can get a list of known volumes with the 'koji
list-volumes' command, and you can move a build to a different volume
with the 'koji set-build-volume' command. Like all koji subcommands,
these have a --help option.

Moving a build across volumes will cause kojira to trigger repo
regenerations, if appropriate. When the volume is not DEFAULT, koji will
create a relative symlink to the new build directory on the default
volume. Moving builds across volumes may immediately break repos (until
the regen occurs), so use caution.

Policies involving builds (e.g. gc policy, tag policy), can test a
build's volume (by name) with the 'volume' test.

That's pretty much it. It is a very simplistic system. There is no
automation. It is up to the administrator to manage the mount points and
to manage which builds are stored on which volumes. All new builds are
stored on the default volume until they are moved elsewhere.
