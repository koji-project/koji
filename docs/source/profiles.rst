=============
Koji Profiles
=============

Koji clients can connect to multiple Koji instances via "profiles". These are
configuration sections that describe how to connect to different environments.


Command Line Interface
======================

By default, the ``koji`` CLI will use a profile named ``koji``. (This profile
is Fedora's production Koji environment.)

You can choose a different profile on the CLI. For example, to choose CentOS's
"cbs" profile instead:

 * Run ``koji`` with ``--profile=cbs``, for example ``koji --profile cbs
   list-hosts``.

 * Symlink or alias the profile name to the ``koji`` executable. For example,
   ``ln -s /usr/bin/koji /usr/bin/cbs`` or ``alias cbs=koji``. The CLI will
   use the executable name as the profile name, so you can simply run ``cbs
   list-hosts``.

Configuration Files
===================

The Koji client searches for profile definitions in the following locations:

 * ``/etc/koji.conf``
 * ``/etc/koji.conf.d/*.conf``
 * ``~/.koji/config.d/*.conf``
 * The ``--config=FILE`` option on the CLI

Koji reads all these files and searches for ``[$profile_name]`` sections. For
example, if you use a profile named ``cbs``, the Koji client will search for a
section titled ``[cbs]`` in the files.

Using Koji Profiles in Python
=============================

Instead of using the ``koji`` Python module directly, you can get a
profile-specific module by calling::

    mykoji = koji.get_profile_module("cbs")

This ``mykoji`` module is clone of the ``koji`` module with additional
profile-specific tweaks.

You can read all the settings in the profile configuration with the
``.config`` property::

    mykoji.config        # optparse.Values object
    vars(mykoji.config)  # plain python dict


Examples
--------

Print configurations for multiple profiles::

    import koji

    fedora_koji = koji.get_profile_module("koji")
    stage_koji = koji.get_profile_module("stg")

    for this_koji in (fedora_koji, stage_koji):
        print("PROFILE: %s" % this_koji.config.profile)
        for key, value in sorted(vars(this_koji.config).items()):
            print("    %s = %s" % (key, value))
        print("")


Use ``ClientSession`` to send RPCs to the hub::

    import koji

    mykoji = koji.get_profile_module("koji")
    client = mykoji.ClientSession(mykoji.config.server)
    print(client.listTags())
