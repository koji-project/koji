
Koji 1.33.1 Release notes
=========================

All changes can be found in `the roadmap <https://pagure.io/koji/roadmap/1.33.1/>`_.
Most important changes are listed here.


Migrating from Koji 1.33
------------------------

No special actions are needed.

Security Fixes
--------------

None

Client Changes
--------------

**Streamline python/json options in call command**

| PR: https://pagure.io/koji/pull-request/3846

Better JSON/python support in CLI ``call`` command.

System Changes
--------------
**Wait with writing timestamps after results dir is created**

| PR: https://pagure.io/koji/pull-request/3834

In some cases using ``log_timestamps`` option on builder resulted in traceback
as results directory hasn't existed yet.

**Add support for sw_64 and loongarch64**

| PR: https://pagure.io/koji/pull-request/3836

Support for these architectures in ``distrepo``.

WWW
---
**Fix duplicate build link on CG taskinfo page**

| PR: https://pagure.io/koji/pull-request/3857

As there is historically more places where CG can store build link in task, web
page could have displayed duplicit links.

VM
--
**Drop stray typing hint**

| PR: https://pagure.io/koji/pull-request/3864

Typo (py3 typing hint) which prevents python2 version of kojivmd from running.


Documentation
-------------
**Basic vim syntax highlighting for hub policy**

| PR: https://pagure.io/koji/pull-request/3839

Simple syntax highlighting file for koji policies. It makes mistakes a bit more
visible. Nevertheless, policy syntax doesn't have strict grammar, so don't rely
only on this.

**readTaggedRPMS/Builds API documentation**

| PR: https://pagure.io/koji/pull-request/3840
