Koji 1.35.3 Release notes
=========================

All changes can be found in `the roadmap <https://pagure.io/koji/roadmap/1.35.3/>`_.
Most important changes are listed here.

This is a small bugfix release to address a few issues in 1.35.2

Migrating from Koji 1.35.x
--------------------------

No special action are needed.


Security Fixes
--------------

None


System Changes
--------------

**Handle duplicate logs for image imports**

| PR: https://pagure.io/koji/pull-request/4232

This works around a build import issue by adding the arch to the log path when an overlap is detected.


**Fix min_avail calculation**

| PR: https://pagure.io/koji/pull-request/4358

This fixes an internal calculation in the scheduler code.


**Fix hub option data types**

| PR: https://pagure.io/koji/pull-request/4310

This fixes the data types for several hub options that were added in 1.35.
Prior to this fix, specifying some of these options could result in an error.


Kojira
------

**Keep latest default repo for build tags**

| PR: https://pagure.io/koji/pull-request/4270

This change causes kojira to preserve the latest repo for a build tag, even if it is no longer current.

Previously, because of the on-demand repo generation changes in 1.35, rarely used build targets could end
up with no repo at all.


Web UI
------

**Fix tasks url on userinfo page**

| PR: https://pagure.io/koji/pull-request/4303

A small bug fix in the web ui


**Work around parse_qs behavior in python < 3.11**

| PR: https://pagure.io/koji/pull-request/4334

This fixes a web ui bug resulting from the removal of the cgi module dependency in 1.35.2.


Devel and testing
-----------------

**Fix two unit test issues**

| PR: https://pagure.io/koji/pull-request/4357


**Fix python2 unittests**

| PR: https://pagure.io/koji/pull-request/4341


**Use unittest.mock instead of mock**

| PR: https://pagure.io/koji/pull-request/4328


**Remove fp file using os.unlink**

| PR: https://pagure.io/koji/pull-request/4326

Compatibility fix for unit tests
