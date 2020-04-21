========================
Koji Miscellaneous Notes
========================


Notes and miscellaneous details about Koji
==========================================

This document is intended to illuminate some of the small quirks that
you may encounter while running your own koji server.

Koji CLI
--------

Getting Help
~~~~~~~~~~~~

-  There are multiple ways to receive help from the koji command, each
   of them gives you something a little different:

   -  List of user commands:
      ::

          koji help

   -  Command-specific help:
      ::

          koji [command] --help

   -  List of admin commands:
      ::

          koji help --admin

Building from SRPM
~~~~~~~~~~~~~~~~~~

Koji only allows admins access to build directly from srpm. It expects
normal users to build out of an SCM.

Building from SCM
~~~~~~~~~~~~~~~~~

SCM Layout
^^^^^^^^^^

When building out of an SCM, Koji expects there will be a Makefile in
the project root that has a 'sources' target. Koji will call 'make
sources' on the checked out files.

This target simply needs to download all the sources for the SRPM that
are not already included in the SCM repository.

SCM URI Structure
^^^^^^^^^^^^^^^^^

In Fedora, this detail is typically handled by the fedpkg tool. Outside
of Fedora, you may need to know how to manually submit builds from an
SCM to koji.

Koji accepts an SCM URI in this format:

::

    koji build [target] [scheme]://[user]@[hostname]/[path/to/repository]?[path/to/project]#[revision]

Note the division between repository path and project path. During setup
of kojid, the allowed\_scms parameter is configured in
/etc/kojid/kojid.conf. This value of this parameter should match the
path to the repository.

In some SCM configurations, there isn't a difference between repository
path and project path. In these cases, it should be understood that
dividing your SCM path into two components, URI path and URI query, can
seem somewhat arbitrary. An easy way to remember this detail is that the
path specified in allowed\_scms is the portion of your SCM path that
goes before the URI query, any sub-directories not specified in
allowed\_scms is given to koji as the URI query.

Koji tasks
----------

BuildNotifications
~~~~~~~~~~~~~~~~~~

-  Koji sends build notifications to the package owner and the user who
   submitted the build. For BuildNotifications to work successfully, the
   package owner's username needs to match a valid username for an
   e-mail address, because kojihub sends to
   username@domain\_in\_kojihub.conf.

   -  For SSL authentication, this means that your CN must be valid as
      the user portion of an e-mail address.

Koji server administration
--------------------------

Importing an rpm without srpm
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

If you are running a private koji instance, you may run into a situation
where you need to integrate a proprietary rpm into your build system. To
do this, it is similar to the package imports you did when bootstrapping
your koji instance:

::

    koji import --create-build [package]

Multi-arch builds
~~~~~~~~~~~~~~~~~

There are some packages that need to build across multiple arches. For
example, the kernel package no longer builds an i386 kernel, kernels are
built on i586 and above. To instruct koji to build these additional
arches, use this command:

::

    koji set-pkg-arches [options] <arches> <tag> <package> [<package2> ...]

Note: is a single entity, so denote multiple arches within quotes (e.g.
'i386 i586 i686').

How noarch sub-packages are built
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

It is a technical detail, but can make sense for someone debugging
noarch issues. If there are multiple architectures defined, multiple
`buildArch` tasks are spawned. Each of them will produce arch and also
noarch packages. While arch packages are unique compared to other
subtasks, noarch packages should be the same. It shouldn't matter on
which arch you're building it. If there is a difference, it is a bug.
Koji internally checks some data from these noarch packages and
chooses randomly one, which will appear in final builds. If
differences are found, build will fail. Koji is using simple embedded
rpmdiff variant, which checks for each file included in rpm: mode,
device, vflags, user, group, digest. Furthermore, Name, Summary,
Description, Group, License, URL, PreIn, PostIn, PreUn, PostUn,
Provides, Requires, Conflicts and Obsoletes are compared.  In case of
failing this test, `BuildError` is raised.

Manually submitting a task
~~~~~~~~~~~~~~~~~~~~~~~~~~

Occasionally, you may need to manually submit a task to koji. One likely
usage is to manually trigger a createRepo. To do this, use this command:

::

    koji make-task [options] <arg1> [<arg2>...]

The make-task command is a bit of under-documented black magic. Task
parameters are defined in kojihub.py. The easiest way I have found to
figure out the right incantations for make-task is to query the *task*
table in the koji database directly. Find a similar task to the one you
want to create, and look in the request field for the parameters the
task used, and mimic those.

So, citing the createRepo case above, here is an example:

::

    kojiadmin@localhost$ koji make-task --channel=createrepo --priority=15 \
    newRepo dist-foo-build

Managing your tags
~~~~~~~~~~~~~~~~~~

Occasionally an unwanted package or version of a package will be built
by koji. Don't fret. There are two mechanisms to handle rescinding a
package or specific package version.

-  To remove a specific version of a package, you can untag it:

::

    koji untag-build [options] <tag> <pkg> [<pkg>...]

 supports either %name or %name-%version-%release

-  To remove all versions of a package, you can untag it as above or you
   can administratively block it from being listed in a tag:

::

    koji block-pkg [options] tag package [package2 ...]

Spec file processing
--------------------

Macro processing
~~~~~~~~~~~~~~~~

Macros in the spec file are expanded before Requires and BuildRequires
are processed. If there are any custom macros in the spec file, the
package that drops those macros into /etc/rpm must be tagged under your
dist-build tag

%dist tags
^^^^^^^^^^

For packages that incorporate the %dist tags in their filename, they
expect %dist to be defined in /etc/rpm/macros.dist, which was added in
Fedora 7. For building on RHEL5/FC6 and earlier, koji needs the
`https://buildsys.fedoraproject.org/buildgroups/
buildsys-macros <https://buildsys.fedoraproject.org/buildgroups/ buildsys-macros>`__
package tagged under the dist-build tag.
