
Koji 1.34.1 Release notes
=========================

All changes can be found in `the roadmap <https://pagure.io/koji/roadmap/1.34.1/>`_.
Most important changes are listed here.


Migrating from Koji 1.34
------------------------

No special actions are needed.

Security Fixes
--------------

None

Client Changes
--------------
**Fix scheduler log ordering**

| PR: https://pagure.io/koji/pull-request/4018

Scheduler logs were returned in random order.

**--limit from scheduler-logs/info**

| PR: https://pagure.io/koji/pull-request/4043

List only limited set of records.

System Changes
--------------

**policy_data_from_task_args: set target to None when it doesn't exist**

| PR: https://pagure.io/koji/pull-request/3942

Deleted targets which remained in the policy rules could have led to hub
tracebacks.

**Oz: don't hardcode the image size unit as 'G'**

| PR: https://pagure.io/koji/pull-request/3989

New oz versions allow usage of different units.

**Typo in set_refusal**

| PR: https://pagure.io/koji/pull-request/3998

Fix for scheduler bug which is not critical but could create tracebacks in the
hub log.

**Have builders refuse repo tasks if they can't access /mnt/koji**

| PR: https://pagure.io/koji/pull-request/3999

Simple check that if builder is missing required mountpoint, it will refuse the
createrepo tasks instead of failing later.

**rmtree: use fork**

| PR: https://pagure.io/koji/pull-request/4012

Parallel deletions in some cases can lead to error messages in the hub log.

**Provide draft flag to build policy**

| PR: https://pagure.io/koji/pull-request/4015

Provide information about draft builds for "build" policy.

**Implicit task refusals**

| PR: https://pagure.io/koji/pull-request/4032

Improving scheduler planning capability especially for noarch/exclusivearch
packages.

**Fix temporary cg_import.log file path**

| PR: https://pagure.io/koji/pull-request/4037

Fixing 1.34 problem with CG imports with error logs.

**Use host maxtasks if available**

| PR: https://pagure.io/koji/pull-request/4041

Further improvement of scheduler planning.

**Avoid explicit rowlock in taskWaitCheck**

| PR: https://pagure.io/koji/pull-request/4056

Fix for scheduler deadlock issues. They are not critical, but polluting kojid's
log.

**Bandit [B411]: use defusedxml to prevent remote XML attacks**

| PR: https://pagure.io/koji/pull-request/3975
| PR: https://pagure.io/koji/pull-request/4005
| PR: https://pagure.io/koji/pull-request/4069

Implementing bandit-proposed solution to replace base xml library with
defusedxml.

WWW
---

**Add some handy links for module builds**

| PR: https://pagure.io/koji/pull-request/3931

**Fix formatting of rpm in title**

| PR: https://pagure.io/koji/pull-request/4052


Documentation
-------------
**readTaggedRPMS/Builds API documentation**

| PR: https://pagure.io/koji/pull-request/3840

**Remove rpm-py-installer, update test docs and update Dockerfiles**

| PR: https://pagure.io/koji/pull-request/3992

**Document draft builds**

| PR: https://pagure.io/koji/pull-request/3996

**Tests: py3 versions compatibility fixes**

| PR: https://pagure.io/koji/pull-request/4088
