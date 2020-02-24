Koji 1.20.1 Release notes
=========================

This is first regular minor release. We're trying new release cycle. It should
involve of regular releases (1.x.0) roughly every three months. In between there
should be one minor release (1.x.1) with bugfixes and documentation updates.

Overall policy for minor release is, that it shouldn't contain anything changing
API or any compatibility features. Neither it should touch the db schema. Client
has to be completely compatible with 1.x.0 version.

Reason to introduce them is to make quicker delivery of simple fixes to end
users. As an administrator of koji instance you're free to not/update as you
wish. There also needs to be clear update path from 1.x via 1.x.1 to 1.x+1.

Anyway, if some security or important bugfix is found anywhere during 1.x cycle,
we're going to do additional minor release addressing this problem. We will
announce it properly through standard channels (mainly koji-devel mailing list).

All changes can be found at `pagure <https://pagure.io/koji/roadmap/1.20.1/>`_.
Most important changes are listed here.

Migrating from Koji 1.20
------------------------

No special actions are needed.

Security Fixes
--------------
None

Client Changes
--------------
**Fix flags display for list-tag-inheritance**

| PR: https://pagure.io/koji/pull-request/1929

Fix of the bug with garbage output for given command.

**Don't use full listTags in list-groups call**

| PR: https://pagure.io/koji/pull-request/1967

Speed improvement - sidetags introduced large tag sets which slowed down some
calls.

Library Changes
---------------
**Always use stream=True when iterating over a request**

| PR: https://pagure.io/koji/pull-request/1993

Bug introduced in 1.20 could cause kojid running out of memory.

API Changes
-----------
None

Web UI Changes
--------------
**Display params also for malformed tasks in webui**

| PR: https://pagure.io/koji/pull-request/1488

**Display some taskinfo for deleted buildtags**

| PR: https://pagure.io/koji/pull-request/1920

**Expect, that hub is returning GM time**

| PR: https://pagure.io/koji/pull-request/1919

Information on taskinfo page could have wrong times.

Builder Changes
---------------

**Ensure that all keys in distrepo are lowered**

| PR: https://pagure.io/koji/pull-request/1982

Distrepo now should treat sigkeys as case-insensitive.

System Changes
--------------
**Improve sql speed in build_references**

| PR: https://pagure.io/koji/pull-request/1962

``build_references`` was using one of the slowest SQL calls in koji. It was
rewritten now to be faster.

Utilities Changes
-----------------

Garbage Collector
.................
None

DB Sweeper
..........
**Analyze/vacuum all affected tables**

| PR: https://pagure.io/koji/pull-request/1944

There was a mistake in vacuumed table and one another was missing.

Kojikamid
.........
None

Documentation Changes
---------------------
**Fix help message for list-groups**

| PR: https://pagure.io/koji/pull-request/1947

**Fix usage message for add-pkg**

| PR: https://pagure.io/koji/pull-request/1946

**improve search() API documentation**

| PR: https://pagure.io/koji/pull-request/1995

**Docs for kojira and koji-gc**

| PR: https://pagure.io/koji/pull-request/1935
