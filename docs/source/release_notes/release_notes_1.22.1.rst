Koji 1.22.1 Release notes
=========================

All changes can be found at `pagure <https://pagure.io/koji/roadmap/1.22.1/>`_.
Most important changes are listed here.

Migrating from Koji 1.22
------------------------

No special actions are needed.

Security Fixes
--------------
None

Library changes
---------------
**Fix time formatting for timezone values**

| PR: https://pagure.io/koji/pull-request/2409

Some datetime values returned from hub were not properly parsed which resulted
in failing CLI/web. We've replaced it with GMT timestamps internally, so we are
more sure about their proper timezones.

Hub Changes
-----------
**ensure that cursors are closed in QueryProcessor.iterate()**

| PR: https://pagure.io/koji/pull-request/2436

In some cases (especially ``hastag`` policy in combination with ``clone-tag``)
there were allocated db cursors but not freed.

**stricter config file permissions**

| PR: https://pagure.io/koji/pull-request/2474

Hub and web config files contains sensitive values. We've made permissions
stricter by default and encourage existing users to review theirs.

Builder Changes
---------------
**builder: handle btrfs subvolumes in ApplianceTask**

| PR: https://pagure.io/koji/pull-request/2365

When using btrfs, the / mountpoint can be associated with a subvolume; if that's
the case, return the btrfs partition as the root device. Note that this
implementation assumes there's only one btrfs partition defined in kickstart.

**fix extra-boot-args option**

| PR: https://pagure.io/koji/pull-request/2452

``bootloader append`` directive in kickstart wasn't properly passed to lorax.

API Changes
-----------
**editTag: make compat perm_id option an alias for perm**

| PR: https://pagure.io/koji/pull-request/2409

It is a backward compatible change.


Documentation Changes
---------------------
**setting rpm macros for build tags**

| PR: https://pagure.io/koji/pull-request/2410


**more info about permission system**

| PR: https://pagure.io/koji/pull-request/2415

**migration note regarding dropped krb configuration options**

| PR: https://pagure.io/koji/pull-request/2427
