Koji 1.21.0 Release notes
=========================

Announcement: We're going to drop python 2 support for hub and web in koji 1.22.
Please, prepare yourself for deploying python 3 versions of these. Both are
already supported and this is the next step in retiring python 2 codebase.

All changes can be found at `pagure <https://pagure.io/koji/roadmap/1.21/>`_.
Most important changes are listed here.

Migrating from Koji 1.20
------------------------

For details on migrating see :doc:`../migrations/migrating_to_1.21`

Security Fixes
--------------
None

Client Changes
--------------
**Add --no-delete option to clone-tag**

| PR: https://pagure.io/koji/pull-request/1385

``clone-tag`` command was enhanced to produce 'copy' operation without deleting
what is in the target tag. See PR for detailed semantics, as it could be
confusing a bit.

**display merge mode for external repos**

| PR: https://pagure.io/koji/pull-request/2097

Merge modes are now listed in taginfo command (and also in web ui)

**koji download-build resuming downloads**

| PR: https://pagure.io/koji/pull-request/2080

``download-build`` could often break for bigger builds. Resuming truncated
download after relaunch is now default behaviour.

**add-host work even if host already tried to log in**

| PR: https://pagure.io/koji/pull-request/2042

Previously, if builder contacted before its user was created in db, it was hard
to fix it. Now, it could be forced via cli's ``--force``.

**Allow to skip SRPM rebuild for scratch builds**

| PR: https://pagure.io/koji/pull-request/2083

Rebuilding SRPMs doesn't make much sense in most of scratch builds. There is an
option ``--no-rebuild-srpm`` which can be used to skip this step. Note, that it
doesn't work for regular builds, which needs to adhere to policy set by
rel-engs.

**Deprecating list-tag-history and tagHistory**

| PR: https://pagure.io/koji/pull-request/938

These commands are superseded by ``list-history`` resp. ``queryHistory`` and
will be removed in near future.

**Add detail about known koji signatures to buildinfo**

| PR: https://pagure.io/koji/pull-request/2016

If koji knows about any signatures, they are now also printed.

**deprecation of krb_login**

| PR: https://pagure.io/koji/pull-request/1992

gssapi_login should be now used wherever possible

Library Changes
---------------

**Remove deprecated functions**

| PR: https://pagure.io/koji/pull-request/1984
| PR: https://pagure.io/koji/pull-request/2001

md5/sha1 constructors and cgi.escape functions were removed.

API Changes
-----------

**editTagExternalRepo is able to set merge_mode**

| PR: https://pagure.io/koji/pull-request/2051

Removing and re-adding external repo is no more needed if user just needs to
change merge strategy.

**Remove debugFunction API**

| PR: https://pagure.io/koji/pull-request/1863

Removed deprecated call

Builder Changes
---------------

**make xz options configurable**

| PR: https://pagure.io/koji/pull-request/2028

xz compression for images now can be configured on builder level. It can be
tuned accordingly to CPU/memory ratio available.

**Delete oldest failed buildroot when there is no space**

| PR: https://pagure.io/koji/pull-request/2082

If there is no space on builder, we try to delete buildroots from oldest to
newest. It could be harder to debug some failed builds, as those data can be
already deleted, on the other hand, builders will not refuse to work due to lack
of space.

System Changes
--------------

**new policy for dist-repo**

| PR: https://pagure.io/koji/pull-request/2081

Previously only users with ``dist-repo`` permission were allowed to run it. Now,
there could be a policy defined, mostly based on tag or user names.

**Add 'target' policy**

| PR: https://pagure.io/koji/pull-request/1058

We used it before, but with generic tests like ``match``. Now we have proper
``target`` policy test.

**always set utf8 pg client encoding**

| PR: https://pagure.io/koji/pull-request/2105

We're now forcing utf8 client encoding for database connection.

**Limit final query by prechecking buildroot ids**

| PR: https://pagure.io/koji/pull-request/2074

Significant performance improvement for ``query_buildroots``.

**use real time for events**

| PR: https://pagure.io/koji/pull-request/2068

Events now should be created with real-world time, not with the beginning of
transaction. It could have led to non-clear history in some cases, it should be
better now.

**log --force usage by admins**

| PR: https://pagure.io/koji/pull-request/2019

Using ``--force`` to override policies is now logged.

**Add smtp authentication support**

| PR: https://pagure.io/koji/pull-request/692

SMTP authentication is now available in kojid and koji-gc.

Plugins
-------

**Sidetag plugin is now part of koji**

| PR: https://pagure.io/koji/pull-request/1956
| PR: https://pagure.io/koji/pull-request/2006
| PR: https://pagure.io/koji/pull-request/2004

We've integrated sidetag plugin to koji, so we can add more integrated
functionality to it.

**allow debuginfo for sidetag repos**

| PR: https://pagure.io/koji/pull-request/1990

sidetag repos can now contain debuginfo packages (``--debuginfo`` option for
``add-sidetag`` command).

**New call editSideTag**

| PR: https://pagure.io/koji/pull-request/2054

New API call allowing users of sidetags to modify certain values (debuginfo,
package lists).

**Emit user in PackageListChange messages**

| PR: https://pagure.io/koji/pull-request/1059

protonmsg now sends also user name and id.

**limit size of extra field in proton msgs**

| PR: https://pagure.io/koji/pull-request/2047

``extra`` field can be omitted from proton message if it exceeds configured
threshold. Some content generators can create very big ``extra`` data which
needn't to be sent via message bus and can be queried on demand via API.

Utilities Changes
-----------------

Garbage Collector
.................

**file locking for koji-gc**

| PR: https://pagure.io/koji/pull-request/1333

As GC can run for long periods of time, ensuring, that there is only one
instance running is worthwile. ``--lock-file`` and ``--exit-on-lock``

Kojira
......

**kojira monitors external repos changes**

| PR: https://pagure.io/koji/pull-request/516

External repositories are now monitored and kojira will trigger ``newRepo``
tasks when their content changed.

**reverse score ordering for tags**

| PR: https://pagure.io/koji/pull-request/2022

Fixed bug which regenerated repositories in least-important-first order.

Documentation Changes
---------------------

Lot of documentation was added in last release in API and also in docs pages.

**Documentation**

| PR: https://pagure.io/koji/pull-request/2057
| PR: https://pagure.io/koji/pull-request/2129
| PR: https://pagure.io/koji/pull-request/2128
| PR: https://pagure.io/koji/pull-request/2078
| PR: https://pagure.io/koji/pull-request/2079
| PR: https://pagure.io/koji/pull-request/2034
| PR: https://pagure.io/koji/pull-request/1975

**API**

| PR: https://pagure.io/koji/pull-request/1987
| PR: https://pagure.io/koji/pull-request/2000

**CLI**

| PR: https://pagure.io/koji/pull-request/2071
