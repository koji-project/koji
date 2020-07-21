======================
Exporting repositories
======================

There are multiple ways to export repositories from koji. In first place,
koji is not a repository manager - it is a build system. Anyway, due to
architecture and build logic it knows about some repositories, typically those
needed to populate buildroots. These are stored at
``<topdir>/repos/<tag_name>/<repo_id>`` and can be consumed by builders via
http. Of course, other users can download them also. Anyway, these repos are by
design not suited for distribution.

The simplest way to create a distribution-ready repo is to use the ``koji dist-repo``
command. It allows a user with ``dist-repo`` permission (non-default requirements
can be specified via :doc:`hub policy <defining_hub_policies>`. The ``dist-repo``
command takes two basic arguments, where first is the name of the tag, while
second is signing key id. You can create also repositories from unsigned rpms by
supplying a nonsense signing key and adding ``--allow-missing-signatures``.
Further options can tell koji if debuginfo or source rpms are needed, if zck
dictionaries or multilib support should be used, etc. Feel free to go through
whole ``koji dist-repo --help``.

If you're aiming to have more control about repositories, varieties of
distribution flavours, etc. use `pungi <https://pagure.io/pungi/>`_ which can
create whole composes and which uses koji for some of the subtasks. Pungi + koji
is what Fedora currently uses for composes.
