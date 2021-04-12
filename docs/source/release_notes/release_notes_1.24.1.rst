Koji 1.24.1 Release notes
=========================

All changes can be found at `pagure <https://pagure.io/koji/roadmap/1.24.1/>`_.
Most important changes are listed here.

Migrating from Koji 1.24
------------------------

No special actions are needed.

Security Fixes
--------------

None

System Changes
--------------
**drop PyOpenSSL usage**

Library is no longer needed (superseded by ``requests``).

| PR: https://pagure.io/koji/pull-request/2753

Library changes
---------------

**revert "requests exception"**

Regression fix for retrying requests to hub.

| PR: https://pagure.io/koji/pull-request/2787

CLI changes
-----------
**adding check for the license header key**

The CLI could sometimes fail on a missing header key. This no longer happens.

| PR: https://pagure.io/koji/pull-request/2692

Hub Changes
-----------
**set correct import_type for volume policy in completeImageBuild**

Policy data provided incorrect ``import_type`` (maven instead of image)

| PR: https://pagure.io/koji/pull-request/2713

Web Changes
-----------
**escape vcs and disturl**

Web page correctly escapes these URLs now.

| PR: https://pagure.io/koji/pull-request/2747

**optional KojiHubCA usage**

Koji 1.24 introduced a bug where the ``KojiHubCA`` option was required even in
cases when SSL auth was not used for web. Fixed.

| PR: https://pagure.io/koji/pull-request/2749

Utilities Changes
-----------------
**repo removal improvements**

A few bugs related to kojira's repo removal have been fixed. In some cases,
these bugs could have stalled delete threads or even blocked repo deletions
altogether.

| PR: https://pagure.io/koji/pull-request/2755
| PR: https://pagure.io/koji/pull-request/2715
| PR: https://pagure.io/koji/pull-request/2699

Documentation/DevTools Changes
------------------------------
**remove "ca" option from server howto**

| PR: https://pagure.io/koji/pull-request/2725

**update kojid steps in server howto**

| PR: https://pagure.io/koji/pull-request/2724

**fix Fedora's koji URL**

| PR: https://pagure.io/koji/pull-request/2777

**jenkins fedora -> centos migration**

| PR: https://pagure.io/koji/pull-request/2754

**document getNextRelease method**

| PR: https://pagure.io/koji/pull-request/2706

**Additional docs for CVE-2020-15856**

| PR: https://pagure.io/koji/pull-request/2717

**Fix small documentation typo**

| PR: https://pagure.io/koji/pull-request/2772

**set WSGIProcessGroup inside Directory**

| PR: https://pagure.io/koji/pull-request/2731

**tests: stop mock in DBQueryTest**

| PR: https://pagure.io/koji/pull-request/2759

**devtools: updated Dockerfiles**

| PR: https://pagure.io/koji/pull-request/2744
