Koji 1.29.1 Release notes
=========================

All changes can be found in `the roadmap <https://pagure.io/koji/roadmap/1.29.1/>`_.
Most important changes are listed here.

Migrating from Koji 1.29
------------------------

No special actions are needed.


Security Fixes
--------------

None

Library Changes
---------------

Client Changes
--------------
**Download output for all task types in download-task**

| PR: https://pagure.io/koji/pull-request/3343

It was not possible to download e.g. image scratch task. We've
extended download options, so all task types can be downloaded now.

Hub Changes
-----------
**postgresql hub: date_part instead of EXTRACT**

| PR: https://pagure.io/koji/pull-request/3388

PostgreSQL 14 introduced small changes in formats which led to failing koji on
Fedora rawhide.

**Rename log to cg_import.log and add successful import log message.**

| PR: https://pagure.io/koji/pull-request/3415

Small change renaming log from 1.29 `external_rpm_warning.log` was too
confusing, so we've renamed it to `cg_import.log` and added final SUCCESS
message.

**more verbose default policy denials**

| PR: https://pagure.io/koji/pull-request/3398

Default policies were not verbose enough, so it could be overseen that they are
used instead of local policies from some reason (typically apache can't read the
proper config).

**Fix wrong encoding in changelog entries**

| PR: https://pagure.io/koji/pull-request/3413

There are still some very old rpms which contain broken unicode in their
changelogs (behaviour which is impossible to trigger nowadays). We're going to
replace the broken characters with '?'.

Web Changes
-----------
**Order channels at hosts page**

| PR: https://pagure.io/koji/pull-request/3368

Simple change to use ordered channel listing in place of random order.

Plugins
-------

**Fix arches check in kiwi plugin**

| PR: https://pagure.io/koji/pull-request/3428

As part of 1.29 security improvements we've made a regression about architecture
handling in kiwi plugin which prevented builds. It is fixed now and works as
before.

Documentation/DevTools Changes
------------------------------
 * `Add long description to setup.py <https:/pagure.io/koji/pull-request/3374`_
 * `CGRefundBuild description in CG docs <https://pagure.io/koji/pull-request/3411`_
