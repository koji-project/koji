======================
Exporting repositories
======================

Koji provides some *limited* features for exporting repositories of RPMs.
Please note that Koji is a build system, not a repository manager, and these
features are secondary.
If you need more robust repository generation than Koji provides, then you may
want to look into using `pungi <https://pagure.io/pungi/>`_.


Koji's internal repositories
============================

Koji uses yum repositories as part of its build process for RPMs.
These repositories are used by the builders to generate buildroots.
Their generation is focused on that purpose, and they are not really suitable
for export.
However, they can be useful for simple cases.

Koji's internal repositories can be accessed at
``<topdir>/repos/<tag_name>/<repo_id>``
For a given tag name, there will be multiple repo ids over time as tag content
changes.
The current repo for a given tag can be determined with a call to ``getRepo``.

For convenience, Koji also maintains a "latest" symlink for each tag:
``<topdir>/repos/<tag_name>/latest``.
Please note that this symlink changes over time, which could break a yum transaction.


Dist-repos
==========

The simplest way to create a distribution-ready repo is to use the ``koji dist-repo``
command.
It allows users with access to generate a more robust yum repository from the
contents of a given tag.
These repos differ from the internal ones in several key ways:

* generation is user-controlled via the ``dist-repo`` command
* supports using signed rpms
* supports multilib
* allows for more customized comps data
* supports deltarpm generation
* can split debuginfo into separate repos
* can generate zchunk files

**Access control**

In order to use the ``dist-repo`` command, a user must satisfy one of the
following:

* have the ``dist-repo`` permission
* have the ``admin`` permission
* satisfy the requirements of the ``dist_repo`` policy

For more information about hub policies, see :doc:`defining_hub_policies`.


**Usage**

The ``dist-repo`` command takes a tag name and one or more key ids for signing keys.

..

    koji dist-repo [options] <tag> <key_id> [<key_id> ...]

The ``tag`` argument must be a valid tag name.
The resulting repository will be based on the contents of that tag.
Any valid tag will work, whether or not it has an associated target.

Koji will attempt to find a signed copy for each rpm matching one
of the given ``key_id`` arguments (searching in the order given).
Normally, Koji will error if there is no matching signed copy for any of the
rpms.
This behavior can be modified with the ``--allow-missing-signatures`` or
``--skip-missing-signatures`` options.
The ``key_id`` argument may be omitted entirely if the
``--allow-missing-signatures`` option is specified.

Koji will export the repository to ``<topdir>/repos-dist/<tag_name>/<repo_id>``
The current dist repo for a given tag can be determined with a call to
``getRepo(dist=True)``. Similar to internal build repos, Koji also maintains a
"latest" symlink for each tag: ``<topdir>/repos-dist/<tag_name>/latest``.

Various features of repo generation (e.g. multilib support, delta rpms, or
zchunk files) are controlled via command options.
For a full list of options, see ``koji dist-repo --help``.

**Koji Hub plugin**

Fedora release engineering uses a hub plugin `tag2distrepo
<https://pagure.io/releng/tag2distrepo>`_ to automatically export dist-repos
for certain tags.

Beyond Koji
===========

If you're aiming to have more control about repositories, varieties of
distribution flavours, etc. use `pungi <https://pagure.io/pungi/>`_ which can
create whole composes and which uses Koji for some of the subtasks.
Pungi + koji is what Fedora currently uses for composes.
