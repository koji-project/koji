==========
Koji HOWTO
==========

Introduction
============

Koji is a system for building and tracking RPMs. It was designed with
the following features in mind:

**Security**

-  New buildroot for each build
-  nfs is used (mostly) read-only

**Leverage other software**

-  Uses Yum and Mock open-source components
-  XML-RPC APIs for easy integration with other tools

**Flexibility**

-  rich data model
-  active code base

**Usability**

-  Web interface with Kerberos authentication
-  Thin, portable client
-  Users can create local buildroots

**Reproducibility**

-  Buildroot contents are tracked in the database
-  Versioned data

This HOWTO document covers the basic tasks that a developer needs to be
able to accomplish with Koji.

Getting started
===============

The web interface
-----------------

The primary interface for viewing Koji data is a web application. Most
of the interface is read-only, but if you are logged in (see below) and
have sufficient privileges there are some actions that can be performed
though the web. For example:

-  Cancel a build
-  Resubmit a failed task

Those with admin privileges will find additional actions, such as:

-  Create/Edit/Delete a tag
-  Create/Edit/Delete a target
-  Enable/Disable a build host

The web site utilizes Kerberos authentication. In order to log in you
will need a valid Kerberos ticket and your web browser will need to be
configured to send the Kerberos information to the server.

In Firefox, you will need to use the about:config page to set
a Kerberos parameter. Use the search term 'negotiate' to filter the list.
Change network.negotiate-auth.trusted-uris to the domain you want to
authenticate against, e.g .example.com. You can leave
network.negotiate-auth.delegation-uris blank, as it enables Kerberos
ticket passing, which is not required.

In order to obtain a Kerberos ticket, use the kinit command.

Installing the Koji cli
-----------------------

There is a single point of entry for most operations. The command is
called 'koji' and is included in the main koji package.

The koji tool authenticates to the central server using Kerberos, so you
will need to have a valid Kerberos ticket to use many features. However,
many of the read-only commands will work without authentication.

Building a package
------------------

Builds are initiated with the command line tool. To build a package, the
syntax is:

::

    $ koji build <build target> <git URL>

For example:

::

    $ koji build f25 git://pkgs.fedoraproject.org/rpms/eclipse-jgit?#00ca55985303b1ce19c632922ebcca283ab6e296

The ``koji build`` command creates a build task in Koji. By default the
tool will wait and print status updates until the build completes. You
can override this with the ``--nowait`` option. To view other options to
the build command use the ``--help`` option.

::

    $ koji build --help

Build Options
-------------

There are a few options to the build command. Here are some more
detailed explanations of them:

``--skip-tag``
    Normally the package is tagged after the build completes. This
    option causes the tagging step to be skipped. The package will be in
    the system, but untagged (you can later tag it with the tag-build
    command)
``--scratch``
    This makes the build into a scratch build. The build will not be
    imported into the db, it will just be built. The rpms will land
    under <topdir>/scratch. Scratch builds are not tracked and can never
    be tagged, but can be convenient for testing. Scratch builds are
    typically removed from the filesystem after one week.
``--nowait``
    As stated above, this prevents the cli from waiting on the build
    task.
``--arch-override``
    This option allows you to override the base set of arches to build
    for. This option is really only for testing during the beta period,
    but it may be retained for scratch builds in the future.

Build Failures
--------------

If your package fails to build, you will see something like this.

::

          420066 buildArch (kernel-2.6.18-1.2739.10.9.el5.jjf.215394.2.src.rpm,
          ia64): open (build-1.example.com) -> FAILED: BuildrootError:
          error building package (arch ia64), mock exited with status 10

You can figure out why the build failed by looking at the log files. If
there is a build.log, start there. Otherwise, look at init.log

::

          $ ls -1 <topdir>/work/tasks/420066/*
          <topdir>/work/tasks/420066/build.log
          <topdir>/work/tasks/420066/init.log
          <topdir>/work/tasks/420066/mockconfig.log
          <topdir>/work/tasks/420066/root.log


Koji Architecture
=================

Terminology
-----------

In Koji, it is sometimes necessary to distinguish between the a package
in general, a specific build of a package, and the various rpm files
created by a build. When precision is needed, these terms should be
interpreted as follows:

Package
    The name of a source rpm. This refers to the package in general and
    not any particular build or subpackage. For example: kernel, glibc,
    etc.
Build
    A particular build of a package. This refers to the entire build:
    all arches and subpackages. For example: kernel-2.6.9-34.EL,
    glibc-2.3.4-2.19.
RPM
    A particular rpm. A specific arch and subpackage of a build. For
    example: kernel-2.6.9-34.EL.x86\_64, kernel-devel-2.6.9-34.EL.s390,
    glibc-2.3.4-2.19.i686, glibc-common-2.3.4-2.19.ia64

Koji Components
---------------

Koji is comprised of several components:

-  **koji-hub** is the center of all Koji operations. It is an XML-RPC
   server running under mod\_wsgi in Apache. koji-hub is passive in
   that it only receives XML-RPC calls and relies upon the build daemons
   and other components to initiate communication. koji-hub is the only
   component that has direct access to the database and is one of the
   two components that have write access to the file system.
-  **kojid** is the build daemon that runs on each of the build machines.
   Its primary responsibility is polling for incoming build requests and
   handling them accordingly. Koji also has support for tasks other than
   building. Creating install images is one example. kojid is
   responsible for handling these tasks as well.

   kojid uses mock for building. It also creates a fresh buildroot for
   every build. kojid is written in Python and communicates with
   koji-hub via XML-RPC.

-  **koji-web** is a set of scripts that run in mod\_wsgi and use the
   Cheetah templating engine to provide an web interface to Koji.
   koji-web exposes a lot of information and also provides a means for
   certain operations, such as cancelling builds.
-  **koji** is a CLI written in Python that provides many hooks into Koji.
   It allows the user to query much of the data as well as perform
   actions such as build initiation.
-  **kojira** is a daemon that keeps the build root repodata updated.

Package Organization
--------------------

**Tags and Targets**

Koji organizes packages using tags. In Koji a tag is roughly analogous
to a beehive collection instance, but differ in a number of ways:

-  Tags are tracked in the database but not on disk
-  Tags support multiple inheritance
-  Each tag has its own list of valid packages (inheritable)
-  Package ownership can be set per-tag (inheritable)
-  Tag inheritance is more configurable
-  When you build you specify a *target* rather than a tag

A build target specifies where a package should be built and how it
should be tagged afterwards. This allows target names to remain fixed as
tags change through releases. You can get a full list of build targets
with the following command:

::

    $ koji list-targets

You can see just a single target with the ``--name`` option:

::

    $ koji list-targets --name dist-fc7
    Name                           Buildroot                      Destination
    ---------------------------------------------------------------------------------------------
    dist-fc7                       dist-fc7-build                 dist-fc7

This tells you a build for target dist-fc7 will use a buildroot with
packages from the tag dist-fc7-build and tag the resulting packages as
dist-fc7.

You can get a list of tags with the following command:

::

    $ koji list-tags

*Package lists*

As mentioned above, each tag has its own list of packages that may be
placed in the tag. To see that list for a tag, use the ``list-pkgs``
command:

::

    $ koji list-pkgs --tag dist-fc7
    Package                 Tag                     Extra Arches     Owner
    ----------------------- ----------------------- ---------------- ----------------
    ElectricFence           dist-fc6                                 pmachata
    GConf2                  dist-fc6                                 rstrode
    lucene                  dist-fc6                                 dbhole
    lvm2                    dist-fc6                                 lvm-team
    ImageMagick             dist-fc6                                 nmurray
    m17n-db                 dist-fc6                                 majain
    m17n-lib                dist-fc6                                 majain
    MAKEDEV                 dist-fc6                                 clumens
    ...

The first column is the name of the package, the second tells you which
tag the package entry has been inherited from, and the third tells you
the owner of the package.

**Latest Builds**

To see the latest builds for a tag, use the ``latest-build`` command:

::

    $ koji latest-build --all dist-fc7
    Build                                     Tag                   Built by
    ----------------------------------------  --------------------  ----------------
    ConsoleKit-0.1.0-5.fc7                    dist-fc7              davidz
    ElectricFence-2.2.2-20.2.2                dist-fc6              jkeating
    GConf2-2.16.0-6.fc7                       dist-fc7              mclasen
    ImageMagick-6.2.8.0-3.fc6.1               dist-fc6-updates      nmurray
    MAKEDEV-3.23-1.2                          dist-fc6              nalin
    MySQL-python-1.2.1_p2-2                   dist-fc7              katzj
    NetworkManager-0.6.5-0.3.cvs20061025.fc7  dist-fc7              caillon
    ORBit2-2.14.6-1.fc7                       dist-fc7              mclasen

The output gives you not only the latest builds, but which tag they have
been inherited from and who built them (note: for builds imported from
beehive the "built by" field may be misleading)

Exploring Koji
--------------

We've tried to make Koji self-documenting wherever possible. The command
line tool will print a list of valid commands and each command supports
``--help``. For example:

::

    $ koji help
    Koji commands are:
            build                Build a package from source
            cancel-task          Cancel a task
            help                 List available commands
            latest-build         Print the latest builds for a tag
    ...
    $ koji build --help
    usage: koji build [options] tag URL
    (Specify the --help global option for a list of other help options)

    options:
      -h, --help            show this help message and exit
      --skip-tag            Do not attempt to tag package
      --scratch             Perform a scratch build
      --nowait              Don't wait on build
    ...
