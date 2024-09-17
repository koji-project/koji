
Koji 1.35.0 Release notes
=========================

All changes can be found in `the roadmap <https://pagure.io/koji/roadmap/1.35/>`_.
Most important changes are listed here.

Major change is this release is kojira rewrite and repos on-demand.

Migrating from Koji 1.34/1.34.1
-------------------------------

For details on migrating see :doc:`../migrations/migrating_to_1.35`


Security Fixes
--------------

None


Client Changes
--------------

**Don't try to resolve server version for old hubs**

| PR: https://pagure.io/koji/pull-request/3891

Some CLI commands have extended capabilities with newer hub versions. But if
they were run against really old version (one that doesn't report its version),
they've failed completely. Now the correctly use older API signatures.

**New CLI command list-users**

| PR: https://pagure.io/koji/pull-request/3970
| PR: https://pagure.io/koji/pull-request/4008
| PR: https://pagure.io/koji/pull-request/4051

As we're more using user groups in policies, ``list-users`` with
``--perm=<permission>`` and ``--inherited-perm`` options now could help with
finding and debugging such users.

``--type`` option would limit NORMAL/HOST/GROUP user types.

**Fix remove-tag-inheritance with priority**

| PR: https://pagure.io/koji/pull-request/4000

Better handling of ``remove-tag-inheritance <tag> <parent> <priority>`` command
variant.

**Taskinfo CLI and webUI info message why output is not in the list**

| PR: https://pagure.io/koji/pull-request/4075

Informational messages for missing logs and task outputs.

API Changes
-----------

**Anonymous getGroupMembers and getUserGroups**

| PR: https://pagure.io/koji/pull-request/3912

First call was previously requiring ``admin`` permission. As the same
information is available through other paths this requirement was dropped. Alse
new ``getUserGroups`` API call was added.

**Better default handling for getMultiArchInfo**

| PR: https://pagure.io/koji/pull-request/4164

Simple API default update.

 **Allow None in repoInfo for backwards compat**

| PR: https://pagure.io/koji/pull-request/4192

Web UI had in some cases problems to corectly display taskinfo page
because of the older regression.

System Changes
--------------

**Keep schema upgrade transactional**

| PR: https://pagure.io/koji/pull-request/4141

Simple fix to migration scripts. Indices are now created as part of the
transaction as it doesn't take much time even in big deployments.

**Backup signature headers in delete_rpm_sig**

| PR: https://pagure.io/koji/pull-request/3944

Signatures can be deleted by admin-only call. It is anyway a good practice to
store even deleted signatures, so we can audit such situations. They are now
stored in build directory.

**Stop lowercasing the policy failure reason**

| PR: https://pagure.io/koji/pull-request/3953

Simple update to not convert messages in policies.

**Let ``tag.extra`` override tag arches for noarch**

| PR: https://pagure.io/koji/pull-request/4013

In some cases noarch packages can't be built on some architectures. As there is
no first-class support for such routing, tag can be modified via
``extra.noarch_arches`` key.

**Better index for rpm lookup**

| PR: https://pagure.io/koji/pull-request/4026

Improved index after addition of draft builds.

**Auto arch refusal for noarch tasks**

| PR: https://pagure.io/koji/pull-request/4060

Scheduler improvement for noarch tasks which could have been assigned to
builders without access to relevant buildroot architecture repos. It would
speedup correct assigning of noarch tasks in some cases.

**Fix errors in channel policy**

| PR: https://pagure.io/koji/pull-request/4066

Channel policy can refer to non-existent tags, etc. Policy would have failed
even in case where there would be other valid rule.

**Sort checksums before inserting**

| PR: https://pagure.io/koji/pull-request/4073

``create_rpm_checksums`` could have triggered deadlock. This change would
prevent it.

**Handle volumes when clearing stray build dirs**

| PR: https://pagure.io/koji/pull-request/4092

``recycle_build`` ignored some files and left them on non-default volumes
instead of deleting. Newly created build then already contained some files and
failed while trying to recreate them.

**Drop unused DBHandler class**

| PR: https://pagure.io/koji/pull-request/4095

Logging class which is not used anywhere.

**Stop suggesting that users need repo permission**

| PR: https://pagure.io/koji/pull-request/4097

``regen-repo`` is the correct permission which should be granted to users.
``repo`` is a privileged one and is mostly intended for kojira.

**CG import updates**

| PR: https://pagure.io/koji/pull-request/4113

Content generator API now allows uploading subdirectories instead of just flat
structure. ``CG_import`` policy gets also ``version``, ``release`` and
``btypes`` fields for additional checks.

**Fix tz mismatch issues with various queries**

| PR: https://pagure.io/koji/pull-request/4115

Further unification of timestamp/timezone usage.

**RetryError is subclass of AuthError**

| PR: https://pagure.io/koji/pull-request/4117

Small fix for unreachable code.

**Provide tag data in policy_data_from_task_args**

| PR: https://pagure.io/koji/pull-request/4121

More data available for policy tests.


Builder Changes
---------------

**Use dnf5-compatible "group install" command**

| PR: https://pagure.io/koji/pull-request/3974

Dnf5 dropped support for ``group install`` command so, we've made a dnf4/5
compatible changes.

**Split out buildroot log watching logic**

| PR: https://pagure.io/koji/pull-request/4023

Rewritten code for handling mock's logs. It now allows to fetch more logs than
before.

**Update getNextTask for scheduler**

| PR: https://pagure.io/koji/pull-request/4044

Followup work after introducing new scheduler. Mostly builder code
simplification.

**Log if a restart is pending**

| PR: https://pagure.io/koji/pull-request/4076

Builder is more verbose about this situation.

**Refuse image tasks when required deps are missing**

| PR: https://pagure.io/koji/pull-request/4083

If image-supporting libraries are not present on builder it will decline the
image tasks without trying them, so they'll not fail.

**Don't ignore files in uploadFile**

| PR: https://pagure.io/koji/pull-request/4093

Empty files were ignored before. Now we upload also these.

Kojira
------

**Kojira on demand**

| PR: https://pagure.io/koji/pull-request/4033
| PR: https://pagure.io/koji/pull-request/4127

Massive overwrite of repo regeneration. Previously, kojira was in charge of
regenerating everything what is out of date. It could have been thousands of
repos which will be never used. We've moved to on-demand behaviour drastically
limiting number of ``newRepo`` tasks.

Full description of behaviour change is at :doc:`../repo_generation`.

Web UI
------

**Show only active channels at clusterhealth**

| PR: https://pagure.io/koji/pull-request/4011

Simplification of web ui.

**Drop part of code related to host without update_ts**

| PR: https://pagure.io/koji/pull-request/4086


Plugins
-------

SCMPolicy
.........
| PR: https://pagure.io/koji/pull-request/3969

New policy plugin which can decide if build can proceed with data based on SCM
checkout results. Typical usecase would be checking that commit beeing built is
present on some explicit branch.

Kiwi
....
**Generate full logs with debug information**

| PR: https://pagure.io/koji/pull-request/4046

Uploading additional logs for easier kiwi debugging.

**Only add buildroot repo if user repositories are not defined**

| PR: https://pagure.io/koji/pull-request/4063

We've changed default behaviour that kiwi has access to buildroot repo. Now it
must be explicitly specified via ``--buildroot-repo`` option.


**Add support for overriding image type attributes**

| PR: https://pagure.io/koji/pull-request/4156
| PR: https://pagure.io/koji/pull-request/4181

CLI option ``--set-type-attr`` for kiwi. For possible values look at `kiwi docs
<https://osinside.github.io/kiwi/commands/system_build.html>`_.

**Add support for overriding kiwi image file name format**

| PR: https://pagure.io/koji/pull-request/4157

CLI option ``--bundle-format`` for kiwi. For possible values look at `kiwi docs`_.


**Add support for overriding version and releasever**

| PR: https://pagure.io/koji/pull-request/4184

``--version`` and ``--repo-releasever`` CLI options for overriding these in the
resulting image.

Devtools and tests
------------------

**Updates for various tests**

| PR: https://pagure.io/koji/pull-request/4068
| PR: https://pagure.io/koji/pull-request/4082
| PR: https://pagure.io/koji/pull-request/4087
| PR: https://pagure.io/koji/pull-request/4110
| PR: https://pagure.io/koji/pull-request/4111
| PR: https://pagure.io/koji/pull-request/4118
| PR: https://pagure.io/koji/pull-request/4132
| PR: https://pagure.io/koji/pull-request/4133
| PR: https://pagure.io/koji/pull-request/4158
| PR: https://pagure.io/koji/pull-request/4186

**setup.py: Fix version retrieval on Python 3.13+**

| PR: https://pagure.io/koji/pull-request/4100

**make clean - more files**

| PR: https://pagure.io/koji/pull-request/4103


Documentation
-------------

**Mock's configuration**

| PR: https://pagure.io/koji/pull-request/4025

**Add external koji dev environments' links**

| PR: https://pagure.io/koji/pull-request/4104

**Drop unused auth options**

| PR: https://pagure.io/koji/pull-request/4107

Dropping some older options from example configuration files and documentation.
