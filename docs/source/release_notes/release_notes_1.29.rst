
Koji 1.29.0 Release notes
=========================

All changes can be found in `the roadmap <https://pagure.io/koji/roadmap/1.29/>`_.
Most important changes are listed here.


Migrating from Koji 1.28/1.28.1
-------------------------------

For details on migrating see :doc:`../migrations/migrating_to_1.29`


Security Fixes
--------------

None


Client Changes
--------------
**Retry gssapi_login if it makes sense**

| PR: https://pagure.io/koji/pull-request/3248

Only place in CLI where we did not retried when server was inaccessible was
rewriteen to retry in some cases when there is an expecetation that it could
work.

**Fix more users in userinfo**

| PR: https://pagure.io/koji/pull-request/3325

Userinfo regressions - it now correctly list information for all users specified
on command line.

**Allow untag-build for blocked packages**

| PR: https://pagure.io/koji/pull-request/3255

When package is blocked in the tag but there was already some build for that
package, CLI refused to untag it. It is now fixed.

API Changes
-----------
**Remove taskReport API call**

| PR: https://pagure.io/koji/pull-request/3237

**Add strict option to getRPMHeaders**

| PR: https://pagure.io/koji/pull-request/3256

Similarly to other stricts it will raise an error if rpm doesn't exist. Empty
dictionary was returned instead which was indistunguishable with missing
requested key in existing RPM. This behaviour is still available with
``strict=False``.

**Add extra of builds to listTagged call result**

| PR: https://pagure.io/koji/pull-request/3282

Pattern of ``listTagged`` followed by multicall of ``getBuild`` is used often,
so we decided to put missing info (``extra`` field) directly into ``listTagged``
so only one call is required now.

**Add as_string option to showOpts for raw string or dict output**

| PR: https://pagure.io/koji/pull-request/3313
| PR: https://pagure.io/koji/pull-request/3349

Usable for koji administration - additional format for getting current
configuration in machine-readable format. ``as_string=True`` reflects old
behaviour.

Builder Changes
---------------
**Check ccache size before trying to use it**

| PR: https://pagure.io/koji/pull-request/3234

Machine restart could cause failing authentication for the builder as ccache
file is not properly deleted.

**call git rev-parse before chowning source directory**

| PR: https://pagure.io/koji/pull-request/3355

Newer git (2.35.2) fixed long-standing git security issue but we needed to adapt
our code as a result.

System Changes
--------------
**Remove koji.listFaults**

| PR: https://pagure.io/koji/pull-request/3238

This method was not used anywhere in koji code and could complicate future
exception redesign, so we've removed it.

**Add log file for match_rpm warnings in cg_import**

| PR: https://pagure.io/koji/pull-request/3257

CG import was writing errors to hub logs when rpm were not found in koji. As it
could be a problem in some workflows, we've added more visibility by uploading
separate log to the imported build which lists these errors.

**Return 400 codes when client fails to send a full request**

| PR: https://pagure.io/koji/pull-request/3269

Changing to errcode instead of exception will allow client to retry it. So,
another type of network problems can be handled more transparently.

**Weak dep on httpd.service for kojid/ra - koji**

| PR: https://pagure.io/koji/pull-request/3277

In case more services are running on same node (e.g. hub + kojira) this change
will trigger ``kojid``/``kojira`` after hub is running resulting in no initial
errors due to inaccessible hub.

**Log content-length when we get an error reading request**

| PR: https://pagure.io/koji/pull-request/3289

Additional logging information for unstable networks.

**Hub, plugins and tools inputs validation**

| PR: https://pagure.io/koji/pull-request/3318

Internal changes improving security via better input handling.

**Add admin check when priority has negative value in wrapperRPM**

| PR: https://pagure.io/koji/pull-request/3321
| PR: https://pagure.io/koji/pull-request/3347

It was a bug present in the code, where ``wrapperRPM`` s could have been set to
negative priority even by their owners. Negative priorities are reserved just
for admins.

**Permit forcing releasever/arch within mock per tag**

| PR: https://pagure.io/koji/pull-request/3358

Mock's ``forcearch`` and ``relver`` options are now accesible via tag extras.

Web
---
**Add free task for admin**

| PR: https://pagure.io/koji/pull-request/3272

In addition to cancelling task, admin now has also "free" button available.

**Add blocked option to packages page**

| PR: https://pagure.io/koji/pull-request/3334
| PR: https://pagure.io/koji/pull-request/3329

New filter to see blocked packages in webui.

**Display load/capacity at hosts page**

| PR: https://pagure.io/koji/pull-request/3346

It is sometimes useful to see these values there.

Plugins
-------
**Adding Driver Update Disk building support**

| PR: https://pagure.io/koji/pull-request/3217

Previously Driver Update Disks were done by custom scripts or by `ddiskit
<https://github.com/orosp/ddiskit/blob/master/bin/ddiskit>`_. Now it can be done
in koji, so it benefits from auditability, etc.

**koji-sidetag-cleanup: delete inactive tags**

| PR: https://pagure.io/koji/pull-request/3294

New cleanup option allow to delete sidetags which are no longer active (no new
builds are tagged there).

**Add tag2distrepo plugin to hub**

| PR: https://pagure.io/koji/pull-request/3326

Plugin will trigger ``distrepo`` tasks for configured tags when a new build
arrives.

**Fix age to max_age in protonmsg**

| PR: https://pagure.io/koji/pull-request/3344

Incoherent naming in documentation and code is now unified.


Documentation
-------------
**Clarify rpm imports**

| PR: https://pagure.io/koji/pull-request/3301

**Better description for kiwi channel requirements**

| PR: https://pagure.io/koji/pull-request/3331

**Winbuild documentation updates**

| PR: https://pagure.io/koji/pull-request/3333

**Document "list-signed" requires filesystem access**

| PR: https://pagure.io/koji/pull-request/3342
