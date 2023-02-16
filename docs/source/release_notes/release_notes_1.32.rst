
Koji 1.32.0 Release notes
=========================

All changes can be found in `the roadmap <https://pagure.io/koji/roadmap/1.32/>`_.
Most important changes are listed here.

Migrating from Koji 1.31/1.31.1
-------------------------------

For details on migrating see :doc:`../migrations/migrating_to_1.32`

Security Fixes
--------------

None

Client Changes
--------------
**download-tasks has sorted tasks in check closed/not closed tasks**

| PR: https://pagure.io/koji/pull-request/3672

Simple change to have deterministic output


API Changes
-----------
**Remove krbLogin API**

| PR: https://pagure.io/koji/pull-request/3599

This call is deprecated for long and should have been replaced by ``sslLogin``
everywhere. In this case ``sslLogin`` is backed up by GSSAPI.

**Add checksum API**

| PR: https://pagure.io/koji/pull-request/3628

We've added complete API for computing/storing/querying full file checksums for
individual RPM files.  Basic set of checksum types is computed when RPM is
imported into koji (via import or build task). This set is defined in
``hub.conf`` via ``RPMDefaultChecksums`` which is md5 and sha256 by default.
All users can query stored checksums via ``getRPMChecksums`` call.

Builder Changes
---------------
**Handle migrated rpmdb path**

| PR: https://pagure.io/koji/pull-request/3618

RPM db was in recent Fedora's moved from ``/var/lib/rpm`` to
``/usr/lib/sysimage/rpm``. For builds based on that koji was unable to determine
buildroot content correctly resulting in empty buildroot listings.

System Changes
--------------
**Use_fast_upload=True as default everywhere**

| PR: https://pagure.io/koji/pull-request/3530

It is seamless change for almost everybody. Fast upload mechanism is here for
more than ten years. Clients now has one less call to do (determining if server
supports it)

**rpmdiff: replace deprecated rpm call**

| PR: https://pagure.io/koji/pull-request/3562

``rpmdiff`` was adapted to current rpm API

**Move hub code to site-packages**

| PR: https://pagure.io/koji/pull-request/3588

We've moved hub code to site-packages allowing further refactoring. Important is
that _everybody_ needs to fix their ``httpd.conf`` to point to new app location:

.. code-block:: diff

  - Alias /kojihub /usr/share/koji-hub/kojixmlrpc.py
  + Alias /kojihub /usr/share/koji-hub/kojiapp.py

**Continuing internal refactoring for safer SQL handling.**

| PR: https://pagure.io/koji/pull-request/3589
| PR: https://pagure.io/koji/pull-request/3632
| PR: https://pagure.io/koji/pull-request/3668


**Fix default archivetypes extensions**

| PR: https://pagure.io/koji/pull-request/3614

Simple fix of default extensions for VHDX compressed images.

**unify migration scripts**

| PR: https://pagure.io/koji/pull-request/3624

Merged few older redundant migration scripts.

**Deprecated get_sequence_value**

| PR: https://pagure.io/koji/pull-request/3636

For plugin writers - this internal method is now deprecated and similar method
``koji.db.nextval`` should be used instead.

**Remove DisableGSSAPIProxyDNFallback option on Hub**

| PR: https://pagure.io/koji/pull-request/3649

Deprecated setting finally removed.

**replace deprecated distutils**

| PR: https://pagure.io/koji/pull-request/3654

We've dropped deprecated distutils.

**Add custom_user_metadata to build info for wrapperRPM build type**

| PR: https://pagure.io/koji/pull-request/3660

**Recreate timeouted session**

| PR: https://pagure.io/koji/pull-request/3664
| PR: https://pagure.io/koji/pull-request/3659
| PR: https://pagure.io/koji/pull-request/3657

Sessions now can have defined lifetime. After that they'll be marked as
``expired`` still allowing client to reauthenticate and reuse that session.
Calling ``logout`` will finally destroy the session with no possibility of
reviving. This change should be seamless for most users. (E.g. builder code
needed no change as it is completely transparent behaviour for pythong client)

Expiration time is not defined anywhere now. It is up to admins to either expire
sessions selectively or set up cron job expiring all sessions after some time.
If not handled, koji sessions will behave exactly same way as in previous
releases.

This is a new behaviour to improve koji's security.

Utilities
---------
**koji-gc: use history to query trashcan contents**

| PR: https://pagure.io/koji/pull-request/3608

Performance improvement lowering memory usage on the hub.

VM
--
**kojikamid: remove clamav scanner**

| PR: https://pagure.io/koji/pull-request/3584

As ClamAV is no more supported on cygwin, we're going to drop source and
artifcats scanning support for windows build expecting that this scanning should
happen outside of koji (or via plugin). We're not scanning any other artifact
type, so it makes more sense to outsource it here also.

Content Generator Changes
-------------------------
**metadata for koji task id**

| PR: https://pagure.io/koji/pull-request/3656

Metadata format was extended to allow linking to koji task. So new key
``metadata['build']['task_id']`` is allowed now. For OSBS there is a
compatibility fallback on ``metadata['extra']['container_koji_task_id']`` for
older builds.

Documentation
-------------
**Fix auth unit tests**

| PR: https://pagure.io/koji/pull-request/3661

**Improve help for call --python option**

| PR: https://pagure.io/koji/pull-request/3663
