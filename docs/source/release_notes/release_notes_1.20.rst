Koji 1.20.0 Release notes
=========================

Announcement: We're going to drop python 2 support for hub and web in
koji 1.22. Please, prepare yourself for deploying python 3 versions of
these. Both are already supported and this is the next step in
retiring python 2 codebase.

Migrating from Koji 1.19
------------------------

For details on migrating see :doc:`../migrations/migrating_to_1.20`

Security Fixes
--------------
None

Client Changes
--------------
**Add basic zchunk support for dist-repo**

| PR: https://pagure.io/koji/pull-request/1743

Fixes: https://pagure.io/koji/issue/1198

The ``dist-repo`` supports new options ``--zck``, which enables createrepo's
zchunk generation, and ``--zck-dict-dir``, which indicates the directory
the builder that contains zchunk dictionaries to use.

**Add repo waiting options to the build command**

| PR: https://pagure.io/koji/pull-request/1626
| PR: https://pagure.io/koji/pull-request/1889

New options ``--wait-build`` and ``--wait-repo`` for the ``build`` command
cause the build to wait for a repo regeneration.
This is similar to using ``wait-repo`` + ``build`` in succession, except
that the repo monitoring is handled in the build task itself.

**Remove title option for livemedia-creator**

| PR: https://pagure.io/koji/pull-request/1781

livemedia-creator dropped ``--title`` option, so we are.

**Add --disabled option to list-hosts command**

| PR: https://pagure.io/koji/pull-request/1738

This option is simply an alias for the existing ``--not-enabled`` option.

**Unify return values for permission denied**

| PR: https://pagure.io/koji/pull-request/1785

Some places were using ``print`` + ``return 1``, some `parser.error` calls.
Let's unify it to ``parser.error``.

**list-pkgs: Fix opts check**

| PR: https://pagure.io/koji/pull-request/1848
| PR: https://pagure.io/koji/pull-request/1814

Warn if non-compatible options are used.

**Fix downloads w/o content-length**

| PR: https://pagure.io/koji/pull-request/983

When content-length is not specified, whole file is read to memory. Use chunks instead.

**Refine output of list-signed**

| PR: https://pagure.io/koji/pull-request/1828

Removed debug info.


Library Changes
---------------
**Raise error when we have not configuration**

| PR: https://pagure.io/koji/pull-request/1767
| PR: https://pagure.io/koji/pull-request/1787

Previously, Koji would proceed with only the coded defaults,
which is no longer sensible.

**Sanity check on remotely opened RPMs**

| PR: https://pagure.io/koji/pull-request/1829

Sometimes RPMs are not downloaded correctly into buildroot and it results in
weird errors. A simple check was added to detect corruption of downloaded files.

**Replace urllib.request with requests library**

| PR: https://pagure.io/koji/pull-request/1542

**util: Rename "dict" arg**

| PR: https://pagure.io/koji/pull-request/1807

The ``dslice`` and ``dslice_ex`` functions accepted an argument named ``dict``,
which conflicts with a built-in Python type.
These arguments have been renamed to ``dict_``

**Include profile name in parsed config options**

| PR: https://pagure.io/koji/pull-request/1525

Fix behaviour to be in line with docs examples.

**Make rpm import optional in koji/__init__.py**

| PR: https://pagure.io/koji/pull-request/1773
| PR: https://pagure.io/koji/pull-request/1795

``koji/__init__.py`` is being used more and more often in virtualenv. As rpm is
always the pain here and most users don't need those specific functions, we can
make it optional (and require only on spec level). Distribution via PyPi will be
less painful.


API Changes
-----------
**getUser: default krb_princs value is changed to True**

| PR: https://pagure.io/koji/pull-request/1872

This argument was added in PR #1648, whose default value is ``False``.  It is
used to control if to show the ``krb_principals`` list in the result of
``getUser``. It is better to be shown by default, as it may confuse people that
Kerberos principal was deleted.

**drop buildMap API call**

| PR: https://pagure.io/koji/pull-request/1755

It was designed for GC, but it is not used anymore.

**hub: new addArchiveType RPC**

| PR: https://pagure.io/koji/pull-request/1149

Adds a new hub method for inserting new archivetype records.

**raise ``GenericError`` on existing build reservation.**

| PR: https://pagure.io/koji/pull-request/1893

Previously database exception was propagated. Now, it is raising proper koji
exception.

Web UI Changes
--------------
**browsable api**

| PR: https://pagure.io/koji/pull-request/1821

``koji list-api`` output browsable via web.

**cluster health info page**

| PR: https://pagure.io/koji/pull-request/1551

New web page showing current usage of build cluster.

**fix closing table tag**

| PR: https://pagure.io/koji/pull-request/1839

Fixed corrupted table.

**Show build link(s) on buildContainer task page**

| PR: https://pagure.io/koji/pull-request/284

Workaround before we have a proper web plugin API

**human-friendly file sizes in taskinfo page**

| PR: https://pagure.io/koji/pull-request/1820

Builder Changes
---------------
**kojid: use binary msg for python3 in notification tasks**

| PR: https://pagure.io/koji/pull-request/1892

Fix encoding problems in notification

**split admin_emails option for kojid**

| PR: https://pagure.io/koji/pull-request/1246

Fix for multiple addresses in kojid error handler.

**Provide for passing credentials to SRPMfromSCM**

| PR: https://pagure.io/koji/pull-request/1640

Builder's conf can now contain ``scm_credentials_dir`` option, where can be
stored authentication certificates or other data for use inside the mock when
building SRPMs for fetching data from authenticated SCMs.

**Log kernel version used for buildroot**

| PR: https://pagure.io/koji/pull-request/821
| PR: https://pagure.io/koji/pull-request/1850

**use --update for dist-repos if possible**

| PR: https://pagure.io/koji/pull-request/1037

Improves speed of new distrepos.

**fix time type for restartHosts**

| PR: https://pagure.io/koji/pull-request/1826

**no notifications in case of deleted tag**

| PR: https://pagure.io/koji/pull-request/1380

In some cases (sidetags) tag can be deleted before untag notifications are sent,
so don't send them if tag is already deleted.

**add _remote.repositories to ignored maven files**

| PR: https://pagure.io/koji/pull-request/1732

Maven3 file type added to ignored.

**check existence of maven symlink**

| PR: https://pagure.io/koji/pull-request/1742

In recent Fedora's maven is alternatives symlink. Original check now failed even
if maven was installed.

System Changes
--------------
**QueryProcessor: fix countOnly for group sql**

| PR: https://pagure.io/koji/pull-request/1845

WebUI returned an error on Users tab after multiple kerberos realms per user
were introduced.

**limit distRepo tasks per tag**

| PR: https://pagure.io/koji/pull-request/1869
| PR: https://pagure.io/koji/pull-request/1912

Introduces ``distrepo.cancel_others`` extra flag for tags. If enabled, new
distRepo task will cancel previous non-finished ones leaving only new one.

**do not use with statement with requests.get**

| PR: https://pagure.io/koji/pull-request/1854

Older python-requests doesn't handle correctly ``with`` statement, so we've
avoided it for now.

**clean all unused `import` and reorder imports**

| PR: https://pagure.io/koji/pull-request/763

Making our code PEP-8 compliant.

**fix CGRefundBuild to release build properly**
| PR: https://pagure.io/koji/pull-request/1853

Fixes for refunding failed/cancelled build.

**gitignore: exclude .vscode folder**

| PR: https://pagure.io/koji/pull-request/1862

trivial change in `.gitignore`

**improve test and clean targets in Makefiles**

| PR: https://pagure.io/koji/pull-request/723

**remove old db constraint**

| PR: https://pagure.io/koji/pull-request/1790

**use BulkInsertProcessor for hub mass inserts**

| PR: https://pagure.io/koji/pull-request/1714
| PR: https://pagure.io/koji/pull-request/1847

Speed up mass inserts.

**rm old test code**

| PR: https://pagure.io/koji/pull-request/1798

Some files in the tree had bits of code that you could run if you executed the
files directly as scripts. Now that we have unit tests and the "fakehub" tool,
we do not need this code.

**hub: build for policy check should be build_id in host.tagBuild**

| PR: https://pagure.io/koji/pull-request/1797

**rpm: remove %defattr**

| PR: https://pagure.io/koji/pull-request/1800

RHEL 5 and later do not require %defattr.

**allow comma delimiter for allowed_methods**

| PR: https://pagure.io/koji/pull-request/1745

Example config says, that comma is allowed, but it was not true.

**hub: Fix issue with listing users and old versions of Postgres**

| PR: https://pagure.io/koji/pull-request/1751

**Fix hub reporting of bogus ownership data**

| PR: https://pagure.io/koji/pull-request/1753

**clean python compiled binaries for non *.py code**

| PR: https://pagure.io/koji/pull-request/1695

**allow tag or target permissions as appropriate (on master)**

| PR: https://pagure.io/koji/pull-request/1733

**More default values in example kojihub.conf**

| PR: https://pagure.io/koji/pull-request/1739

Utilities Changes
-----------------
**Add koji-gc/kojira/koji-shadow to setup.py**

| PR: https://pagure.io/koji/pull-request/1428

Koji utilities are now installlable from PyPi.

Garbage Collector
.................
**untagging/moving to trashcan is very slow**

| PR: https://pagure.io/koji/pull-request/1873

Rewrite of how koji-gc handles untagging. Multicalls are used now and some
speedup of related API calls is also included.

**human-readable timestamp in koji-gc log**

| PR: https://pagure.io/koji/pull-request/1691

**koji-gc: Fix up usage of default configuration file**

| PR: https://pagure.io/koji/pull-request/1769

Previously, koji-gc would fail if run without a configuration file
being specified on the command line.

**don't expect all buildReferences fields (koji-gc)**

| PR: https://pagure.io/koji/pull-request/1724

Bug fix

**koji-gc: fix typo in --ignore-tags**

| PR: https://pagure.io/koji/pull-request/1726

DB Sweeper
..........
**additional options to clean database**

| PR: https://pagure.io/koji/pull-request/1824

Last release introduced new tool ``koji-sweep-db`` which is used to clean the
database. Few new options were added now like cleaning scratch builds, CG
reservations, notification tasks or unused buildroots.

Note, that these new features are more technical preview. You need to use
``--force`` flag to run them for a good reason. They can a) take insane time to
finish b) remove data you never wanted to delete.  Always test these commands in
safe environment, before running them in production.

Cleaning sessions and reservations are still safe and they are primary goals of
the script.

**turn on autocommit to eliminate VACUUMing errors**

| PR: https://pagure.io/koji/pull-request/1771

**remove accuracy from koji-sweep-db timer**

| PR: https://pagure.io/koji/pull-request/1761

**fix typo in table column name**

| PR: https://pagure.io/koji/pull-request/1760

Kojikamid
.........
**A few fixes for kojikamid**

| PR: https://pagure.io/koji/pull-request/1837

kojikamid (the daemon that runs in VMs) needs a few updates to be consistent
with changes to the the Koji data model, and Python 3 compatibility.

Documentation Changes
---------------------
**reorder docs**

| PR: https://pagure.io/koji/pull-request/1716
| PR: https://pagure.io/koji/pull-request/1794

**docstrings for API**

| PR: https://pagure.io/koji/pull-request/1832
| PR: https://pagure.io/koji/pull-request/1868
| PR: https://pagure.io/koji/pull-request/1799

**document noarch rpmdiff behaviour**

| PR: https://pagure.io/koji/pull-request/1875

**MaxRequestsPerChild -> MaxConnectionsPerChild**

| PR: https://pagure.io/koji/pull-request/1804

**explain "compile/builder1" user principal**

| PR: https://pagure.io/koji/pull-request/1806

**recommend 2048 bit keys**

| PR: https://pagure.io/koji/pull-request/1805

**fix indent for reloading postgres settings**

| PR: https://pagure.io/koji/pull-request/1801

**simplify admin bootstrapping intro**

| PR: https://pagure.io/koji/pull-request/1802

**fix rST syntax for DB listening section**

| PR: https://pagure.io/koji/pull-request/1803

**docs for partitioning buildroot_listings**

| PR: https://pagure.io/koji/pull-request/1823

**document tag inheritance**

| PR: https://pagure.io/koji/pull-request/1817

**clarify --ts usage**

| PR: https://pagure.io/koji/pull-request/1775

**Update typeinfo metadata documentation**

| PR: https://pagure.io/koji/pull-request/1917

** add "--new" option in "grant-permission" help summary

| PR: https://pagure.io/koji/pull-request/1918
| PR: https://pagure.io/koji/pull-request/1921
