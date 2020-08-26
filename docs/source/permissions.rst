=================
Permission system
=================

Permissions are used by Koji to control access in a number of ways.
Some permissions are built-in (e.g. ``admin``, ``repo``), but new ones can be
created by administrators.

The ``admin`` permission is special.
It grants superuser access and can stand in for any other permission.

Most of the built-in permissions control access to various hub calls.
For example, the ``dist-repo`` permission allows access to create dist repos.

Custom permissions can used as the required permission for a tag, or they can be
referenced in :doc:`hub policies <defining_hub_policies>`. Note, that you need
to first understand the policy mechanism as most permissions are reflected in
policy rules.


Permission management
=====================

Granting or removing permissions requires the ``admin`` permission.
A user with sufficient access can use the following koji CLI commands:

``koji grant-permission [--new] <permission> <user> [<user> ...]``\
    Grants permission to one or more users. It can be also used to create
    a new permission with the ``--new`` option.

``koji revoke-permission <permission> <user> [<user> ...]``
    Removes the named permission from users.

``koji list-permissions [--user <user>] [--mine]``
    Lists permissions in the system.


Built-in permissions
====================

Administration
--------------

The following permissions govern access to key administrative actions.


``admin``
  This is a superuser access without any limitations, so grant with caution.
  Users with admin effectively have every other permission.
  We recommend granting the smallest effective permission.

``host``
  Restricted admin permission for handling host-related management tasks.

``tag``
  Permission for adding/deleting/editing tags.  Allows use of the
  ``tagBuildBypass`` and ``untagBuildBypass`` API calls also. Note, that this
  name could be confusing as it is not related to tagging builds but to editing
  tags themselves. Tagging builds (and adding/removing packages from package
  lists for given tags) is handled by ``tag`` and ``package_list`` policies
  respectively.

``target``
  Permission for adding/deleting/editing targets


Tasks
-----

The following permissions grant access to trigger specialized tasks.

``appliance``
  appliance tasks (``koji spin-appliance``)

``dist-repo``
  distRepo tasks (``koji dist-repo``)

``image``
  image tasks (``koji image-build``)

``livecd``
  livecd tasks (``koji spin-livecd``)

``livemedia``
  livemedia tasks (``koji spin-livemedia``)

``regen-repo``
  This permission grants access to regenerate repos (i.e. to trigger
  ``newRepo`` tasks).

``win-admin``
  The default ``vm`` policy requires this permission to trigger Windows builds.


Data Import
-----------

The following import permissions allow a user to directly import build
artifacts of different types.
We recommend caution when granting these.
In general, it is better to use the
:doc:`content generator interface <content_generators>` rather than the direct
import calls these govern.

``image-import``
  used for importing external maven artifacts
  (``koji import-archive --type maven``)

``maven-import``
  used for importing external maven artifacts
  (``koji import-archive --type maven``)

``win-import``
  used for importing external maven artifacts
  (``koji import-archive --type win``)


Other
-----

These remaining permissions don't fit into other categories.

``build``
  Defined in the database but currently unused

``repo``
  This special permission is only intended to be granted to the user that
  ``kojira`` runs as.
  It grants access to regenerate and expire repos, as well as flag them as
  deleted or broken.
  Do not grant this permission to normal users.
  The ``regen-repo`` permission can be used to grant access for regeneration
  only.

``sign``
  This permission grants access to add signatures to rpms and to write out
  signed copies (``koji import-sig`` and ``koji write-signed-rpm``).
