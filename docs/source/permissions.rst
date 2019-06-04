=================
Permission system
=================

Basic privileges for koji are handled by ``permissions``. These are granted
and removed by ``admin`` user and allows other users to use different parts
of koji. There are some default permissions, but new ones can be created by
administrator and used in koji's :doc:`policies <defining_hub_policies>` or tag
locks.

Permission management
=====================

Admin user can use following koji CLI commands:

  * ``koji grant-permission [--new] <permission> <user> [<user> ...]`` for
    granting permission to one or more users. It can be also used to create
    new permission class with ``--new``.
  * ``koji revoke-permission <permission> <user> [<user> ...]`` for removing
    such permission from users.
  * ``koji list-permissions [--user <user>] [--mine]`` is self-descriptive.

Default permissions
===================

Administration
--------------

``admin``
  Basic permission, which can be delegated to other users. This
  is superadmin without any limitations, so grant with caution. Especially
  services should use some limited form instead of this.

``host``
  Restricted permission for handling host-related management tasks.

``tag``
  Permission for adding/deleting/editing tags

``target``
  Permission for adding/deleting/editing targets

Tasks
-----

``appliance``
  appliance tasks (``koji spin-appliance``)

``build``
  currently unused

``dist-repo``
  distRepo tasks (``koji dist-repo``)

``image``
  image tasks (``koji image-build``)

``livecd``
  livecd tasks (``koji spin-livecd``)

``repo``
  newRepo tasks (``koji regen-repo``)

``regen-repo``
  same as ``repo`` for now

Data Import
-----------
``image-import``
  used for importing external maven artifacts
  (``koji import-archive --type maven``)

``maven-import``
  used for importing external maven artifacts
  (``koji import-archive --type maven``)

``win-admin``
  used in default policy for windows builds ('vm' channel)

``win-import``
  used for importing external maven artifacts
  (``koji import-archive --type win``)
