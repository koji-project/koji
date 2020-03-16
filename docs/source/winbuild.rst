====================
Building for Windows
====================

Koji provides a fairly basic mechanism to perform builds for Windows.

.. toctree::
   :hidden:

   win_spec_example

Introduction
============

Koji supports building components in a Windows-based environment.  This is
accomplished by cloning and starting a Windows VM, checking out sources and
building from within it.  The VM would have compile tools and utility already
installed, and the results are then passed back up the hub.  Windows builds are
treated similarly to RPM builds in that they have a unique name, version, and
release field.  The resulting builds are built using targets and tagged into tags
just as normal builds are.  When you build a Windows component, you can
reference other components and they will be downloaded into the build
environment to satisfy build-time dependencies.


Initiating a build
==================

Note: access to performing Windows builds is governed by the ``vm`` policy on the hub.
The default policy requires the user to have the ``win-admin`` permission.
Different Koji instances may have different policies.
If the policy denies you access, you will see an ``ActionNotAllowed`` error.
In that case, you will need file a request with your Koji administators.


Windows builds are initiated with the ``win-build`` subcommand.

..

    $ koji win-build <target> <scm-url> <vm-name>

Where ``target`` is the build target to use for the build,
``scm-url`` is the SCM URL for the sources to build,
and ``vm-name`` is the name of the vm image to use for the build.

The ``target`` works like targets for other types of builds.
The build tag for the target determines where Koji will pull build dependencies from,
and the destination tag for the target determines where the resulting build is tagged
after building is completed.

The ``scm-url`` follows the same syntax used for other Koji builds

..

    scheme://[user@]host/path/to/repo?path/to/module#revision_or_tag_identifier

In order for Koji to perform the build, a "Windows spec file" is required (see below).
This spec file can either be included in the top directory of the sources or specified
separately with the ``--specfile`` option.

The ``vm-name`` argument is the name of the vm image that will be used for the build.
This name must be one of the know images available on the builders.

An option you may be interested in is ``--specfile``, which allows you to specify a second
remote repository that contains the windows spec file using the same SCM URL syntax as
described below. That way you are not forced to keep the spec in with the rest of your
sources if you don't want to. There is also a ``--patches`` option which is just
like ``--specfile``, except meant for a repository of separate patches, which will
be applied to the sources before the build is launched. ``--specfile`` and
--patches may reference the same repo.


The Windows "Spec-File"
=======================

This is the file that controls the build process, and is modeled very loosely
on RPM's spec files. The Windows spec file is in .ini format.

It's probably easiest to start by looking at this
:doc:`example <win_spec_example>`
spec file.

All values in the [naming] section must be defined.
The name, version, and release are used to determine the NVR of the build.
As with all NVRs in Koji, this must be a unique value.

The [building] section defines preconditions that must be satisfied before the
build will be launched, and the commands used to perform the build.  platform
indicates to VM type the build is running in, and should be in the format of
osname-arch.


The ``preinstalled`` value under [building] lists the files and directories
that must be present for the build
to run.  Any tools that were installed in the VM when it was setup should be
listed here.  If any of the files or directories listed here are missing when
the build runs, it will fail immediately.  Files and directories may be listed
in Windows format (C:\Program Files\...), full Cygwin paths (/bin/...), or as
command names (tar, unzip, etc).  If they are listed as command names, the
Cygwin PATH will be checked for the command.


The ``buildrequires`` value under [building] lists other packages that
the build depends on.  As with rpm
BuildRequires, the buildrequires entries should be package names only (no
version information).  The latest build of that package will be looked up in
the -build tag associated with the build target that was used when launching
the build, and files from that build will be downloaded into the VM.  Each
package listed in buildrequires can have a colon-delimited list of options
associated with it, which determine which files from the build will be
downloaded.  By default, all Windows files associated with the dependent build
will be downloaded (this is the same as specifying type=win).  In this case,
comma-separated lists of platforms= and flags can also be specified, in which
case the files downloaded into the VM will be limited to those associated with
one or more of the platform and flag values (more about this in the [files]
section below.  If type=rpm is specified, then all rpms associated with the
dependent build will be installed.  In this case a comma-separated list of
arches= may be specified, and only rpms matching one of those arches will be
downloaded.  If type=maven is specified, then comma-separated lists of
group_ids=, artifact_ids=, and/or versions= may be specified, and only Maven
artifacts matching at least one value in each list will be downloaded.  In all
cases, a patterns= option may be specified, which is a comma-separated list of
globs to match against the filenames.  Only files matching at least one of the
patterns will be downloaded.


The files downloaded to satisfy the buildrequires are placed in a directory
based on their type, and variables are set which point to their location.  The
variable names are constructed by converting the dependency name to variable
format (a leading number is converted to and underscore, and any character that
is not a letter, number, or underscore is converted to an underscore).  If
type= is specified, then <type>_dir is appended to complete the variable name.
Otherwise, just _dir is appended.  In the example above, the directory
containing the boost-win files would be indicated by $boost_win_dir.  The
directory containing the .src.rpm from the qpid-cpp-mrg build would be
$qpid_cpp_mrg_rpm_dir.  Note the extra _rpm there, because it specified
type=rpm.  There is also a corresponding _files variable which is a
newline-delimited list of all files downloaded for each dependency.  In the
example, both $boost_win_files and $qpid_cpp_mrg_rpm_files would be defined.


The files are downloaded to the VM unmodified.  It is up to the build process
to extract them if necessary, and move/copy them to whatever location is
required by the current build.


The ``provides`` value under [building] is optional, and can be used to indicate what the build is
producing.  It is freeform, but a structure like <name>-<version> is
encouraged.


The ``shell`` value under [building] indicates how the build script should be run.
Valid values are
bash, which will cause the script to be run in bash, and cmd.exe, which will
cause the script to be run in Windows cmd.exe.  cmd is also an alias for
cmd.exe.  bash is the default if no shell value is present.


The ``execute`` value under [building] is required, and this is what drives the build process.
This value is multiline, and each line is treated as a separate command to be execute in the
shell specified above.  In addition to the variables defined for the buildrequires, the
following variables will be available when the script is executed:

  * name: name from the [naming] section
  * version: version from the [naming] section
  * release: release from the [naming] section
  * source_dir: the directory the sources were checked out into
  * spec_dir: the directory the .ini was checked out into.  If there was no separate --winspec
    option passed on the command-line, this will be the same as source_dir
  * patches_dir: the directory the patches were checked out into.  If there was no --patches
    option passed on the command-line, this will be undefined.


If using bash, the build script will be executed with -x and -e, which will
cause all commands to be echoed, and will cause the script to fail if any
commands have a non-zero exit status.  There is no equivalent fail-fast option
for Windows cmd.exe.  If executing the script using cmd.exe, it is recommend
that you frequently check the return value of commands with this:

..

    if %ERRORLEVEL% neq 0 exit %ERRORLEVEL%


The script will start in the root directory of the sources that were checked
out ($source_dir).  Extra scripts or supplementary files required by the build
may be checked in along with the .ini file, and will be available under
$spec_dir (assuming a separate --specfile option was used).


The postbuild value is optional, and specifies a list of files and directories
(relative to $source_dir) that must be present for the build to be considered
successful.  If any of them are missing, the build will fail.  This is useful
for verifying that all expected output was generated correctly, in the case
that some commands may have failed silently.


The [files] section describes what output should be collected after the build
completes. The logfiles value is optional, but it should be set to whatever
build logs are produced from the build. The syntax for the output variable is
as follows:

..

    output = qpid-cpp-x86-$version.zip:i386:chk,fre

Note the colon-separated nature. The first token is the path to the file you
want collected as part of your build output. This path is rooted at the
checkout from the SCM ($source_dir). The file path relative to $source_dir is
retained when output is uploaded to Koji and when it is downloaded as a
buildrequires by future builds.  If you don't want a long, confusing file path,
it may be desirable to copy the build output to $source_dir at the end of your
build script.  File globs are not allowed, but the $name, $version, and
$release variables will be expanded in the file paths and names, using the
values from the [naming] section. The second token is a comma-separated list of
platforms (which we haven't really standardized on yet, but i386 and/or x86_64
are logical choices).  The last is a comma-separated list of build flags. These
fields are purely informational, they do not influence future builds at this
time, but they do make for good housekeeping in the future.  Common flags are
chk (indicating a debug build) and fre (indicating an optimized build).  If an
output file contains both kinds of builds, both may be specified.


The logs value indicates extra log files generated during the build that should
be tracked.  The contents of these log files will be streamed to the hub during
the build and may be watched in realtime using the "Watch logs"
feature of the web interface, or the "koji watch-logs" cli command.
They will also be included in the build logs stored on in Koji.


Source Repository
=================

As noted earlier, the sources are checked out from within a Windows VM that
Koji clones and starts when you submit your task with the client. Koji supports
checking out sources from CVS, SVN, and git.
As with other types of builds, the ``allowed_scms`` setting limits which sources
can be built from.


Administration
==============

Windows Build Hosts
-------------------

By default, all ``winbuild`` tasks go to the ``vm`` channel.
The hosts in this channel require special setup.

 * They run the ``kojivmd`` daemon instead of the regular ``kojid`` daemon
 * VM images for builds must be stored in the local image directory


Managing VM Images
------------------

The directory where ``kojivmd`` looks for vm images can be controlled by setting ``imagedir``
in ``/etc/kojivmd/kojivmd.conf``. The default value is ``/var/lib/libvirt/images``.

These images must be qcow2 images named with a ``.qcow2`` extension. The basename of the
image file is the same name that users refer to in the ``vm-name`` parameter to the
``win-build`` command.
