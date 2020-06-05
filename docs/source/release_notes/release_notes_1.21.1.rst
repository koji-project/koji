Koji 1.21.1 Release notes
=========================

All changes can be found at `pagure <https://pagure.io/koji/roadmap/1.21.1/>`_.
Most important changes are listed here.

Migrating from Koji 1.21
------------------------

No special actions are needed.

Security Fixes
--------------
None

Client Changes
--------------

**Don't use listTagged(tag, *) for untag-build**

| PR: https://pagure.io/koji/pull-request/2038

Simple change which speeds up ``untag-build`` call.

**Fix list-signed --tag memory issues**

| PR: https://pagure.io/koji/pull-request/2103

Another performance improvement - rpms are filtered on hub's side on client's.

**Fix variable name**

| PR: https://pagure.io/koji/pull-request/2224

Koji buildinfo could have failed on missing content generator fiels.

**Fix un/lock-tag permission handling**

| PR: https://pagure.io/koji/pull-request/2223

Bug caused unlock-tag to fail on missing permission for admin.

Library changes
---------------

**don't decode signature headers**

| PR: https://pagure.io/koji/pull-request/2268

Some rpm signature headers were not handled properly.

Hub Changes
-----------

**Admin can force tag now**

| PR: https://pagure.io/koji/pull-request/2203

Previously admin cannot force policy for tagging. Now admins can override the
policy and force tagging.

Utilities Changes
-----------------

Garbage Collector
.................

**fix query order**

| PR: https://pagure.io/koji/pull-request/2279

New ``queryHistory`` method doesn't sort output, so sorting on client side is
needed. It is returned in DB preferred order which seems to work for PG, but
better safe than sorry.

**koji-gc: various typos in maven path**

| PR: https://pagure.io/koji/pull-request/2153

This is the important regression fix for bug which caused koji-gc to fail in
many cases.

**koji-gc: test existence of trashcan tag**

| PR: https://pagure.io/koji/pull-request/2211

We assumed that ``trashcan`` tag exists. If it is not the case GC will notice it
relatively late. This is additional check during the start.

Kojira
......

**kojira: use cached getTag for external repos**

| PR: https://pagure.io/koji/pull-request/2157

Use cached values for external repos checks.

Documentation Changes
---------------------

**Links to copr builds**

| PR: https://pagure.io/koji/pull-request/2248


**Fix sidetag enablement typo**

| PR: https://pagure.io/koji/pull-request/2178


**Document removeExternalRepoFromTag arguments**

| PR: https://pagure.io/koji/pull-request/2174


**Extend docs for --before/--after options**

| PR: https://pagure.io/koji/pull-request/2245


**API docs**

| PR: https://pagure.io/koji/pull-request/2241
| PR: https://pagure.io/koji/pull-request/2242


**Document addExternalRepoToTag arguments**

| PR: https://pagure.io/koji/pull-request/2158


**Remove obsoleted note**

| PR: https://pagure.io/koji/pull-request/2194

**Update for mod_auth_gssapi configuration**

| PR: https://pagure.io/koji/pull-request/2141
