
Koji 1.31.0 Release notes
=========================

All changes can be found in `the roadmap <https://pagure.io/koji/roadmap/1.31/>`_.
Most important changes are listed here.


Migrating from Koji 1.30/1.30.1
-------------------------------

For details on migrating see :doc:`../migrations/migrating_to_1.31`


Security Fixes
--------------

None


Client Changes
--------------
**download-task more specific info for non-CLOSED tasks**

| PR: https://pagure.io/koji/pull-request/3488

A bit more info about state of the task.

**Add count and size for download-build**

| PR: https://pagure.io/koji/pull-request/3516

Unification of output how many files are being downloaded.

**list-hosts fix when list of channels is empty**

| PR: https://pagure.io/koji/pull-request/3533

Command was failing when builder was not assigned to any channel.

**edit-channel set default return value and print error msg to stderr**

| PR: https://pagure.io/koji/pull-request/3535

Unification of return values and error-handling.

**Fix nvr sorting in list-builds**

| PR: https://pagure.io/koji/pull-request/3542

Confusing default ``--sort-key=nvr`` was replaced by ``--sort-key=build_id``.
NVR sorting was/is in reality alphabetic sort, not NVR sort. We're not planning
to introduce NVR comparison anywhere, so we've changed the default here.

**Add regex --filter and --skip option for download-task**

| PR: https://pagure.io/koji/pull-request/3552

``download-task`` command can download many files and default filters like
``--arch`` can be insufficient and lead to downloading much more content than
needed. Two new regexp filters are introduced to further limit bandwith.

API Changes
-----------
**Allow buildTagID and destTagID as string and dict in getBuildTargets**

| PR: https://pagure.io/koji/pull-request/3550

A bit more comfort in specifying these values.

Builder Changes
---------------
**Remove login shell from kojibuilder user**

| PR: https://pagure.io/koji/pull-request/3476

Login shell is not needed for normal ``kojid`` usage. It was meant more for
debugging but it is better to lock it off by default due to potential security
risks.

**Enable fetching any ref from git repo**

| PR: https://pagure.io/koji/pull-request/3509

Support for fetching any refs which were not fetched by original ``git clone``.
Typically merge requests.

**Error on list-tagged --sigs --paths without mount**

| PR: https://pagure.io/koji/pull-request/3531

It was confusing for users that there is no output if they don't have
``/mnt/koji`` (or other topdir) mounted. Such combination of options now fail
instead of printing empty output.

**Fix restartHosts on py 3.5+**

| PR: https://pagure.io/koji/pull-request/3541

Newer python introduced behaviour which leads to non-working ``restartHosts``
task parent.

System Changes
--------------
**Build policy**

| PR: https://pagure.io/koji/pull-request/3407

New ``build_rpm`` policy for specifying which builds are allowed. It is
superceeding ``build_from_srpm`` and ``build_from_repo_id`` policies,
effectively adding capability for ``build_from_scm`` policy and merging these to
one more simple. Former two are now deprecated and will be removed in 1.33.

**Save source for wrapperRPM**

| PR: https://pagure.io/koji/pull-request/3417

``wrapperRPM`` is now more compatible with regular rpm builds storing
``source`` into metadata.

**Header-based sessions**

| PR: https://pagure.io/koji/pull-request/3426

Formerly, we've had session id and key as a part of URL. These values are now
moved to HTTP headers to be more in line with current security practices.
Backward compatibility is still ensured and can be turned off by
``DisableURLSessions`` in config. Old-style session support will be removed in
1.34.

**Move database classes and functions to koji/db.py**

| PR: https://pagure.io/koji/pull-request/3474
| PR: https://pagure.io/koji/pull-request/3489
| PR: https://pagure.io/koji/pull-request/3563
| PR: https://pagure.io/koji/pull-request/3513

Most of the database queries are rewritten to use ``*Processor`` classes which
improves maintanability and allows easier migration to SQLAlchemy or other
library. Also all db code is now in ``koji/db.py``, so also other tools can
utilize it (typically ``koji-sweep-db`` script).

**Emphasize non-working image XML**

| PR: https://pagure.io/koji/pull-request/3490

Koji is supporting more output formats for images than libvirt can utilize. For
these we're adding some more info directly to libvirt's XML, so end-user is more
informed about need to convert the data to some format libvirt supports.

**Log when session ID, session key and hostip is not related**

| PR: https://pagure.io/koji/pull-request/3557

Additional logging for security/audit reasons, so we can more easily detect
e.g. session stealing.

**Fedora 37 compatibility update**

| PR: https://pagure.io/koji/pull-request/3592

Python 3.11 finally dropped ``inspect.getargspec``, so hub/web are not running
on F37. Simple update to ``getfullargspec`` fixes it. Change is backward-compatible to
python 3.6 which is still oldest :doc:`supported version
<../supported_platforms>` for hub/web.

Web
---
**Add active sessions web page**

| PR: https://pagure.io/koji/pull-request/3446

In line with other security/transparency items in this release, we've added
simple web page to list all active sessions user currently have.

**More generic taskinfo parameter handling**

| PR: https://pagure.io/koji/pull-request/3455

Task web page sometimes shows cryptic messages like "Parameters are not right
for this method" and for some less integrated plugins it shows just python dict
of values. This was improved to handle such values more systematically.

Plugins
-------
**kiwi: Fix include path**

| PR: https://pagure.io/koji/pull-request/3555

More safe include handling in kiwi's profiles.

**kiwi: Propagate --type option**

| PR: https://pagure.io/koji/pull-request/3558

New option to select image type.

**kiwi: Bind builders's /dev only in old_chroot**

| PR: https://pagure.io/koji/pull-request/3585

Device-mapper based images needs exposed /dev/mapper/control file, but not whole
dev filesystem. /dev filesystem is now mounted only in ``old_chroot`` buildroots.
Nspawn-based buildroots (``mock.new_chroot=True``) don't bind it and for dm there
is a corresponding mock `change
<https://github.com/rpm-software-management/mock/pull/1005>`_.

Utilities
---------
**koji-gc: Fix check for type cc_addr, bcc_addr**

| PR: https://pagure.io/koji/pull-request/3573

**koji-sweep-db: fix**

| PR: https://pagure.io/koji/pull-request/3566

**Add absolute to clean sessions in koji-sweep-db**

| PR: https://pagure.io/koji/pull-request/3569


VM
--
**Various updates to kojivmd**

| PR: https://pagure.io/koji/pull-request/3503
| PR: https://pagure.io/koji/pull-request/3504
| PR: https://pagure.io/koji/pull-request/3505
| PR: https://pagure.io/koji/pull-request/3507
| PR: https://pagure.io/koji/pull-request/3538
| PR: https://pagure.io/koji/pull-request/3576
| PR: https://pagure.io/koji/pull-request/3577
| PR: https://pagure.io/koji/pull-request/3578

Various updates to changes in libvirt, improving error handling, VM cleanup,
better repo handling, python3 and documentation fixes.

Documentation
-------------
**Explain waitrepo tasks in vm channel**

| PR: https://pagure.io/koji/pull-request/3506

**Change license identifiers to SPDX format**

| PR: https://pagure.io/koji/pull-request/3521

**Increase unit tests**

| PR: https://pagure.io/koji/pull-request/3528
| PR: https://pagure.io/koji/pull-request/3548
| PR: https://pagure.io/koji/pull-request/3546


