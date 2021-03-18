=============================
Setting RPM Macros for Builds
=============================

The values of RPM macros can have significant effects on the results of RPM builds.
Note that the subject of RPM macros is complicated and goes well beyond Koji.
For the purposes of this document, we assume the reader is familiar with the basic concepts.

Further reading:

* https://rpm-guide.readthedocs.io/en/latest/rpm-guide.html#rpm-macros
* https://rpm.org/user_doc/macros.html
* https://rpm-packaging-guide.github.io/#more-on-macros

When Koji builds RPMs, it does so by running ``rpmbuild`` in a controlled build environment.
Inside that environment, ``rpm`` can pull macro values from multiple sources.

There are two basic ways to set rpm macro values for builds in Koji:

* using a build that places an rpmmacros file in the build environment
* setting ``rpm.macro.`` values for the build tag


Setting rpm macros with a build
===============================

Prior to Koji 1.18, this was the only way to set rpm macros in Koji.
This method is still valid, and in some cases preferred.
However, values set this way can be overridden by ``rpm.macro.*`` values set for the build tag.

In short, this method involves:

* creating an rpm build that places an rpm macros file in the buildroot
* requiring this build to be installed in the build environment

This might be a very simple build that only provides a single rpm macros file.
Such files will be read by ``rpm`` when they are installed into ``/etc/rpm`` or
``/usr/lib/rpm/macros.d/``.

There are many examples of this.
In Fedora, there are numerous packages like ``python-rpm-macros``, ``perl-macros``, and
``systemd-rpm-macros``.
Other packages might package such macro files alongside other content.
The ``ansible`` package is currently an example of this.

*In order for such a build to affect the build environment, it must be installed there.*
First the build needs to be in the build tag, either tagged there directly or indirectly via 
inheritance.
Second, the package needs to be either part of the base buildroot install, or pulled in via
build requirements.

Often, you want to make sure these macros affect *all* builds for a tag.
This means making your macros build part of the base install for the buildroot.
This can be done by adding the rpm name to the ``build`` group for the tag.

::

$ koji add-group-pkg f33-build build my-custom-rpm-macros

If your macro also needs to be available when building source rpms (e.g. ``%dist``), then you'll
also want to add it to the the ``srpm-build`` group.

::

$ koji add-group-pkg f33-build build my-custom-rpm-macros


Setting rpm.macro values
========================

(this feature was added in :doc:`Koji 1.18 <release_notes/release_notes_1.18>`)

As a convenience, Koji will honor any ``rpm.macro.NAME`` values in the "tag extra" settings for
a given build tag.
These values can be set by tag administrators with the ``edit-tag`` command and viewed with
the ``taginfo`` command.
For example, to set the ``dist`` macro value, you could use a command like the following:

::

$ koji edit-tag f33-build -x rpm.macro.dist=.fc33

This will cause Koji to pass this value to ``mock`` when constructing the buildroot.
These values are placed in the mock configuration file.

**Use case**

This feature is best used for macros with simple values that need to be managed by tag administrators.
The canonical example is managing the ``%dist`` macro, but other simple macros would also make sense.

We do not recommend setting complicated macros in this way.
E.g. macros that contain complex expansions, or those that are central to the rpmbuild process.


**Inheritance**

In Koji, the "tag extra" values are inherited.
So, by default, any tag a given build tag inherits from will contribute its settings.
The exception is if the inheritance line has the ``noconfig`` flag set.


**Priority over macros builds**

Koji places these macro values in the ``mock`` configuration file in for the buildroot.
The ``mock`` program places them in the ``.rpmmacros`` file in the build directory, which causes
them to take priority over other macros defined in the build environment.

In short, this method for setting rpm macros "wins".

This can be important when other build tags inherit from yours.
If the child tag has its own macros build, but inherits your ``rpm.macro.*`` setting, then the
inherited value will win.
