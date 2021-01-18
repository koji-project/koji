Koji 1.23.1 Release notes
=========================

All changes can be found at `pagure <https://pagure.io/koji/roadmap/1.23.1/>`_.
Most important changes are listed here.

Migrating from Koji 1.23
------------------------

No special actions are needed.

PR#2579: Install into /usr/lib rather than /usr/lib64/

Security Fixes
--------------

**web: XSS vulnerability**

| PR: https://pagure.io/koji/pull-request/2652

CVE-2020-15856 - Web interface can be abused by XSS attack. Attackers can supply
subversive http links containing malicious javascript code. Such links were not
controlled properly, so attackers can potentially force users to submit actions
which were not intended. Some actions which can be done via web UI can be
destructive, so updating to this version is highly recommended.

System Changes
--------------
**Revert "timezones for py 2.7"**

| PR: https://pagure.io/koji/pull-request/2569

We've returned some behaviour which prevented time operations on py 2.7

Library Changes
---------------
**lib: better argument checking for eventFromOpts**

| PR: https://pagure.io/koji/pull-request/2517

``eventFromOpts`` can now properly parse ``after`` and ``before`` arguments.

Hub Changes
-----------
**hub: use CTE for build_references**

| PR: https://pagure.io/koji/pull-request/2567

This should improve kojira's performance in some cases.

Builder Changes
---------------
**mergerepo uses workdir as tmpdir**

| PR: https://pagure.io/koji/pull-request/2547

Until now mergerepo used /tmp instead of workdir. It could lead to space
exhaustion if there is not enough space there. Workdir gets cleaned more often.

Web Changes
-----------
**disable links to deleted tags**

| PR: https://pagure.io/koji/pull-request/2558

**Only redirect back to HTTP_REFERER if it points to kojiweb**

| PR: https://pagure.io/koji/pull-request/2504

Utilities Changes
-----------------
**kojira: don't expire ignored tags with targets**

| PR: https://pagure.io/koji/pull-request/2548

Ignored tags' repos were expired even in case when they've had targets. It is
fixed now and ignored tags are really ignored.

**kojira: cache external repo timestamps by arch_url**

| PR: https://pagure.io/koji/pull-request/2533

Fix of bug which could have missed some split repositories updates.

Documentation Changes
---------------------

**assign multicall to "m" in code example**

| PR: https://pagure.io/koji/pull-request/2593

**api docs**

| PR: https://pagure.io/koji/pull-request/2509

**python support matrix**

| PR: https://pagure.io/koji/pull-request/2528
