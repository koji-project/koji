=============
Koji Profiles
=============
This document describes how to work with koji profiles.


Command Line Interface
======================
Koji client allows connecting to multiple koji instances from CLI
by using profiles. The default profile is given by executable file name,
which is 'koji'.

To change koji profile, you can:

 * run koji with --profile=$profile_name argument
 * change executable file name by symlinking $profile_name -> koji


Configuration Files
===================
Configuration files are located in following locations:

 * /etc/koji.conf
 * /etc/koji.conf.d/\*.conf
 * ~/.koji/config.d/\*.conf
 * user-specified config

Koji reads them, looking for [$profile_name] sections.


Using Koji Profiles in Python
=============================
Instead of using koji module directly,
get profile specific module by calling::

    >>> mod = koji.get_profile_module($profile_name)

This module is clone of koji module with additional
profile specific tweaks.

Profile configuration is available via::

    >>> mod.config


Example
-------

Print configuration::

    import koji

    fedora_koji = koji.get_profile_module("koji")
    ppc_koji = koji.get_profile_module("ppc-koji")

    for i in (fedora_koji, ppc_koji):
        print("PROFILE: %s" % i.config.profile)
        for key, value in sorted(i.config.__dict__.items()):
            print("    %s = %s" % (key, value))
        print("")


Use ClientSession::

    import koji

    koji_module = koji.get_profile_module("koji")
    client = koji_module.ClientSession(koji_module.config.server)
    print(client.listTags())


TODO
====
* consider using pyxdg for user config locations
