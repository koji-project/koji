
Koji 1.32.1 Release notes
=========================

All changes can be found in `the roadmap <https://pagure.io/koji/roadmap/1.32.1/>`_.
Most important changes are listed here.


Migrating from Koji 1.32
------------------------

No special actions are needed.

Security Fixes
--------------

None

Client Changes
--------------
**list-untagged: One space of double space before references**

| PR: https://pagure.io/koji/pull-request/3731

Simple unification of output format.

**Delete double check existing source tag, --batch option is invisible**

| PR: https://pagure.io/koji/pull-request/3706

Option doesn't make sense for server-side clonetag anymore.

System Changes
--------------
**fix query for partially generated checksums**

| PR: https://pagure.io/koji/pull-request/3692
| PR: https://pagure.io/koji/pull-request/3694

Fix the query logic for new API ``getRPMChecksums``.


Plugins
-------
**ArgumentParser instead of ArgumentParser in sidetag CLI plugin**

| PR: https://pagure.io/koji/pull-request/3740

Unified with the other code we've. This was the only place using
``ArgumentParser`` instead of ``OptionParser``. It is step back, but better for
testing. When we finally drop py2 code, it will be reverted.

**Add missing argument in edit-sidetag help msg**

| PR: https://pagure.io/koji/pull-request/3718

Fixed help message.


Documentation
-------------
**Fix timezone in clone-tag test case**

| PR: https://pagure.io/koji/pull-request/3734

**Unify migration script Koji 1.31 -> 1.32**

| PR: https://pagure.io/koji/pull-request/3697

Migration scripts were split to two files. Merged to one.
