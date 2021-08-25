hub.conf
--------
hub.conf is a standard .ini-like configuration file. Its main section is
called ``[hub]`` and contains the following options. They can occur anywhere.

Incomplete document
^^^^^^^^^^^^^^^^^^^

This document is a stub and does not cover all options.
Work to complete this document is tracked in `Issue 3073 <https://pagure.io/koji/issue/3073>`_

The old :doc:`Server HOW TO <server_howto>` doc also describes some hub configuration options.

Name verification
^^^^^^^^^^^^^^^^^
Currently we have two groups for name verification:
 - internal names
 - user names

Group internal names is currently used for:
 - archive type
 - btype
 - channel
 - external repo
 - group
 - host
 - kerberos
 - permission
 - tag
 - target
 - volume

Group user names is currently used for:
 - user
 - host

Host names are listed in both groups because hosts always have an associated user entry.

.. glossary::
    MaxNameLengthInternal = 256
        Set length of internal names. By default there is allowed length set up to 256.
        When length is set up to 0, length verifying is disabled.

    RegexNameInternal = ^[A-Za-z0-9/_.+-]+$
        Set regex for verify an internal names. When regex string is empty, verifying
        is disabled.

    RegexUserName = ^[A-Za-z0-9/_.@-]+$
        Set regex for verify a user name and kerberos. User name and kerberos have
        in default set up allowed '@' and '/' chars on top of basic name regex
        for internal names. When regex string is empty, verifying is disabled.
