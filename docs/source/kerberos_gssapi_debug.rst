==============================
Koji Kerberos/GSSAPI debugging
==============================

Run basic command Koji with debug option isn't help to debug Kerberos/GSSAPI issue.
In successful call you'll see what authentication method was used and was is the
koji server connected to:

::

    $ kinit my_account@FEDORAPROJECT.ORG
    Password for my_account@FEDORAPROJECT.ORG:

    $ koji hello
    successfully connected to hub
    dobrý den, my_account!

    You are using the hub at https://koji.fedoraproject.org/kojihub
    Authenticated via GSSAPI

...or you can get some error:

::

    $ koji hello
    2021-04-23 09:45:22,732 [ERROR] koji: (gssapi auth failed: requests.exceptions.HTTPError: 401 Client Error: Unauthorized for url: https://koji.fedoraproject.org/kojihub/ssllogin)
    Use following documentation to debug kerberos/gssapi auth issues. https://docs.pagure.org/koji/kerberos_gssapi_debug/
    2021-04-23 09:45:22,734 [ERROR] koji: GSSAPIAuthError: unable to obtain a session (gssapi auth failed: requests.exceptions.HTTPError: 401 Client Error: Unauthorized for url: https://koji.fedoraproject.org/kojihub/ssllogin)
    Use following documentation to debug kerberos/gssapi auth issues. https://docs.pagure.org/koji/kerberos_gssapi_debug/

In this case we see not one but two errors while trying to authenticate. Let's
see what more info we can get:

::

    $ KRB5_TRACE=/dev/stdout python koji -d hello
    2021-04-23 09:47:58,730 [DEBUG] koji: Opening new requests session
    2021-04-23 09:47:58,731 [DEBUG] koji: Opening new requests session
    2021-04-23 09:47:59,446 [DEBUG] koji: Opening new requests session
    2021-04-23 09:47:59,446 [ERROR] koji: (gssapi auth failed: requests.exceptions.HTTPError: 401 Client Error: Unauthorized for url: https://koji.fedoraproject.org/kojihub/ssllogin)
    Use following documentation to debug kerberos/gssapi auth issues. https://docs.pagure.org/koji/kerberos_gssapi_debug/
    Traceback (most recent call last):
      File "/usr/bin/koji", line 335, in <module>
        rv = locals()[command].__call__(options, session, args)
      File "/home/tkopecek/cvs/koji/cli/koji_cli/commands.py", line 7496, in handle_moshimoshi
        activate_session(session, options)
      File "/home/tkopecek/cvs/koji/cli/koji_cli/lib.py", line 749, in activate_session
        session.gssapi_login(proxyuser=runas)
      File "/home/tkopecek/cvs/koji/koji/__init__.py", line 2513, in gssapi_login
        raise GSSAPIAuthError(err)
    koji.GSSAPIAuthError: unable to obtain a session (gssapi auth failed: requests.exceptions.HTTPError: 401 Client Error: Unauthorized for url: https://koji.fedoraproject.org/kojihub/ssllogin)
    Use following documentation to debug kerberos/gssapi auth issues. https://docs.pagure.org/koji/kerberos_gssapi_debug/

We see no output from krbV library. It indicates that there was no significant
interaction with the library. Main reason would be missing ``kinit``. Fixing
this problem is pretty easy. What about other problems?

You can see wrong URL for the hub. Check if it is coming from system-wide config
``/etc/koji.conf`` or anything in ``/etc/koji.conf.d`` or ``~/.koji/config``.
Maybe URL for your instance has changed or some old config was forgotten in
place.

Compare with successful output when krbV library does its work:

::

    $ KRB5_TRACE=/dev/stdout koji -d hello
    2021-04-23 09:50:34,442 [DEBUG] koji: Opening new requests session
    2021-04-23 09:50:34,442 [DEBUG] koji: Opening new requests session
    [36315] 1619164236.523876: TXT record _kerberos.koji.fedoraproject.org. not found
    [36315] 1619164236.523877: TXT record _kerberos.fedoraproject.org. found: FEDORAPROJECT.ORG
    [36315] 1619164236.523878: ccselect module realm chose cache FILE:/tmp/krb5cc_1000 with client principal my_account@FEDORAPROJECT.ORG for server principal HTTP/koji.fedoraproject.org@FEDORAPROJECT.ORG
    [36315] 1619164236.523879: Getting credentials my_account@FEDORAPROJECT.ORG -> HTTP/koji.fedoraproject.org@ using ccache FILE:/tmp/krb5cc_1000
    [36315] 1619164236.523880: Retrieving my_account@FEDORAPROJECT.ORG -> HTTP/koji.fedoraproject.org@ from FILE:/tmp/krb5cc_1000 with result: -1765328243/Matching credential not found (filename: /tmp/krb5cc_1000)
    [36315] 1619164236.523881: Retrying my_account@FEDORAPROJECT.ORG -> HTTP/koji.fedoraproject.org@FEDORAPROJECT.ORG with result: -1765328243/Matching credential not found (filename: /tmp/krb5cc_1000)
    [36315] 1619164236.523882: Server has referral realm; starting with HTTP/koji.fedoraproject.org@FEDORAPROJECT.ORG
    [36315] 1619164236.523883: Retrieving my_account@FEDORAPROJECT.ORG -> krbtgt/FEDORAPROJECT.ORG@FEDORAPROJECT.ORG from FILE:/tmp/krb5cc_1000 with result: 0/Success
    [36315] 1619164236.523884: Starting with TGT for client realm: my_account@FEDORAPROJECT.ORG -> krbtgt/FEDORAPROJECT.ORG@FEDORAPROJECT.ORG
    [36315] 1619164236.523885: Requesting tickets for HTTP/koji.fedoraproject.org@FEDORAPROJECT.ORG, referrals on
    [36315] 1619164236.523886: Generated subkey for TGS request: aes256-cts/A108
    [36315] 1619164236.523887: etypes requested in TGS request: aes256-cts, aes128-cts, aes256-sha2, aes128-sha2, rc4-hmac, camellia128-cts, camellia256-cts
    [36315] 1619164236.523889: Encoding request body and padata into FAST request
    [36315] 1619164236.523890: Sending request (977 bytes) to FEDORAPROJECT.ORG
    [36315] 1619164236.523891: Sending DNS URI query for _kerberos.FEDORAPROJECT.ORG.
    [36315] 1619164236.523892: URI answer: 10 1 "krb5srv:m:kkdcp:https://id.fedoraproject.org/KdcProxy/"
    [36315] 1619164236.523893: Resolving hostname id.fedoraproject.org
    [36315] 1619164236.523894: TLS certificate name matched "id.fedoraproject.org"
    [36315] 1619164236.523895: Sending HTTPS request to https 152.19.134.142:443
    [36315] 1619164237.522076: Received answer (929 bytes) from https 152.19.134.142:443
    [36315] 1619164237.522077: Terminating TCP connection to https 152.19.134.142:443
    [36315] 1619164237.522078: Response was from master KDC
    [36315] 1619164237.522079: Decoding FAST response
    [36315] 1619164237.522080: FAST reply key: aes256-cts/F6DC
    [36315] 1619164237.522081: TGS reply is for my_account@FEDORAPROJECT.ORG -> HTTP/koji.fedoraproject.org@FEDORAPROJECT.ORG with session key aes256-cts/A3FF
    [36315] 1619164237.522082: TGS request result: 0/Success
    [36315] 1619164237.522083: Received creds for desired service HTTP/koji.fedoraproject.org@FEDORAPROJECT.ORG
    [36315] 1619164237.522084: Storing my_account@FEDORAPROJECT.ORG -> HTTP/koji.fedoraproject.org@ in FILE:/tmp/krb5cc_1000
    [36315] 1619164237.522086: Creating authenticator for my_account@FEDORAPROJECT.ORG -> HTTP/koji.fedoraproject.org@, seqnum 742219461, subkey aes256-cts/1CC1, session key aes256-cts/A3FF
    successfully connected to hub
    dobrý den, my_account!

    You are using the hub at https://koji.fedoraproject.org/kojihub
    Authenticated via GSSAPI


Most problems could be tracked down by this command plus kinit/klist tools. for
list of these consult next section.

General problems
================
* *No KRB5_TRACE output* - You've not run ``kinit`` in first place, run ``kinit``.
* If yes, maybe ticket is no longer valid - check ``klist`` + run ``kinit``
* *Hub URL is wrong* - check configs, find out right URL for your environment,
  update related packages (e.g. ``fedora-packager``)
* *Wrong service ticket* - e.g. because your instance is hidden behind a proxy.
  In such a case, you'll see a wrong principal in the output, such as e.g.
  ``HTTP/proxy10.fedoraproject.org@FEDORAPROJECT.ORG``. Kerberos
  authentication will fail because ``krbV`` will try to fetch a service ticket for
  PTR instead of a DNS record, effectively asking for a wrong service.
  The correct form is ``HTTP/koji.fedoraproject.org@FEDORAPROJECT.ORG``
  (also listed as "Ticket Server" in klist output). This problem is usually
  caused by a wrong value of ``dns_canonicalize_hostname`` in ``/etc/krb5.conf``.
  Please try setting it to ``true``, ``fallback`` and ``false`` in turn,
  as different values may be required depending on your situation.
* *You can't get service ticket at all*. You've not set up the ``/etc/krb5.conf``
  for relevant KDC/REALM. It shouldn't happen if you were able to ``kinit`` with
  the correct credentials (It means that you've already set up something).
  Anyway, you'll see following in the debug output
* *Your user account was disabled* This error is not krbV specific. But you can
  hit it. In such case you will see simple message ``koji: AuthError: unable to
  obtain a session``. From security reasons we don't display it differently from
  non-existent account. If you've suspicion that it could be the reason you need
  to check with your koji instance admin.
