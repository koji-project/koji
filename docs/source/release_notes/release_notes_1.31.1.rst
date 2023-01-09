
Koji 1.31.1 Release notes
=========================

All changes can be found in `the roadmap <https://pagure.io/koji/roadmap/1.31.1/>`_.
Most important changes are listed here.


Migrating from Koji 1.31
------------------------

No special actions are needed.

Security Fixes
--------------

None


Client Changes
--------------
**Support deleted build tag in taskinfo**

| PR: https://pagure.io/koji/pull-request/3604

As sidetag plugin with garbage-collection is now widely used,
people are often querying tasks which refers to already deleted
tags. This is one of the places which were not behaving correctly.

Builder Changes
---------------
**Use old-style checkout for shortened refs**

| PR: https://pagure.io/koji/pull-request/3630

In 1.31 we've introduced patch for checking out GIT content from
any ref. Nevertheless, it broke dealing with short refs. Fixed
now.

System Changes
--------------
**Create DeleteProcessor class and use it**

| PR: https://pagure.io/koji/pull-request/3601

Continuing work on moving from raw SQL.

- PR#3611: Replace deprecated inspect methods

Python 3.11 is dropping some older inspect API we were using.

**Fix different PG capabilities in schema**

| PR: https://pagure.io/koji/pull-request/3615

1.31 introduced new index which is supported only in postgres 12.
This resulted in problems with installation on older systems.
We've fixed update script to behave accordingly to installed
postgres. Also updated :doc:`../../supported_platforms` to encourage PG 12
usage.

Web
---
**Fix target link in taskinfo page**

| PR: https://pagure.io/koji/pull-request/3644

Simple typo breaking link to target.

**Change canceled icon color from red to orange**

| PR: https://pagure.io/koji/pull-request/3607

Unify default CSS.

Plugins
-------
**Kiwi: fix typo preventing building docker images**

| PR: https://pagure.io/koji/pull-request/3620

1.30 introduced bug preventing correct architecture parsing.

**Kiwi: upload log for failed tasks**

| PR: https://pagure.io/koji/pull-request/3598

Image root log is now uploaded incrementally and uploaded also for
failing tasks.

Documentation
-------------
**Better wording in listTagged docstring**

| PR: https://pagure.io/koji/pull-request/3639

**Typo in CLI add-tag-inheritance error msg**

| PR: https://pagure.io/koji/pull-request/3641

**Increase unit tests**

| PR: https://pagure.io/koji/pull-request/3650
