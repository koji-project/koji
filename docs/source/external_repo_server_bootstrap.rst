====================================
External Repository Server Bootstrap
====================================

Bootstrapping a new External Repo Koji build environment
========================================================

These are the steps involved in pointing a new Koji server at external
repositories so that it can be used for building. This assumes that the Koji
hub is up, appropriate authentication methods have been configured, the Koji
repo administration daemon (``kojira``) is properly configured and running,
and at least one Koji builder (``kojid``) is properly configured and running.
All koji cli commands assume that the user is a Koji ``admin``.  If you need
help with these tasks, see the :doc:`server_howto`.

* Create a new tag. ::

    $ koji add-tag dist-foo

* Create a build tag with the desired arches, and the previously created tag
  as a parent. ::

    $ koji add-tag --parent dist-foo --arches "i386 x86_64 ppc ppc64" dist-foo-build

* Add an external repository to your build tag. Koji substitutes $arch for the
  arches in your build tag. The ``$`` needs to be escaped for the shell to send
  it though without interpreting it. See below for some additional examples of
  external repo URLs. ::

    $ koji add-external-repo -t dist-foo-build dist-foo-external-repo http://repo-server.example.com/path/to/repo/for/foo/\$arch/

  .. note::
    If you are adding multiple external repos, koji assigns a priority to each
    repo in FIFO order. This may cause updated packages to not be visible if a
    repo with older packages is ranked at a higher priority (lower numeric
    value). Use the ``-p`` flag to set specific repo priorities.

  .. note::
    This uses $arch NOT $basearch

  Koji behaves differently to the external repository based on which ``merge``
  mode is set for that. Merge modes can be set via ``-m`` option and are as
  follows:

    ``koji``
        Basic mode - koji expects, that that repo is complete and
        doesn't contain mixed content. It means that only rpms from one SRPM can
        be present in repo for given package.

        It runs ``mergerepos_c --koji`` Repositories generated via ``dist-repo``
        command (and all other repositories coming from koji` has these
        properties.

    ``bare``
        It runs ``mergerepos_c --pkgorigins --all``. It includes all rpms with
        same package name and architecture even if version or release is
        different. This one is needed for modular repos. ``createrepo_c`` 0.14+
        compiled with ``libmodule`` support needs to be installed on the
        builder. Nevertheless, only the first rpm with identical NEVRA is
        accepted.

    ``simple``
        It runs ``mergerepos_c --mode simple`` - we're least restrivtive with
        this type of repo. Even packages with identical NEVRA are accepted in
        such case. Simple mode is in ``createrepo_c`` suite from version 0.13.
        Reasons to use this compared to ``bare`` mode is a) you have older
        ``createrepo_c``, b) you really want to have all this identical NEVRAs
        in the repo.

* Create a build target that includes the tags you've already created. ::

    $ koji add-target dist-foo dist-foo-build

  At this point you can verify that your external repository is set with the
  "taginfo" command. You should see it listed under "External repos". Here is
  an example with several CentOS external repos::

    $ koji taginfo dist-foo-build
      Tag: dist-foo-build [740]
      Arches: x86_64
      Groups: build, srpm-build
      Tag options:
      This tag is a buildroot for one or more targets
      Current repo: repo#55077: 2017-11-29 03:34:18.847127
      Targets that build from this tag:
        dist-foo
      External repos:
          2 centos7-cr (http://mirror.centos.org/centos/7/cr/$arch/)
          3 centos7-extras (http://mirror.centos.org/centos/7/extras/$arch/)
          5 centos7-updates (http://mirror.centos.org/centos/7/updates/$arch/)
         10 centos7-os (http://mirror.centos.org/centos/7/os/$arch/)

* Create a ''build'' and ''srpm-build'' group associated with your build tag. ::

    $ koji add-group dist-foo-build build
    $ koji add-group dist-foo-build srpm-build

* Populate the ``build`` and ``srpm-build`` group with packages that will be
  installed into the minimal buildroot. You can find out what the is in the
  current groups for Fedora by running ``koji list-groups dist-f9-build``
  against the Fedora Koji instance. This is probably a good starting point for
  your minimal buildroot and srpm creation buildroot. If you are rebuilding
  Fedora packages, it is recommended that you add all packages listed in the
  Fedora Koji instance. ::

    $ koji add-group-pkg dist-foo-build build <pkg1> <pkg2> .....

* Add packages that you intend to build to your tag. ::

    $ koji add-pkg --owner <kojiuser> dist-foo <pkg1> <pkg2> .....

* Wait for the repo to regenerate, and you should now be able to run a build
  successfully.

Regenerating your repo
======================

koji doesn't monitor external repositories for changes by default.
Administrators can enable such bejaviour with setting ``check_external_repos =
true`` in ``kojira.conf`` (for details see :doc:`utils`). If it is not
enabled new repositories will be generated when packages you build land in a tag
that populates the buildroot or you manually regenerate the repository. you
should be sure to regularly regenerate the repositories manually to pick up
updates.

::

    $ koji regen-repo dist-foo-build

Examples of urls to use for external Repositories
=================================================

all these examples use mirrors.kernel.org please find the closest mirror
to yourself. Note that the Fedora minimal buildroots download ~100Mb
then build dependencies on top. these are downloaded each build you can
save a lot of network bandwidth by using a local mirror or running
through a caching proxy.

NOTE: this uses $arch **NOT** $basearch

Fedora 10
---------

::

    https://mirrors.kernel.org/fedora/releases/10/Everything/\$arch/os/
    https://mirrors.kernel.org/fedora/updates/10/\$arch/

CentOS 5 and EPEL
-----------------

::

    https://mirrors.kernel.org/centos/5/os/\$arch/
    https://mirrors.kernel.org/centos/5/updates/\$arch/
    https://mirrors.kernel.org/fedora-epel/5/\$arch/

Example tags and targets
========================

In the simplest setup, where you just want to build against what is
available in the external repositories, you may want to go with a simple
layout of *dist-f\ **X**-build* tags inheriting one another, and
*dist-f\ **X**-updates* tags and targets that inherit the
*dist-f\ **X**-build* tag and have external repos attached to them. This
way, a *dist-f\ **Y**-build* or *dist-f\ **Y**-updates* tag will not
automatically inherit the external repos of your *dist-f\ **X*** tags.

Tags
----

::

    dist-f10-updates               - This is where the external repos for f10 release and f10 updates are attached
     `- dist-f10-build             - This is the f10 build target with the 'build' and 'srpm-build' group inherited from dist-f9-build,
         |                           so that your buildroot gets populated but you do not have to maintain these groups for each
         |                           separate release.
         `- dist-f9-build          - etc.
             `- dist-f8-build      - etc.

Targets
-------

Each *dist-f\ **X**-build* tag has a *dist-f\ **X**-updates* child tag,
and each *dist-f\ **X**-updates* tag has a corresponding
*dist-f\ **X**-updates-candidate* build target.
