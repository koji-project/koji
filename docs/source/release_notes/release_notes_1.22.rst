Koji 1.22.0 Release notes
=========================

Important: python 2 support for hub and web have been dropped in koji 1.22,
meanwhile CLI and builder are still supporting python2. Please prepare your hub
and web service for python3 if you are going to upgrade them to koji 1.22.

All changes can be found at `pagure <https://pagure.io/koji/roadmap/1.22/>`_.
Most important changes are listed here.


Migrating from Koji 1.21/1.21.1
-------------------------------

For details on migrating see :doc:`../migrations/migrating_to_1.22`


Security Fixes
--------------

None


Client Changes
--------------

**Output extra['rpm.macro.*'] to mock-config**

| PR: https://pagure.io/koji/pull-request/2255

The ``mock-config`` command honors 'rpm.macro.*' options in tag's extra config now.

**--ca option has been deprecated**

| PR: https://pagure.io/koji/pull-request/2182
| PR: https://pagure.io/koji/pull-request/2246

This option is deprecated for a while and not used internally. We added the
deprecation warning and will finally remove it in 1.24.
Notes: It is deprecated in koji-gc as well.

**Flush stdout during watch-logs**

| PR: https://pagure.io/koji/pull-request/2228

Calling ``flush()`` immediately to display the output faster for PY3.

**Do not try unnecessary authentication**

| PR: https://pagure.io/koji/pull-request/2228

In some CLI commands we used ``active_session()`` which will try its best to
login, but it is not necessary. Now, we only ensure the connection without
authentication.

**Unify --debug options**

| PR: https://pagure.io/koji/pull-request/2085

The cli accepts a global ``--debug`` option before the command name.
Some commands accepted a separate ``--debug`` option local to the command,
which was confusing.
Now these commands take their cue from the global option.
The local option is still accepted for backwards compatibility, though
it has been hidden in the help output.

The following commands were affected:

* ``prune-sigs``
* ``list-signed``
* ``list-tag-history``
* ``list-history``

**New option --wait for download-task**

| PR: https://pagure.io/koji/pull-request/2346

This is a UE enhancement to let the command be able to wait for the tasks to be
finished as the same as the behavior of ``build`` command.

**Fix image-build-indirection --wait**

| PR: https://pagure.io/koji/pull-request/2347

Previously, the ``image-build-indirection`` command accepted the ``--wait``
option, but did not honor it.
This oversight has been fixed.

**Fix event option handling in clone-tag**

| PR: https://pagure.io/koji/pull-request/2364

The ``getTag()`` call for fetching source tag info in ``clone_tag`` didn't use event
before. Now, it does.


Library Changes
---------------

**Correctly identify "hostname doesn't match" errors**

| PR: https://pagure.io/koji/pull-request/2266

"hostname doesn't match" can be identified as a certificate error, so that
client will not retry the request.

**openRemoteFile retries and checks downloaded content**

| PR: https://pagure.io/koji/pull-request/2254

Sometimes we hit a problem with incorrect downloads caused by various
malfunctions, like cache, filesystem, network, etc. Now, in
``openRemoteFile``, we are going to

* compare http's ``Content-Length`` header with the data we really downloaded
* check the rpm header is valid if the file is an RPM
* do 3 times retries if it fails


API Changes
-----------

**filterResults and countAndFilterResults raise GenericError**

| PR: https://pagure.io/koji/pull-request/2150

API ``filterResults`` and ``countAndFilterResults`` now raise
``koji.GenericError`` instead of ``xmlrpc.client.Fault`` when method's keyword
argument is not expected.

**Deprecation of host.getTask call**

| PR: https://pagure.io/koji/pull-request/2238
| PR: https://pagure.io/koji/pull-request/2264

This host API will be finally removed in 1.23

**Optimizations to the listBuildroots call**

| PR: https://pagure.io/koji/pull-request/2299
| PR: https://pagure.io/koji/pull-request/2303
| PR: https://pagure.io/koji/pull-request/2301

For the optimization purpose, the ``listBuildroots`` API call avoids
unnecessary checks when the return will be empty.

Additionally, the call avoids some table joins that can slow down the queries
in some cases.
As a result, the return value will no longer include the ``is_update`` field
when querying by ``rpmID``.

**Disable notifications by default in [un]tagBuildBypass calls**

| PR: https://pagure.io/koji/issue/2292

The ``notify`` option to the ``tagBuildBypass`` and ``untagBuildBypass`` now defaults to False.
Tools that wish to generate email notifications will need to explicitly pass ``notify=True``.

**Fix a typo in the error message of getChangelogEntries**

| PR: https://pagure.io/koji/pull-request/2338

**A new option - pattern for listTags call**

| PR: https://pagure.io/koji/pull-request/2320
| PR: https://pagure.io/koji/pull-request/2348
| PR: https://pagure.io/koji/pull-request/2387

This option is a GLOB match pattern for the name of tag. You can now directly
call ``session.listTags(pattern='prefix-*-postfix')`` for example, to filter the
result list on server side. The ``list-tags`` command tries its best to call it with
``pattern`` as well.


Builder Changes
---------------

**Koji now supports Mock's bootstrap chroot and image**

| PR: https://pagure.io/koji/pull-request/2166
| PR: https://pagure.io/koji/pull-request/2212
| PR: https://pagure.io/koji/pull-request/2372
| PR: https://pagure.io/koji/pull-request/2328

Koji now supports Mock's ``--bootstrap-chroot`` and ``--bootstrap-image``
options. See:

* `Bootstrap chroot <https://github.com/rpm-software-management/mock/wiki/Feature-bootstrap>`_
* `Container for bootstrap <https://github.com/rpm-software-management/mock/wiki/Feature-container-for-bootstrap>`_

For the configuration on koji, please refer to :doc:`../using_the_koji_build_system`.
The bootstrap buildroot will be pruned automatically by kojid as the same as the
normal buildroot.

**Pass bootloader append option to livemedia builds**

| PR: https://pagure.io/koji/pull-request/2262

Koji is now able to pass ``--extra-boot-args --append="bootloader --append"``
options to ``livemedia-creator`` tool for livemedia builds.

**Per-tag environment variables in Mock's buildroot**

| PR: https://pagure.io/koji/pull-request/2064

Now, you can set ``rpm.env.*`` in build tag's ``extra`` to specify environment
variables in mock's buildroot. See :doc:`../using_the_koji_build_system`.

**Support specific per-settings for Mock's sign plugin**

| PR: https://pagure.io/koji/pull-request/1932
| PR: https://pagure.io/koji/pull-request/2337

We are now providing ``mock.plugin_conf.sign_enable``,
``mock.plugin_conf.sign_opts.cmd`` and ``mock.plugin_conf.sign_opts.opts`` in
build tag's ``extra`` for enabling and configuring the sign plugin of mock. For
more details, see :doc:`../using_the_koji_build_system`.

**Per-tag settings of yum's depsolver policy for Mock**

| PR: https://pagure.io/koji/pull-request/1932

``mock.yum.best=0/1`` is available in tag's extra config for the corresponding
setting of mock config.

**Use mergerepo_c for all merge modes**

| PR: https://pagure.io/koji/pull-request/2376

As ``mergerepo_c`` has supported ``simple`` mode since 0.13.0, we now use it on
python3 or ``use_createrepo_c=True`` kojid for repo creation. And as `issues/213
<https://github.com/rpm-software-management/createrepo_c/issues/213>`_ of
``createrepo_c`` has been fixed in 0.15.11, we also append ``--arch-expand`` on
demand. Therefore, koji are now able to use ``mergerepo_c`` for all 3 modes: koji,
simple, bare. Nevertheless, we are still providing ``mergerepos`` scripts for
python2.

**Turn off dnf_warning in mock.cfg**

| PR: https://pagure.io/koji/pull-request/2353

In `PR #1595 <https://pagure.io/koji/pull-request/1595>`_, we set
``dnf_warning=True`` when we started to add this configuration. But since Mock
2.0, ``bootstrap_chroot`` is set to ``True`` by default, we need to set
``dnf_warning`` to ``False`` accordingly. For the details, please refer to
`issue #2026 <https://pagure.io/koji/issue/2026>`_.

**BuildSRPMFromSCMTask: Support auto-selecting a matching specfile name**

| PR: https://pagure.io/koji/pull-request/2257

When building SRPM from SCM, if there are more than one ``*.spec`` found in root
directory, or ``support_rpm_source_layout=yes`` in ``/etc/kojid/kojid.conf`` and
there are more than one ``*.spec`` found in ``SPECS`` directory, the builder is
going to use the specfile with the SCM repo's name in root or ``SPECS`` dir.

**Pass buildroot to preSCMCheckout and postSCMCheckout where applicable**

| PR: https://pagure.io/koji/pull-request/2123

The ``preSCMCheckout`` and ``postSCMCheckout`` callbacks for kojid now include
a ``buildroot`` field that provides access to the internal ``BuildRoot``
object, when such an object is available.
This change impacts ``BuildMavenTask``, ``WrapperRPMTask``, ``ImageTask`` and
``BuildSRPMfromRPMTask``.
The current exceptions are ``OzImageTask`` and ``BuildIndirectionImageTask``,
which do not use this type of buildroot.

Any plugins that use this field should be aware that the behavior of this class
may change across releases.


Web UI Changes
--------------

**A new repoinfo page**

| PR: https://pagure.io/koji/pull-request/2193

The new page displays basic information of a normal repo, linked by the repo id
on taskinfo and buildrootinfo page.


Win Builder Changes
-------------------

**Clone mac address via xml**

| PR: https://pagure.io/koji/pull-request/2290

We've hit a problem that while VM is being cloned, the mac address cloning is
refused and a new one is assigned instead. We are now using the xml file for mac
address setup.


System Changes
--------------

**Drop python2 support for hub and web**

| PR: https://pagure.io/koji/pull-request/2218
| PR: https://pagure.io/koji/pull-request/2342

Finally, python2 support for hub and web have been dropped in this release.

**Drop krbV support**

| PR: https://pagure.io/koji/pull-request/2244
| PR: https://pagure.io/koji/pull-request/2151

``krbV`` support has been finally removed from this release. For more information, please refer to
:ref:`migration_krbv`.

**Use requests_gssapi for GSSAPI authentication**

| PR: https://pagure.io/koji/pull-request/2244
| PR: https://pagure.io/koji/pull-request/2401

``requests_gssapi`` is supported in this release. In all of the components we provide, we now try to
use ``request_gssapi`` at first, if it isn't installed, fallback to ``requests_kerberos`` then.

**DB: Use timestamps with timezone**

| PR: https://pagure.io/koji/pull-request/2237
| PR: https://pagure.io/koji/pull-request/2366

We have updated all our timestamp fields to include timezone.
This prevents time inconsistencies when the database has a timezone setting
other than UTC.

**DB: Update sessions_active_and_recent index**

| PR: https://pagure.io/koji/pull-request/2334

We have adjusted the ``sessions_active_and_recent`` index so that the planner
will actually use it.

**Log tracebacks for multicall**

| PR: https://pagure.io/koji/pull-request/2225

The exceptions inside multicall were not logged before. These tracebacks will
benefit us for debugging purpose, as we are often using multicall more and more.

**Fix build_notification crashing caused by recipients check**

| PR: https://pagure.io/koji/pull-request/2308
| PR: https://pagure.io/koji/pull-request/2309

This change fixes an inconsistency in the function where it would return
``None`` instead of an empty list as expected.

**Allow packagelist changes with 'tag' permission by the default policy**

| PR: https://pagure.io/koji/pull-request/2275

The ``tag`` permission was introduced in version 1.18 as part of an effort to
make admin permissions more granular.
This permission now grants access to make package list changes for tags
via the default ``package_list`` policy.

**Improve race condition for getNextRelease call and images**

| PR: https://pagure.io/koji/pull-request/2263

It was possible to meet the race condition in the old logic of image building.
We are now calling ``get_next_release()`` in the ``initImageBuild`` call if there is
ino release passed in, rather than calling ``getNextRelease`` in the ImageBuild
task individually. This would notably reduce the possibility of the race
condition.

**Replace MD5 with SHA-256 in most places**

| PR: https://pagure.io/koji/pull-request/2317

Koji should work on the FIPS enabled system where MD5 is disabled for security
reason. We are now using SHA-256 to replace MD5 for web token and file uploading,
but only keeping MD5 for RPM file processing.

**Remove "GssapiSSLonly Off" option**

| PR: https://pagure.io/koji/pull-request/2162

We have removed the ``GssapiSSLonly`` option from our example httpd
configuration.
It was previously shown in the example, set to ``Off``.
This is also the default in mod_auth_gssapi, but *it is not the recommended
setting*.
For more information, see `mod_auth_gssapi doc
<https://github.com/gssapi/mod_auth_gssapi#gssapisslonly>`_

**Remove "GssapiLocalName Off" option**

| PR: https://pagure.io/koji/pull-request/2351
| PR: https://pagure.io/koji/pull-request/2358

We have also removed the ``GssapiLocalName`` option from our example httpd
configurations.
Similar to the above, our example setting was already the default.

**Provide task-based data to volume policy**

| PR: https://pagure.io/koji/pull-request/2306

For builds with associated tasks, more information is now available to the volume policy.
In particular, the ``buildtag`` policy test should work for such builds.

Note that some builds (e.g. content generator builds and other imported builds) do not
have associated tasks.

For more information on hub policies, see :doc:`../defining_hub_policies`.

**Honor volume policy in host.importImage**

| PR: https://pagure.io/koji/pull-request/2359

This fixes a bug where an underlying function as ignoring the volume policy result.


Plugins
-------

sidetag
.......

**listSideTags also returns user info**

| PR: https://pagure.io/koji/pull-request/2132

We now provide an easier way to find the owner of sidetags

**Give koji admins the permission to operate sidetags**

| PR: https://pagure.io/koji/pull-request/2322


Users with the ``admin`` permission can now manage sidetags even if they are
not their own.

**Fix is_sidetag_owner and is_sidetag policy tests**

| PR: https://pagure.io/koji/pull-request/2326

These policy tests would previously always return a null result.
Now they return the correct one.


Utilities Changes
-----------------

Garbage Collector
.................

**Systemd units for koji-gc**

| PR: https://pagure.io/koji/pull-request/2199

The systemd units(service and timer) are now installed by default.

**Allow specifying CC and BCC address for email notifications**

| PR: https://pagure.io/koji/pull-request/2195
| PR: https://pagure.io/koji/pull-request/2278

New options ``cc_addr``, ``bcc_addr`` in config file, or CLI options
``--cc-addr``, ``--bcc-addr`` are available now.

**Set smtp_host to localhost by default**

| PR: https://pagure.io/koji/pull-request/2253

The previous the default value was ``None``, which would cause failures
if notifications were enabled.

Kojira
......

**New option: queue_file for task queue monitoring**

| PR: https://pagure.io/koji/pull-request/2024

With a writable filepath specified, the state information will be saved into
this file in each cycle. For more information, please refer to
:ref:`utils-kojira`.

**Use mtime of repo directory to determine the age**

| PR: https://pagure.io/koji/pull-request/2154

Kojira should now do a better job of determining the age of a repo at startup.

**Fix logic detecting directories for pruneLocalRepos**

| PR: https://pagure.io/koji/pull-request/2323

The condition was opposite before.

**Totally drop SysV support**

| PR: https://pagure.io/koji/issue/2171

Thus, we won't provide kojira service on <=EL6 platform.

**Repo deletion within thread**

| PR: https://pagure.io/koji/pull-request/2340
| PR: https://pagure.io/koji/pull-request/2397

Kojira are now able to delete repos in a separated thread.
The old ``delete_batch_size`` option is no longer used and has been removed.

koji-sidetag-cleanup
....................

**Set the shebang to /usr/bin/python2 on RHEL<=7**

| PR: https://pagure.io/koji/pull-request/2209

Otherwise, the build will fail on RHEL<=7.

koji-sweep-db
.............

**use "Type=oneshot" for systemd**

| PR: https://pagure.io/koji/pull-request/2187

``oneshot`` is the appropriate choice for periodic cleanup scripts, see `systemd
docs
<https://www.freedesktop.org/software/systemd/man/systemd.service.html#Type=>`_.
