Koji 1.25.0 Release notes
=========================

All changes can be found in `the roadmap <https://pagure.io/koji/roadmap/1.25/>`_.
Most important changes are listed here.


Migrating from Koji 1.24/1.24.1
-------------------------------

For details on migrating see :doc:`../migrations/migrating_to_1.25`


Security Fixes
--------------

None


Client Changes
--------------
**More verbose error/warning messages**

| PR: https://pagure.io/koji/pull-request/2615
| PR: https://pagure.io/koji/pull-request/2694
| PR: https://pagure.io/koji/pull-request/2702
| PR: https://pagure.io/koji/pull-request/2703
| PR: https://pagure.io/koji/pull-request/2709
| PR: https://pagure.io/koji/pull-request/2727
| PR: https://pagure.io/koji/pull-request/2733
| PR: https://pagure.io/koji/pull-request/2738
| PR: https://pagure.io/koji/pull-request/2761
| PR: https://pagure.io/koji/pull-request/2769
| PR: https://pagure.io/koji/pull-request/2770
| PR: https://pagure.io/koji/pull-request/2773
| PR: https://pagure.io/koji/pull-request/2790
| PR: https://pagure.io/koji/pull-request/2792
| PR: https://pagure.io/koji/pull-request/2803
| PR: https://pagure.io/koji/pull-request/2829
| PR: https://pagure.io/koji/pull-request/2850

We've revised many calls which previously returned empty results to raise more
meaningful errors. For example, ``koji list-untagged package_x`` previously did
not distinguish between the case where ``package_x`` had no untagged builds
and the case where ``package_x`` did not exist.
Also, all warning and error messages were unified in their wording.

**Show connection exception for anonymous calls**

| PR: https://pagure.io/koji/pull-request/2705

Calls which don't need authentication were not properly propagating
connection-related exceptions with ``--debug``.

**list-api option for one method**

| PR: https://pagure.io/koji/pull-request/2688

Now you don't need to scroll through ``list-api`` output if you want a single
method signature. The ``koji list-api listBuilds`` command will show just one.

**Add wait/nowait to all calls**

| PR: https://pagure.io/koji/pull-request/2831

Some commands had ``--wait`` and/or ``--nowait`` options. We've made it
consistent, so all eligible commands now contain both variants.
These options override waiting behavior for the command.

If neither option is specified, the default depends on the runtime context.
If the client is running on a TTY, then it defaults to waiting.
If it is running in the background, then it defaults to not waiting.

This is not new behaviour, just adding explicit options in cases
where they were not present.

**Use multicall for cancel, list-hosts and write-signed-rpm commands**

| PR: https://pagure.io/koji/pull-request/2722
| PR: https://pagure.io/koji/pull-request/2808
| PR: https://pagure.io/koji/pull-request/2810

These commands are now much faster when acting on multiple items.

**Using 'call' command without authentication**

| PR: https://pagure.io/koji/pull-request/2734

The ``call`` command authenticates by default, which is not always desired.
This authentication can be disabled with the the global ``--noauth`` option.
The help text now clarifies this.

**Support modules and other btypes in download-build**

| PR: https://pagure.io/koji/pull-request/2678

The ``download-build`` command now downloads all regular archives. Previously it
was limited to a subset of file types.


Library Changes
---------------
**Better failed authentication/connections**

| PR: https://pagure.io/koji/pull-request/2723
| PR: https://pagure.io/koji/pull-request/2735
| PR: https://pagure.io/koji/pull-request/2794
| PR: https://pagure.io/koji/pull-request/2824
| PR: https://pagure.io/koji/pull-request/2826

Connection errors now provide a bit more information for debugging.
Some errors were masked by more generic ones. We're now trying to display more
information about these, and to help with debugging krbV/GSSAPI errors. We have
added a :doc:`documentation page <../kerberos_gssapi_debug>` for common GSSAPI
errors, which the CLI now refers to.

**More portable BadStatusLine checking**

| PR: https://pagure.io/koji/pull-request/2819

Python 3 versions had some problems detecting expired keepalive connections.
We've made the code a bit more portable so you shouldn't see these errors now.

**Missing default values in read_config**

| PR: https://pagure.io/koji/pull-request/2689

Some default values were missing in the config parsing which could have led to
mysterious behaviour. The configuration values in question were related to
retry behavior when making calls to the hub.

**Use parse_task_params for taskLabel**

| PR: https://pagure.io/koji/pull-request/2771

The ``taskLabel`` function (used in various places to generate a short label
for a given task) has been updated to use the newer ``parse_task_params``
function instead of parsing the parameters itself.
As a result, the function is simpler and more accurate.

The ``parse_task_params`` function is currently the preferred way to interpret
task parameters. We recommend that developers use it rather than ad-hoc code.

API Changes
-----------
**Fail early on wrong info in create*Build methods**

| PR: https://pagure.io/koji/pull-request/2721
| PR: https://pagure.io/koji/pull-request/2732
| PR: https://pagure.io/koji/pull-request/2736

The ``createWinBuild``, ``createImageBuild``, and ``createMavenBuild`` hub
calls will now raise an exception when some data in buildinfo are missing,
and their exception text should be clearer than before.

**getVolume with strict option**

| PR: https://pagure.io/koji/pull-request/2796

This new option brings ``getVolume`` in line with other similar calls.
When the requested volume does not exist, the call will either return ``None``
(when ``strict=False``, the default) or raise an exception (when
``strict=True``).

**getLastHostUpdate ts option**

| PR: https://pagure.io/koji/pull-request/2766

Historically we've passed around dates as text strings. Almost everywhere we're
now also sending GMT timestamps to better handle timezone problems. This new
option in the ``getLastHostUpdate`` call allows you to get a timestamp instead
of a string value.

**Be tolerant with duplicate parents in _writeInheritanceData**

| PR: https://pagure.io/koji/pull-request/2782

Regression fix - call will now not raise an exception if there are duplicated
parents in inheritance chain.

**with_owners options for readPackageList and listPackages**

| PR: https://pagure.io/koji/pull-request/2791

Performance improvement. Most of the calls to these functions don't need
information about the package owner. Dropping this data simplifies the
underlying query to a faster one. If you're using this call in your automation
give it a chance to lower your database load.

System Changes
--------------
**Task priority policy**

| PR: https://pagure.io/koji/pull-request/2711

There is a new ``priority`` policy which can be used to alter task priorities
based on data about task/build.
See :doc:`../defining_hub_policies` for details.

**Python egginfo**

| PR: https://pagure.io/koji/pull-request/2821

After years of struggling with pip/setuptools/rpm packaging we should finally
have something compatible. So, now egginfo, etc. should be properly installed
and usable in virtualenvs.

**Task ID for repos**

| PR: https://pagure.io/koji/pull-request/2802
| PR: https://pagure.io/koji/pull-request/2823

When debugging buildroot content issues it is often important to find out which
repo was used and when it was created, investigate createrepo and mergerepo
logs, etc. It was not easy to find the task that created a given repo.
This information is now tracked in the database, and reported in the web and CLI
interfaces.
It is also recorded in the ``repo.json`` file for the repo.

**Add squashfs-only and compress-arg options to livemedia**

| PR: https://pagure.io/koji/pull-request/2833

Livemedia tasks can now use these options for passing to ImageFactory.

Web
---
**Show VCS and DistURL tags as links when appropriate**

| PR: https://pagure.io/koji/pull-request/2756

Previously these values were shown as plain text in the web interface.
Now they should appears as links.

**Don't use count(*) on first tasks page**

| PR: https://pagure.io/koji/pull-request/2827

The tasks list page can be quite slow in many cases.
The primary cause of this is pagination and the underlying ``count(*)``
query.
As PostgreSQL is very slow for this type of query we've removed the page count
for the first page which is loaded most often.
Subsequent pages will continue to show the count (and therefore also the
performance penalty in some situations).

**Additional info on API page**

| PR: https://pagure.io/koji/pull-request/2828

We've added some simple example client code to the API page, to help users get
started without having to dig through the rest of the documentation.


Plugins
-------
**Configurable sidetags suffixes**

| PR: https://pagure.io/koji/pull-request/2730

The sidetag plugin now allows defining a set of allowed suffixes which can be used
when creating the sidetag. You can distinguish between different types (private,
gating, ...)

**Protonmsg: fixes for persistent queue**

| PR: https://pagure.io/koji/pull-request/2844

The persistent message queue option (see :ref:`protonmsg-config`) was
broken. Now it should work correctly.


Utilities
---------

Kojira
......
**Faster startup**

| PR: https://pagure.io/koji/pull-request/2764

Multicall is used to prefetch tag data from hub. It significantly improves
startup time for larger installations.

**Check repo.json before deleting**

| PR: https://pagure.io/koji/pull-request/2765

Previously kojira refused to delete repositories if the path did not match
the name of the tag the repo was based on.
This kept kojira from cleaning up repos after a build tag was renamed.
Now kojira also consults the ``repo.json`` which records the name of the tag
at the time the repo was created.

**Tolerate floats in metadata timestamps**

| PR: https://pagure.io/koji/pull-request/2784

External repositories sometimes can use float timestamp. We now correctly parse
that.

**Fix fork-related issues**

| PR: https://pagure.io/koji/pull-request/2853
| PR: https://pagure.io/koji/pull-request/2855
| PR: https://pagure.io/koji/pull-request/2856

Forking while deleting is causing some issues (mostly with loggign module)
especially with the latest python.  These can result in kojira not deleting
repos at all.

Garbage Collector
.................
**Allow specifying all CLI options in config**

| PR: https://pagure.io/koji/pull-request/2816

Every option that can be specified on the command line can now be also put into
the configuration file.

**Implement hastag policy for koji-gc**

| PR: https://pagure.io/koji/pull-request/2817

The gc policy now offers a ``hastag`` test for builds, similar to the test
offered by hub policies.

This can be used in numerous ways.
One example (a ``protected`` tag that protects builds from pruning) is
described in the `original request <https://pagure.io/koji/issue/2813>`_.

Documentation
-------------
**Updated docs and devtools**

| PR: https://pagure.io/koji/pull-request/2724
| PR: https://pagure.io/koji/pull-request/2725
| PR: https://pagure.io/koji/pull-request/2772
| PR: https://pagure.io/koji/pull-request/2799
| PR: https://pagure.io/koji/pull-request/2843

Numerous small updates.
