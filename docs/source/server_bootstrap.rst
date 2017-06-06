=====================
Koji Server Bootstrap
=====================

Bootstrapping a new Koji build environment
==========================================

These are the steps involved in populating a new Koji server with
packages so that it can be used for building. This assumes that the Koji
hub is up, appropriate authentication methods have been configured, the
Koji repo administration daemon (``kojira``) is properly configured and
running, and at least one Koji builder (``kojid``) is properly
configured and running. All koji cli commands assume that the user is a
Koji *admin*. If you need help with these tasks, see the
`ServerHowTo <Koji/ServerHowTo>`__ .

-  Download all source rpms and binary rpms for the arches you're
   interested in

-  Import all source rpms

::

    $ koji import /path/to/package1.src.rpm /path/to/package2.src.rpm ...

If the files are on the same volume as /mnt/koji, you can use
``koji import --link``, which hardlinks the files into place, avoiding
the need to upload them to the hub and **very significantly** increasing
import speed. When using ``--link``, you must run as root. It is
**highly** recommended that you use ``--link``.

-  Import all binary rpms using the same method as above

-  Create a new tag

::

    $ koji add-tag dist-foo

-  Tag all of the packages you just imported into the tag you just
   created

You can use ``koji list-untagged`` to get a list of all of the packages
you just imported.

::

    $ koji list-pkgs --quiet | xargs koji add-pkg --owner <kojiuser> dist-foo
    $ koji list-untagged | xargs -n 1 koji call tagBuildBypass dist-foo

We call the *tagBuildBypass* method instead of using ``koji tag-build``
because it doesn't require the builders to process *tagBuild* tasks one
at a time, but does the tagging directly. This will save a significant
amount of time, especially when tagging a large number of packages.

-  Create a build tag with the desired arches, and the previously
   created tag as a parent

::

    $ koji add-tag --parent dist-foo --arches "i386 x86_64 ppc ppc64" dist-foo-build

-  Create a build target that includes the tags you've already created

::

    $ koji add-target dist-foo dist-foo-build

-  Create a *build* group associated with your build tag

::

    $ koji add-group dist-foo-build build

-  Populate the *build* group with packages that will be installed into
   the minimal buildroot

You can find out what the current build group for Fedora is by running
``koji -s https://$ARCH.koji.fedoraproject.org/kojihub list-groups f17-build``
against the Fedora Koji instance for your $ARCH. This is probably a good
starting point for your minimal buildroot.

::

    $ koji add-group-pkg dist-foo-build build pkg1
    $ koji add-group-pkg dist-foo-build build pkg2

If you want to fully duplicate Fedora's group data for a tag, then it would be
easier to do it in bulk -- export Fedora's data and import it to your build
tag.

::

    $ koji -s https://$ARCH.koji.fedoraproject.org/kojihub show-groups --comps f17-build > comps.xml
    $ koji import-comps comps.xml dist-foo-build

-  regenerate the repo

::

    $ koji regen-repo dist-foo-build

-  Wait for the repo to regenerate, and you should now be able to run a
   build successfully.
