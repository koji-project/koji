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
`None`


Client Changes
--------------

**Output extra['rpm.macro.*'] to mock-config**

| PR: https://pagure.io/koji/pull-request/2255

``mock-config`` command honors 'rpm.macro.*' options in tag's extra config now.

**Unify error messages in CLI**

| PR: https://pagure.io/koji/pull-request/2044

This is a technical dept enhancement. Now we are calling ``error()`` instead of
``print()`` and ``return 1``.

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

**Hide local --debug options for some commands**

| PR: https://pagure.io/koji/pull-request/2085

Following commands use the global ``--debug`` option for their own debug purpose
now:

* ``prune-sigs``
* ``list-signed``
* ``list-tag-history``
* ``list-history``

The local ``--debug`` options are still usable as we just hide them in helps.

**New option --wait for download-task**

| PR: https://pagure.io/koji/pull-request/2346

This is a UE enhancement to let the command be able to wait for the tasks to be
finished as the same as the behavior of ``build`` command.

**Fix image-build-indirection --wait**

| PR: https://pagure.io/koji/pull-request/2347

Although there's a ``--wait`` option for ``image-build-indirection``, it was not
working until it's fixed by this PR.

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

**query_buildroots have to return ASAP**

| PR: https://pagure.io/koji/pull-request/2299
| PR: https://pagure.io/koji/pull-request/2303
| PR: https://pagure.io/koji/pull-request/2301

For the optimization purpose, ``query_buildroots()`` can return earlier if there
is no candidate buildroot. This function equals ``listBuildroots`` API and is
used by ``getBuildroot``.

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
result list on server side. ``list-tags`` command tries its best to call it with
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

This change impacts ``BuildMavenTask``, ``WrapperRPMTask``, ``ImageTask`` and
``BuildSRPMfromRPMTask``. Any plugins that use this should be aware that using
this could make them more fragile across releases. This feature does not come
with a promise avoid changing the behavior of the ``BuildRoot`` class.


Web UI Changes
--------------

**A new repoinfo page**

| PR: https://pagure.io/koji/pull-request/2193

The new page displays basic information of a normal repo, linked by the repo id
on taskinfo and buildrootinfo page.

**Fix simple_error_message encoding for PY3**

| PR: https://pagure.io/koji/pull-request/2342

The rendering of error page won't work properly without this fix.


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

Finally, python2 support for hub and web have been dropped in this release.

**Log tracebacks for multicall**

| PR: https://pagure.io/koji/pull-request/2225

The exceptions inside multicall were not logged before. These tracebacks will
benefit us for debugging purpose, as we are often using multicall more and more.

**Fix build_notification crashing caused by recipients check**

| PR: https://pagure.io/koji/pull-request/2308
| PR: https://pagure.io/koji/pull-request/2309

`PR#1417 <https://pagure.io/koji/pull-request/1417>`_ uses ``len()`` to check
the result of ``get_notification_recipients()``, but it could be ``None`` then
will cause a ``TypeError``. Now we fix this issue by both fixing the condition
in ``build_notification()`` and returning ``[]`` in
``get_notification_recipients()``.

**Allow packagelist changes with 'tag' permission by the default policy**

| PR: https://pagure.io/koji/pull-request/2275

'tag' permission has been introduced for tag config management. It makes much
sense to let the users with `tag` permission be able to change packagelist as
well.

**Improve race condition for getNextRelease call and images**

| PR: https://pagure.io/koji/pull-request/2263

It was possible to meet the race condition in the old logic of image building.
We are now calling ``get_next_release()`` in ``initImageBuild`` call if there is
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

This option has been ``Off`` be default, see `mod_auth_gssapi doc
<https://github.com/gssapi/mod_auth_gssapi#gssapisslonly>`_

**Remove "GssapiLocalName Off" option**

| PR: https://pagure.io/koji/pull-request/2351
| PR: https://pagure.io/koji/pull-request/2358

_ditto_, and it is both for hub and web

**hub: Fix typo in ensure_volume_symlink**

| PR: https://pagure.io/koji/pull-request/2354

**Provide task-based data to volume policy**

| PR: https://pagure.io/koji/pull-request/2306

For builds with associated tasks, more information is now available to the volume policy.
In particular, the ``buildtag`` policy test should work for such builds.

Note that some builds (e.g. content generator builds and other imported builds) do not
have associated tasks.

For more information on hub policies, see :doc:`defining_hub_policies`.

**Archive's checksum_type should be always integer in DB**

| PR: https://pagure.io/koji/pull-request/2369

We fixed the problem in ``CG_Importer.match_file()`` and
``import_archive_internal()``.

**host.importImage doesn't honor volume**

| PR: https://pagure.io/koji/pull-request/2359

``host.importImage`` now directly uses the data of ``build_info`` rather than
fetching it from DB again. So, it won't miss the volume information anymore.
Notice that the signature has been changed: the argument ``build_id`` is changed to
``build_info``.


Plugins
-------

sidetag
.......

**listSideTags also returns user info**

| PR: https://pagure.io/koji/pull-request/2132

We now provide an easier way to find the owner of sidetags

**Give koji admins the permission to operate sidetags**

| PR: https://pagure.io/koji/pull-request/2322
| PR: https://pagure.io/koji/pull-request/2326

The admins should be able to manage sidetags even if they are not their own. This also
fix a bug that ``is_sidetag_owner``, ``is_sidetag`` used in policy check and many
other places do not return result.


Utilities Changes
-----------------

Garbage Collector
.................

**Support of GSSAPI auth requests-kerberos**

| PR: https://pagure.io/koji/pull-request/2151

Meanwhile, the ``krb_login`` auth with ``krbV`` has been dropped.

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

The previous default value of ``smtp_host`` is ``None``. It will It will cause
``smtplib.SMTP().connect()`` to fail. Setting the default vault to 'localhost'
fixes this issue accordingly.

Kojira
......

**New option: queue_file for task queue monitoring**

| PR: https://pagure.io/koji/pull-request/2024

With a writable filepath specified, the state information will be saved into
this file in each cycle. For more information, please refer to
:ref:`utils-kojira`.

**Use mtime of repo directory to determine the age**

| PR: https://pagure.io/koji/pull-request/2154

``first_seen`` is measured from start of the kojira process. It doesn't make
much sense for short-lived kojira to determine the age of repo. Trying the best
to replace it with mtime of repo directory would be a more accurate approach.

**Fix logic detecting directories for pruneLocalRepos**

| PR: https://pagure.io/koji/pull-request/2323

The condition was opposite before.

**Replace deprecated Thread.isAlive() by Thread.is_alive()**

| PR: https://pagure.io/koji/pull-request/2316

``is_alive()`` call exists since python 2.7.

**More debug info for un/tracked tasks**

| PR: https://pagure.io/koji/pull-request/2137

**Totally drop SysV support**

| PR: https://pagure.io/koji/issue/2171

Thus, we won't provide kojira service on <=EL6 platform.

**Repo deletion within thread**

| PR: https://pagure.io/koji/pull-request/2340

Kojira are now able to delete repos in a separated thread. ``delete_batch_size``
is useless now.

koji-sidetag-cleanup
....................

**Set the shebang to /usr/bin/python2 on RHEL<=7**

| PR: https://pagure.io/koji/pull-request/2209

Otherwise, the build will fail on RHEL<=7.

**Fix useless of the option --no-empty**

| PR: https://pagure.io/koji/pull-request/2330

There was a typo that checking ``clean_old`` instead of ``clean_empty`` in
``clean_empty()``.

**Fix the dict comparison of dicts**

| PR: https://pagure.io/koji/pull-request/2327

Direct comparison between dicts isn't supported by python3. We've changed the
logic for python3 compatibility.

koji-sweep-db
.............

**use "Type=oneshot" for systemd**

| PR: https://pagure.io/koji/pull-request/2187

``oneshot`` is the appropriate choice for periodic cleanup scripts, see `systemd
docs
<https://www.freedesktop.org/software/systemd/man/systemd.service.html#Type=>`_.


Documentation Changes
---------------------

Documentation
.............

**"koji build" requires a target rather than a tag**

| PR: https://pagure.io/koji/pull-request/2177

**kojira: remove duplicate Kerberos configuration boilerplate**

| PR: https://pagure.io/koji/pull-request/2175

**Server How To: Documentation improvement**

| PR: https://pagure.io/koji/pull-request/2206
| PR: https://pagure.io/koji/pull-request/2205
| PR: https://pagure.io/koji/pull-request/2235
| PR: https://pagure.io/koji/pull-request/2287
| PR: https://pagure.io/koji/pull-request/2161
| PR: https://pagure.io/koji/pull-request/2350

**Document merge modes**

| PR: https://pagure.io/koji/pull-request/2276

**Align "Hub" text in diagram**

| PR: https://pagure.io/koji/pull-request/2329

**Document plugin callbacks**

| PR: https://pagure.io/koji/pull-request/2345

**Document runroot plugin**

| PR: https://pagure.io/koji/pull-request/2344

**Update test suite dependency list for py3**

| PR: https://pagure.io/koji/pull-request/2352

**Exporting repositories**

| PR: https://pagure.io/koji/pull-request/2385

**Sphinx formatting fixes for hub policy doc**

| PR: https://pagure.io/koji/pull-request/2363

API Doc
.......

**getTagExternalRepos**

| PR: https://pagure.io/koji/pull-request/2173

**editUser**

| PR: https://pagure.io/koji/pull-request/2176

**createUser**

| PR: https://pagure.io/koji/pull-request/2172

**setInheritanceData**

| PR: https://pagure.io/koji/pull-request/2213

Correct docstring about deleting inheritance rules.

**listChannels**

| PR: https://pagure.io/koji/pull-request/2331

**listBType**

| PR: https://pagure.io/koji/pull-request/2377

CLI Doc
.......

**Fix "list-history --help" text for "--cg"**

| PR: https://pagure.io/koji/pull-request/2180

**Improve grant-permission --new --help message**

| PR: https://pagure.io/koji/pull-request/2207


Miscellaneous Changes
---------------------

**Packaging: Use %autosetup to manage patches**

| PR: https://pagure.io/koji/pull-request/2197

**DB: Use timestamps with timezone**

| PR: https://pagure.io/koji/pull-request/2237
| PR: https://pagure.io/koji/pull-request/2366

**DB: Change sessions_active_and_recent index to get it used by planner**

| PR: https://pagure.io/koji/pull-request/2334
