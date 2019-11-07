Koji 1.19.0 Release notes
=========================


Migrating from Koji 1.18
------------------------

For details on migrating see :doc:`../migrations/migrating_to_1.19`



Security Fixes
--------------

**GSSAPI authentication checks kerberos principal**

| PR: https://pagure.io/koji/pull-request/1419

When using GSSAPI authentication the user's kerberos principal will be checked
for their username to avoid a potential username and kerberos principal mismatch.



Client Changes
--------------

**Add user edit**

| PR: https://pagure.io/koji/pull-request/902
| PR: https://pagure.io/koji/pull-request/1701
| PR: https://pagure.io/koji/pull-request/1713

A new ``edit-user`` command and API call was added, allowing for user rename,
and changing, adding, or removing the kerberos principal of a user.


**Add remove group**

| PR: https://pagure.io/koji/pull-request/923

A new ``remove-group`` command was added, allowing the removal of a group
from a tag. It uses the existing ``groupListRemove`` API call.


**Query builds per chunks in prune-signed-builds**

| PR: https://pagure.io/koji/pull-request/1589

For bigger installations querying all builds can cause the hub to run out of memory.
``prune-signed-builds`` now queries these in 50k chunks.


**Show inheritance flags in list-tag-inheritance output**

| PR: https://pagure.io/koji/pull-request/1120

While not often used, tag inheritance can be modified with a few different options (e.g. maxdepth).
These options are shown in the ``taginfo`` display, but not the ``list-tag-inheritance`` display.
This change adds basic indicators to the latter.


**Return usage information in make-task**

| PR: https://pagure.io/koji/pull-request/1157

``make-task`` now returns usage information if no arguments are provided.


**Clarify clone-tag usage**

| PR: https://pagure.io/koji/pull-request/1623

The ``clone-tag`` help text now clarifies that the destination tag will be created
if it does not already exist.


**Add option check for list-signed**

| PR: https://pagure.io/koji/pull-request/1631

The ``list-signed`` command will now fail if no options are provided.



Library Changes
---------------

**Consolidate config reading style**

| PR: https://pagure.io/koji/pull-request/1296

Changes have been made to make configuration handling more consistent.

With this new implementation:

* ``read_config_files`` is extended with a strict option and directory support
* ``ConfigParser`` is used for all invokings except kojixmlrpc and ``kojid``
* ``RawConfigParser`` is used for ``kojid``


**list_archive_files handles multi-type builds**

| PR: https://pagure.io/koji/pull-request/1508

If ``list_archive_files`` is provided a build with multiple archive types it now correctly
handles them instead of failing.


**Disallow archive imports that don't match build type**

| PR: https://pagure.io/koji/pull-request/1627
| PR: https://pagure.io/koji/pull-request/1633

The ``importArchive`` call now refuses to proceed if the build does not have the given type.


**Add listCG RPC**

| PR: https://pagure.io/koji/pull-request/1160

``listCGs`` has been added to list new content generator records.

The purpose of this change is to make it easier for administrators to determine what
content generators are present and what user accounts have access to those.


**Add method to cancel CG reservations**

| PR: https://pagure.io/koji/pull-request/1662

The new ``CGRefundBuild`` call allows CGs to cancel build reservations, such as in the case
of a failing build.


**Allow ClientSession objects to get cleaned up by the garbage collector**

| PR: https://pagure.io/koji/pull-request/1653

This change ensures ``koji.ClientSession`` objects are destroyed once their requests are complete.


**Add missing package list check**

| PR: https://pagure.io/koji/pull-request/1244
| PR: https://pagure.io/koji/pull-request/1702

The ``host.tagBuild`` method was missing a check to ensure the package was actually listed in the
destination tag. This should now be checked as expected.


**Increase buildReferences SQL performance**

| PR: https://pagure.io/koji/pull-request/1675

The performance for ``build_references`` has been improved.


**ensuredir does not duplicate directories**

| PR: https://pagure.io/koji/pull-request/1197

``koji.ensuredir`` no longer creates duplicate directories if provided a path ending in a
forward slash.


**Warn users if buildroot uses yum instead of dnf**

| PR: https://pagure.io/koji/pull-request/1595

This change sets the mock config ``dnf_warning`` to True for buildroots using yum.


**Tag permission can be used for tagBuildBypass and untagBuildBypass**

| PR: https://pagure.io/koji/pull-request/1685

The ``tag`` permission can now be used in place of admin to call ``tagBuildBypass``
and ``untagBuildBypass``. Admin is still required to use the ``--force`` option.


**Rework update of reserved builds**

| PR: https://pagure.io/koji/pull-request/1621

This change reworks and simplifies the code that updates reserved build entries for cg imports.
It removes redundancy with checks in ``prep_build`` and avoids duplicate ``*BuildStateChange``
callbacks.


**Use correct top limit for randint**

| PR: https://pagure.io/koji/pull-request/1612

The top limit for ``randint`` has been set to 255 from 256 to prevent ``generate_token`` from
creating unneccesarily long tokens.


**Add strict option to getRPMFile**

| PR: https://pagure.io/koji/pull-request/1068

``getRPMFile`` now has a ``strict`` option, failing when the RPM or filename does not exist.


**Stricter groupListRemove**

| PR: https://pagure.io/koji/pull-request/1173
| PR: https://pagure.io/koji/pull-request/1678

``groupListRemove`` now returns an error if the provided group does not exist for the tag.


**Clarified docs for build.extra.source**

| PR: https://pagure.io/koji/pull-request/1677

The usage for ``build.extra.source`` has now been clarified in the ``getBuild`` call.


**Use bytes for debug string**

| PR: https://pagure.io/koji/pull-request/1657

This change fixes debug output for Python 3.


**Removed host.repoAddRPM call**

| PR: https://pagure.io/koji/pull-request/1680

The ``host.repoAddRPM`` call has been removed because it was unused and broken.



Web UI Changes
--------------

**Made difference between Builds and Tags sections more clear**

| PR: https://pagure.io/koji/pull-request/1676

The search page results for packages now has a clearer delineation between builds and tags.



Builder Changes
---------------

**Use preferred arch when builder provides multiple**

| PR: https://pagure.io/koji/pull-request/1684

When using ExclusiveArch for noarch builds the build task will now use the
arch specified instead of randomly picking from the arches the builder provides.

This change adds a ``preferred_arch`` parameter to ``find_arch``.


**Log insufficient disk space location**

| PR: https://pagure.io/koji/pull-request/1523

When ``kojid`` fails due to insufficient disk space, the directory which needs more
disk space is now included as part of the log message.


**Allow builder to attempt krb if gssapi is available**

| PR: https://pagure.io/koji/pull-request/1613

``kojid`` will now use ``requests_kebreros`` for kerberos authentication when available.


**Add support for new mock exit codes**

| PR: https://pagure.io/koji/pull-request/1682

``kojid`` now expects mock exit code 10 for failed builds (previously 1).


**Fix kickstart uploads for Python 3**

| PR: https://pagure.io/koji/pull-request/1618

This change fixes the file handling of kickstarts for Python 3.



System Changes
--------------

**Package ownership changes do not trigger repo regens**

| PR: https://pagure.io/koji/pull-request/1473
| PR: https://pagure.io/koji/pull-request/1643

Changing tag or package owners no longer cause repo regeneration. A new
``tag_package_owners`` table has been added for this purpose.


**Support multiple realms by kerberos auth**

| PR: https://pagure.io/koji/pull-request/1648
| PR: https://pagure.io/koji/pull-request/1696
| PR: https://pagure.io/koji/pull-request/1701

This change adds a new table ``user_krb_principals`` which tracks a list of ``krb_principals``
for each user instead of the previous one-to-one mapping. In addition:

* all APIs related to user or krb principals are changed
* ``userinfo`` of ``getUser`` will contain a new list ``krb_principals``
    * ``krb_principals`` will contain all available principals if ``krb_princs=True``
* there is a new hub option ``AllowedKrbRealms`` to indicate which realms are allowed
* there is a new client option ``krb_server_realm`` to allow krbV login to set server realm
    * Previously same as client principal realm before, supported by all clients
* ``QueryProcessor`` has a new queryOpt ``group``, which is used to generate ``GROUP BY`` section
    * By default, this feature is disabled by arg ``enable_group=False``


**Added cronjob for sessions table maintenance**

| PR: https://pagure.io/koji/pull-request/1492

The sessions table is now periodically cleaned up via script (handled by cron by default).
Without this the sessions table can grow large enough to affect Koji performance.


**Added basic email template for koji-gc**

| PR: https://pagure.io/koji/pull-request/1430

The email message koji-gc uses has been moved to ``/etc/koji-gc/email.tpl`` for
easier customization.


**Add all permissions to database**

| PR: https://pagure.io/koji/pull-request/1681

Permissions previously missing from schema have been added, including ``dist-repo``, ``host``,
``image-import``, ``sign``, ``tag``, and ``target``.


**Add new CoreOS artifact types**

| PR: https://pagure.io/koji/pull-request/1616

This change adds the new CoreOS artifact types ``iso-compressed``, ``vhd-compressed``,
``vhdx-compressed``, and ``vmdk-compressed`` to the database.


**Enforce unique content generator names in database**

| PR: https://pagure.io/koji/pull-request/1159

Set a uniqueness constraint on the content generator name in the database.
Prior to this change, we were only enforcing this in the hub application layer.
Configure this in postgres for safety.


**Fix typo preventing VM builds**

| PR: https://pagure.io/koji/pull-request/1666

This change fixes the options passed to ``verifyChecksum`` which was preventing VM builds.


**Fix verifyChecksum for non-output files**

| PR: https://pagure.io/koji/pull-request/1670

``verifyChecksum`` now accepts files under the build requires path as well as the output path.
Other paths can be added as needed.


**Set f30+ python-devel default**

| PR: https://pagure.io/koji/pull-request/1683

When installed on a Fedora 30+ host with Python 2 support, Koji will now require
``python2-devel`` instead of ``python-devel``.


**Handle sys.exc_clear for Python 3**

| PR: https://pagure.io/koji/pull-request/1642

The method ``sys.exc_clear`` does not exist in Python 3, so it has been escaped for those instances.


**Remove deprecated koji.util.relpath**

| PR: https://pagure.io/koji/pull-request/1458

``koji.util.relpath`` was deprecated in 1.16 and has been removed from 1.19.


**Remove deprecated BuildRoot.uploadDir**

| PR: https://pagure.io/koji/pull-request/1511

``BuildRoot.uploadDir`` was deprecated in 1.18 and has been removed from 1.19.


**Remove deprecated koji_cli.lib_unique_path**

| PR: https://pagure.io/koji/pull-request/1512

``koji_cli.lib_unique_path`` was deprecated in 1.17 and has been removed from 1.19.


**Deprecation of sha1_constructor and md5_constructor**

| PR: https://pagure.io/koji/pull-request/1490

``sha1_constructor`` and ``md5_constructor`` have been deprecated in favor of ``hashlib``.
