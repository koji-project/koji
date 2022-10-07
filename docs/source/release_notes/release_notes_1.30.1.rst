
Koji 1.30.1 Release notes
=========================

All changes can be found in `the roadmap <https://pagure.io/koji/roadmap/1.30.1/>`_.
Most important changes are listed here.


Migrating from Koji 1.30
------------------------

No special actions are needed.

Security Fixes
--------------

None

Hub Changes
-----------
**Use nextval function instead of query 'SELECT nextval'**

| PR: https://pagure.io/koji/pull-request/3484

Incremental step to remove raw SQL queries.

**Return data when query execute asList with transform**

| PR: https://pagure.io/koji/pull-request/3513

Bug removal in part of code which was not used yet.

Client Changes
--------------
**Allow redirects for file size checking**

| PR: https://pagure.io/koji/pull-request/3464

Commands downloading files from the server were not properly checking file size
when trying to append partially downloaded files.

**Download all files, skip downloaded files**

| PR: https://pagure.io/koji/pull-request/3502

Regression fix for 1.30 to have backward-compatible behaviour with
``download-task``.

Builder Changes
---------------
**Various simple updates to windows content builder**

| PR: https://pagure.io/koji/pull-request/3503
| PR: https://pagure.io/koji/pull-request/3504
| PR: https://pagure.io/koji/pull-request/3505
| PR: https://pagure.io/koji/pull-request/3507

Plugins
-------
**kiwi: Handle include protocols**

| PR: https://pagure.io/koji/pull-request/3496

Forbid other include protocols than ``this://`` to prevent directory traversal.

**kiwi: Explicitly use koji-generated description**

| PR: https://pagure.io/koji/pull-request/3498

Koji now requires user to explicitely select descriptions file instead of
leaving it up to kiwi to select the right one.

Web Changes
-----------
**More generic taskinfo parameter handling**

| PR: https://pagure.io/koji/pull-request/3455

Internal change to use standardized parameter handling on ``taskinfo`` page.
This also replace "Parameters are not correct for this method." with data
display.

**Fix dist-repo repo.json url**

| PR: https://pagure.io/koji/pull-request/3469

``repoinfo`` page display correct link to distrepos.

**Fix arch filter in list of hosts webUI**

| PR: https://pagure.io/koji/pull-request/3492

Filtering via arch sometimes returned additional records.


Documentation/DevTools Changes
------------------------------
* `Fix flake8 errors <https://pagure.io/koji/pull-request/3479>`_
* `Fix URLs to pull requests <https://pagure.io/koji/pull-request/3481>`_
* `Block py3 compilation in py2 env <https://pagure.io/koji/pull-request/3486>`_
* `Explain waitrepo tasks in vm channel <https://pagure.io/koji/pull-request/3506>`_
* `Fix missing characters in config example <https://pagure.io/koji/pull-request/3518>`_
