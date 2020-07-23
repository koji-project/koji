===========================
Using the koji build system
===========================


Using Koji in Fedora
====================

The `Koji Build System <Koji>`__ is Fedora's RPM buildsystem. Packagers
use the koji client to request package builds and get information about
the buildsystem. Koji runs on top of Mock to build RPM packages for
specific architectures and ensure that they build correctly.

There is also a `simplified Chinese
edition <Zh/使用Koji编译打包系统>`__.

Installing Koji
---------------

Installing the Koji CLI
^^^^^^^^^^^^^^^^^^^^^^^

Everything you need to use Koji (and be a Fedora contributor) can be
installed in a single step:

::

    dnf install fedora-packager

fedora-packager provides useful scripts to help maintain and setup your
koji environment. Additionally, it includes dependencies on the Koji
CLI, so it will be installed when you install ``fedora-packager``. The
command is called ``koji`` and is included in the main koji package. By
default the koji tool authenticates to the central server using
Kerberos. However SSL and username/password authentications are
available. You will need to have a valid authentication token to use
many features. However, many of the read-only commands will work without
authentication.

If you run into any problems with Fedora's instance of koji, `here
<https://fedoraproject.org/wiki/Join_the_package_collection_maintainers#Install_the_developer_client_tools>`__
is actual documentation for installing and using developer client tools.

Alternatively, koji CLI is now also available via:

  * `Project releases tarballs <https://pagure.io/koji/releases>`__
    Preferred way is to use your distribution's mechanism instead, as it
    will also contain appropriate configuration files.
  * `PyPi <https://pypi.python.org/pypi/koji>`__ There is only client/API
    part and it is mostly usable for people who wants some more advanced
    client-side scripting in virtualenv's, so API-only access is not
    sufficient for them or who can profit from some utilities in e.g. basic
    ``koji`` library.
  * Actual development version via Pagure's git: ``git clone
    https://pagure.io/koji.git``

Koji Config
^^^^^^^^^^^

The global local client configuration file for koji is
``/etc/koji.conf``. You should not need to change this from the defaults
for building Fedora packages.These will allow you to use the primary
build system as well as secondary arch build systems.

The web interface
-----------------

.. raw:: mediawiki

   {{admon/tip|Optional|The web interface is optional.  You may skip to the
   next section if you like.}}

The primary interface for viewing Koji data is a web application. It is
available at https://koji.fedoraproject.org/koji/ . Most of the interface
is read-only, but with sufficient privileges, you can log in and perform
some additional actions. For example:

-  Cancel a build
-  Resubmit a failed task
-  Setup a notification

Those with admin privileges will find additional actions, such as:

-  Create/Edit/Delete a tag
-  Create/Edit/Delete a target
-  Enable/Disable a build host

The web site utilizes SSL authentication. In order to log in you will
need a valid SSL certificate and your web browser will need to be
configured to trust the SSL cert. Instructions on how to do this are
printed when running ``fedora-packager-setup --with-browser-cert``.

.. raw:: mediawiki

   {{admon/warning|Using the certificate directly downloaded from the FAS web
   interface|If you have generated and downloaded the certificate
   <code>~/.fedora.cert</code> directly from FAS using the form referenced
   above, you need to convert it into a format that the browser can understand
   using the following command:
   <code>openssl pkcs12 -export -in ~/.fedora.cert -CAfile ~/.fedora-upload-ca.cert -out ~/fedora-browser-cert.p12</code>,
   where <code>.fedora-upload-ca.cert</code> can be downloaded from the URL
   referenced above.}}

Installing SSL Certificates in Firefox
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. raw:: mediawiki

   {{admon/note|Optional|You only need to check these instructions if you are intending to authenticate with the web interface with Firefox.  Authenticating with the web interface is optional.}}

Once you have created your FAS account, generated your certificate in
the form posted in the link above and ran
``fedora-packager-setup --with-browser-cert``, you will need to import
it into your web browser. You can do this in Firefox by doing the
following:

1. Launch Firefox and click on the **Edit** menu from the toolbar

2. Select **Preferences** in the sub-menu which appears.

3. This should open the **Preferences** window where you can switch to
the **Advanced** section

4. In the **Advanced** section switch to the **Encryption** tab

5. Click on the **View Certificates** button and the Certificates window
will appear

6. Switch to the **Your Certificates** tab and click on the **Import**
button

7. Point to where your Fedora Certificate is located and click **Open**
(fedora-packager-setup will have told you where it was saved and will
have asked you to set a password for the cert)

You should now be able to see your Fedora Certificate listed under
**Your Certificates** and you should be able to authenticate with the
koji web interface.

Installing SSL Certificates in Chromium
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. raw:: mediawiki

   {{admon/note|Optional|You only need to check these instructions if you are intending to authenticate with the web interface with Chromium.  Authenticating with the web interface is optional.}}

Chromium uses the NSS Shared DB, you will need the nss-tools package
installed.

::

    pk12util -d sql:$HOME/.pki/nssdb -i fedora-browser-cert.p12

Notifications
^^^^^^^^^^^^^

Koji supports a limited number of email notifications:

    - build notifications: when builds complete or fail
    - tag notifications: when builds are tagged or untagged

These mails are sent to:

    - the owner of the build in question
    - (for tag notifications) the owner of the package for the tag
    - any user who as subscribed to notifications for that package or tag

Users can manage their notification subscriptions in the web interface.
To do so, they need to be logged in. The main page (Summary) will list
their subscriptions at the bottom. Each entry includes an "edit" and
"delete" link. Below that table is an "Add a notification" link for adding
new notifications.

Starting in Koji version 1.16.0, users can also manage these subscriptions
on the command line. The relevant commands are:

    - add-notification
    - edit-notification
    - list-notifications
    - remove-notification


Building with fedpkg targets
----------------------------

Every push is automatically tagged via git. All you have done to build
the package is to run,

::

    fedpkg build

This will trigger a build request for the branch. Easy!

It is also possible to target a specific koji tag as follows:

::

    fedpkg build --target TARGET

for example, if building on rawhide against a special tag created by
rel-eng for updating API for many packages, e.g. ``dist-f14-python`` you
would use the following:

::

    fedpkg build --target 'dist-f14-python'

Chained builds
^^^^^^^^^^^^^^

.. raw:: mediawiki

   {{Admon/warning | chain-builds only work when building on the devel/ branch (aka rawhide).  To chain-build packages to update a released OS version, [https://fedoraproject.org/wiki/Bodhi/BuildRootOverrides set up an override using bodhi] requesting packages to be included in the proper buildroot.}}

Sometimes you want to make sure than one build succeeded before
launching the next one, for example when you want to rebuild a package
against a just rebuilt dependency. In that case you can use a chain
build with:

``fedpkg chain-build libwidget libgizmo``

The current package is added to the end of the CHAIN list. Colons (:)
can be used in the CHAIN parameter to define groups of packages.
Packages in any single group will be built in parallel and all packages
in a group must build successfully and populate the repository before
the next group will begin building. For example:

``fedpkg chain-build libwidget libaselib : libgizmo :``

will cause libwidget and libaselib to be built in parallel, followed by
libgizmo and then the correct directory package. If no groups are
defined, packages will be built sequentially.

If a build fail, following builds are cancelled but the builds that
already succeeded are pushed to the repository.

Scratch Builds
--------------

Sometimes it is useful to be able to build a package against the
buildroot but without actually including it in the release. This is
called a scratch build. The following section covers using koji directly
as well as the fedpkg tool to do scratch builds. To create a scratch
build from changes you haven't committed, do the following:

::

    rpmbuild -bs foo.spec
    koji build --scratch rawhide foo.srpm

From the latest git commit:

::

    koji build --scratch rawhide 'git url'

Warning: Scratch builds will *not* work correctly if your .spec file
does something different depending on the value of %fedora, %fc9, and so
on. Macro values like these are set by the *builder*, not by koji, so
the value of %fedora will be for whatever created the source RPM, and
*not* what it's being built on. Non-scratch builds get around this by
first re-building the source RPM.

If you have committed the changes to git and you are in the current
branch, you can do a scratch build with fedpkg tool which wraps the koji
command line tool with the appropriate options:

::

    fedpkg scratch-build

if you want to do a scratch build for a specific architecture, you can
type:

::

    fedpkg scratch-build-<archs>

 can be a comma separated list of several architectures.

finally is possible to combine the scratch-build command with a specific
koji tag in the form:

::

    fedpkg scratch-build --target TARGET

fedpkg scratch-build --help or koji build --help for more information.

Build Failures
--------------

If your package fails to build, you will see something like this:

::

    420066 buildArch kernel-2.6.18-1.2739.10.9.el5.jjf.215394.2.src.rpm,
    ia64): open (build-1.example.com) -> FAILED: BuildrootError:
    error building package (arch ia64), mock exited with status 10

You can figure out why the build failed by looking at the log files. If
there is a build.log, start there. Otherwise, look at init.log.

Logs can be found via the web interface in the Task pages for the failed
task. Alternatively the koji client can be used to view the logs via the
``watch-logs`` command. See the help output for more details.

Advanced use of Koji
--------------------

We've tried to make Koji self-documenting wherever possible. The command
line tool will print a list of valid commands and each command supports
--help. For example:

::

    $ koji help

    Koji commands are:
    build                Build a package from source
    cancel-task          Cancel a task
    help                 List available commands
    latest-build         Print the latest builds for a tag
    [...] 

::

    $ koji build --help

    usage: koji build [options]  tag URL
    (Specify the --help global option for a list of other help options)

    options:
    -h, --help            show this help message and exit
    --skip-tag            Do not attempt to tag package
    --scratch             Perform a scratch build
    --nowait              Don't wait on build
    [...] 

Using koji to generate a mock config to replicate a buildroot
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

koji can be used to replicate a build root for local debugging

::

    koji mock-config --help
    Usage: koji mock-config [options] name
    (Specify the --help global option for a list of other help options)

    Options:
      -h, --help            show this help message and exit
      --arch=ARCH           Specify the arch
      --tag=TAG             Create a mock config for a tag
      --task=TASK           Duplicate the mock config of a previous task
      --buildroot=BUILDROOT
                            Duplicate the mock config for the specified buildroot
                            id
      --mockdir=DIR         Specify mockdir
      --topdir=DIR          Specify topdir
      --topurl=URL          url under which Koji files are accessible
      --distribution=DISTRIBUTION
                            Change the distribution macro
      -o FILE               Output to a file

for example to get the latest buildroot for dist-f12-build run

::

    koji mock-config --tag dist-f12-build --arch=x86_64 --topurl=https://kojipkgs.fedoraproject.org/ dist-f12

you will need to pass in --topurl=https://kojipkgs.fedoraproject.org/ to
any mock-config command to get a working mock-config from fedoras koji.


.. _tuning-mock-per-tag:

Tuning mock's behavior per tag
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Few options for mock can be configured per-tag. These options are stored in
tag info's *extra* field. Extra values can be checked via `koji taginfo`
command.  Example for forcing `dnf` usage in specific build
environment follows:

::

    koji edit-tag dnf-fedora-tag -x mock.package_manager=dnf


* ``mock.package_manager`` - If this is set, it will override mock's default
  package manager. Typically used with ``yum`` or ``dnf`` values.
* ``mock.new_chroot`` - 0/1 value. If it is set, ``--new-chroot`` or
  `--old-chroot` option is appended to any mock call. If it is not set,
  mock's default behavior is used.
* ``mock.use_bootstrap`` - 0/1 value. If it is set, ``--bootstrap-chroot``
  is appended to the mock init call.  This tells mock to build in two stages,
  using chroot rpm for creating the build chroot. If it is not set, mock's
  default behaviour is used. (Note, that it changed in mock `1.4.1
  <https://github.com/rpm-software-management/mock/wiki/Feature-bootstrap>`_.
  Note, that it is not turn on by default by koji, as it is often not needed and
  it consumes additional resources (larger buildroot, downloading more data).
* ``mock.bootstrap_image`` - set to name of image, which can builder's podman
  download (e.g. ``fedora:32``). See mock's `doc
  <https://github.com/rpm-software-management/mock/wiki/Feature-container-for-bootstrap>`_
  before using this. You could need it, but do it with following
  recommendations:

  - you need to explicitly allow builders to do that (``mock_bootstrap_image =
    True`` in ``kojid.conf``).

  - you need to have builders with `podman <https://podman.io/>`_ installed and
    working.

  - use concrete hashes not potentially moving tags. Otherwise, you can get into
    harder debugging and auditing.

  - builders can consume space during time, no cleanup is made for podman's
    image cache. So, you'll probably want to run something like ``podman rmi
    `podman images -a --quiet``` periodically via cron or use some other
    cache-cleaning mechanism. Even simple task will consume roughly three times
    more space than without bootstrap image (downloaded image + exploded
    bootstrap dir + mock's buildroot itself)

  - be sure, that your podman is configured properly and it downloads images
    only from trusted sources. Note, that this setting effectivelly circumvents
    network isolation *inside* buildroot, as outside DNS, etc. can be spoofed.

  - this option will automatically turn ``mock.use_bootstrap`` (this is how
    it is implemented in mock)
* ``mock.yum.module_hotfixes`` - 0/1 value. If set, yum/dnf will use packages
  regardless if they come from modularity repo or not. It makes sense only for
  tags with external repositories. (See dnf `docs
  <https://dnf.readthedocs.io/en/latest/modularity.html#hotfix-repositories>`__)

* `mock signing plugin
  <https://github.com/rpm-software-management/mock/wiki/Plugin-Sign>`__ -
  Options ``mock.plugin_conf.sign_enable``, ``mock.plugin_conf.sign_opts.cmd``
  and ``mock.plugin_conf.sign_opts.opts`` are propagated to mock conf to be used
  by this plugin. Note, that these tools are run outside of the jailed env.
  Note, that this functionality doesn't interfere with koji's standard signing
  commands (``import-sig``, ``write-signed-rpm``, etc.). Note, that rpmsign vs
  gpg must be configured correctly. If it is not it a) can silently ignore
  problems during signing b) can hang forever when e.g. gpg password store is
  not accessible.

You may also specify per-tag environment variables for mock to use.
For example, to set the CC environment variable to clang, you could
do:

::

    koji edit-tag dnf-fedora-tag -x rpm.env.CC=clang


Using Koji to control tasks
^^^^^^^^^^^^^^^^^^^^^^^^^^^

List tasks:

::

    koji list-tasks

List only tasks requested by you:

::

    koji list-tasks --mine

requeue an already-processed task: general syntax is: koji resubmit
[options] taskID

::

    koji resubmit 3

Building a Package with the command-line tool
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Instead of using the fedpkg target, you can also directly use the
command\_line tool, koji.

To build a package, the syntax is:

::

    $ koji build <build target> <git URL>

For example:

::

    $ koji build dist-f14 'git url'

The koji build command creates a build task in Koji. By default the tool
will wait and print status updates until the build completes. You can
override this with the --nowait option.

.. raw:: html

   </pre>

NOTE: For fedora koji, the git url MUST be based on
pkgs.fedoraproject.org. Other arbitrary git repos cannot be used for
builds.

Koji tags and packages organization
-----------------------------------

Terminology
^^^^^^^^^^^

In Koji, it is sometimes necessary to distinguish between a package in
general, a specific build of a package, and the various rpm files
created by a build. When precision is needed, these terms should be
interpreted as follows:

-  Package: The name of a source rpm. This refers to the package in
   general and not any particular build or subpackage. For example:
   kernel, glibc, etc.
-  Build: A particular build of a package. This refers to the entire
   build: all arches and subpackages. For example: kernel-2.6.9-34.EL,
   glibc-2.3.4-2.19.
-  RPM: A particular rpm. A specific arch and subpackage of a build. For
   example: kernel-2.6.9-34.EL.x86\_64, kernel-devel-2.6.9-34.EL.s390,
   glibc-2.3.4-2.19.i686, glibc-common-2.3.4-2.19.ia64

Tags and targets
^^^^^^^^^^^^^^^^

Koji organizes packages using tags. In Koji a tag is roughly a
collection of packages:

-  Tags support inheritance
-  Each tag has its own list of valid packages (inheritable)
-  Package ownership can be set per-tag (inheritable)
-  When you build you specify a target rather than a tag

A build target specifies where a package should be built and how it
should be tagged afterwards. This allows target names to remain fixed as
tags change through releases.

Koji commands for tags
^^^^^^^^^^^^^^^^^^^^^^

Targets
'''''''

You can get a full list of build targets with the following command:

::

    $ koji list-targets

You can see just a single target with the --name option:

::

    $ koji list-targets --name dist-f14

    Name                           Buildroot                      Destination
    ---------------------------------------------------------------------------------------------
    dist-f14                     dist-f14-build                 dist-f14

This tells you a build for target dist-f14 will use a buildroot with
packages from the tag dist-f14-build and tag the resulting packages as
dist-f14.

Watch out: You probably don't want to build against dist-rawhide. If
Fedora N is the latest one out, to build to the next one, choose
dist-f{N+1}.

Tags
''''

You can get a list of tags with the following command:

::

    $ koji list-tags

Packages
''''''''

As mentioned above, each tag has its own list of packages that may be
placed in the tag. To see that list for a tag, use the list-pkgs
command:

::

    $ koji list-pkgs --tag dist-f14

The first column is the name of the package, the second tells you which
tag the package entry has been inherited from, and the third tells you
the owner of the package.

Latest Builds
'''''''''''''

To see the latest builds for a tag, use the latest-build command:

::

    $ koji latest-build --all dist-f14

The output gives you not only the latest builds, but which tag they have
been inherited from and who built them.

`Category:Package Maintainers <Category:Package Maintainers>`__

Koji XMLRPC API
===============

All features supported by command-line client are also accessible by XMLRPC
API. You can get listing of all available calls, arguments and basic help via
calling `koji list-api` command. This call will also provide you API
extensions provided by plugins in that particular koji instance.

Because of the data Koji routinely deals with, we use the following extensions
to the xmlrpc standard:

    * We use the ``nil`` extension to represent null values (e.g. None in
      Python). Koji's library handles this automatically. If you are using a
      different library, you may need to explicitly enable this (e.g. enabling
      allow_none in Python's own xmlrpc library).
    * We represent large integers with the ``i8`` tag. This standard is borrowed
      from Apache's `ws-xmlrpc <https://ws.apache.org/xmlrpc/types.html>`
      implementation. Python's own xmlrpc library understands this tag, even
      thought it will not emit it.
