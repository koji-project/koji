==============================
Koji Kerberos/GSSAPI debugging
==============================

Run basic command Koji with debug option isn't help to debug Kerberos/GSSAPI issue.

::

    koji -d hello

Run following KRB5_TRACE command for debug Kerberos/GSSAPI auth issues:

::

    KRB5_TRACE=/dev/stdout python koji -d hello

Kerberos/GSSAPI debug results:

#. TGS request result: Server krbtgt/SERVER.COM not found in Kerberos database

   Used Kerberos which is not related to current Kerberos database.
