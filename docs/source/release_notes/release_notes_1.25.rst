Koji 1.25.0 Release notes
=========================

All changes can be found at `pagure <https://pagure.io/koji/roadmap/1.25/>`_.
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
| PR: https://pagure.io/koji/pull-request/2702
| PR: https://pagure.io/koji/pull-request/2703
| PR: https://pagure.io/koji/pull-request/2761
| PR: https://pagure.io/koji/pull-request/2769
| PR: https://pagure.io/koji/pull-request/2770
| PR: https://pagure.io/koji/pull-request/2733
| PR: https://pagure.io/koji/pull-request/2803
| PR: https://pagure.io/koji/pull-request/2694
| PR: https://pagure.io/koji/pull-request/2709
| PR: https://pagure.io/koji/pull-request/2829
| PR: https://pagure.io/koji/pull-request/2738
| PR: https://pagure.io/koji/pull-request/2790
| PR: https://pagure.io/koji/pull-request/2792
| PR: https://pagure.io/koji/pull-request/2727
| PR: https://pagure.io/koji/pull-request/2773

We've revised many calls which previously returned empty results to raise more
meaningful errors. Typically ``koji list-untagged xyz`` returned same result if
package never existed and also in case when package was really never untagged.
Also all warning and error messages were unified in their wording.

**Show connection exception for anynymous calls**

| PR: https://pagure.io/koji/pull-request/2705

Calls which don't need authentication were not properly propagating
connection-related exceptions with ``--debug``.

**list-api option for one method**

| PR: https://pagure.io/koji/pull-request/2688

Now you don't need to scroll through ``list-api`` output if you want single
method signature. ``koji list-api listBuilds`` show just one.

**Add wait/nowait to all calls**

| PR: https://pagure.io/koji/pull-request/2831

Some commands had ``--wait`` and/or ``--nowait`` options. We've made it
consistent, so all eligible commands now contain both variants. If option is
specified it is the ultimate override. If none of these is specified, behaviour
differs if client is running on TTY (then it waits) or on background (then it
will not wait). This is no new behaviour, just adding explicit options in cases
where they were not present.

**Use multicall for cancel, list-hosts and write-signed-rpm commands**

| PR: https://pagure.io/koji/pull-request/2722
| PR: https://pagure.io/koji/pull-request/2808
| PR: https://pagure.io/koji/pull-request/2810

Making cancel command much faster if you're cancelling many tasks/builds,
listing many hosts or writing multiple rpm signed copies.

**--no-auth for 'call' command**

| PR: https://pagure.io/koji/pull-request/2734

``call`` command was authenticating for any method. Now you can specify this
option to skip authentication phase.

**Support modules and other btypes in download-build**

| PR: https://pagure.io/koji/pull-request/2678

``download-build`` now downloads all regular archives. Previusly it was limited
to subset of file types.


Library Changes
---------------
**Better failed authentication/connections**

PR#2735: lib: more verbose conn AuthError for ssl/gssapi
PR#2824: lib: is_conn_error catch more exceptions
PR#2794: lib: set sinfo=None for failed ssl_login
PR#2723: better ssl_login() error message when cert is None
PR#2826: Add kerberos debug message

All connection errors now should provide a bit more information for debugging.
Some errors were masked by more generic ones. We're now trying to display more
info about these. Same for debugging krbV/GSSAPI errors. Also added a `doc
(https://docs.pagure.org/koji/content_generator_metadata/)`_ page (and link to
CLI) for typical GSSAPI errors.

**More portable BadStatusLine checking**

| PR: https://pagure.io/koji/pull-request/2819

Python 3 versions had some problems with detecting `keepalive race
(https://github.com/mikem23/keepalive-race)`_ conditions on apache side. We've
made code a bit more portable so you shouldn't see these errors now.

**Missing default values in read_config**

| PR: https://pagure.io/koji/pull-request/2689

Some default values were missing in the config parsing which could have led to
mysterious behaviour (everything related to retry logic in case there is some
connection error)

**lib: use parse_task_params for taskLabel**

| PR: https://pagure.io/koji/pull-request/2771

It is internal only change, but could be used as a promotion place for
developers. Anywhere where you've parsed task options ad hoc (e.g. in your
plugin or in some scripts) you can use ``parse_task_params`` function which
should do this more consistently.

API Changes
-----------
**Fail early on wrong info in create*Build methods**

PR#2721: API: createWinBuild with wrong win/build info
PR#2732: api: createImageBuild non-existing build wrong buildinfo
PR#2736: api: createMavenBuild wrong buildinfo/maveninfo

``createWinBuild``, ``createImageBuild``, ``createMavenBuild`` now will raise an
exception when some data in buildinfo are missing. Exception should be more
senseful than before.

**getVolume with strict option**

| PR: https://pagure.io/koji/pull-request/2796

New option to be in line with other calls. You can check either ``None`` return
or use ``strict=True`` and wrap it in ``try/except``.

**getLastHostUpdate ts option**

| PR: https://pagure.io/koji/pull-request/2766

Historically we've passed aroung dates as text strings. Almost everywhere we're
now also sending GMT timestamps to better handle timezone problems. This new
option in the ``getLastHostUpdate`` call allows you to get timestamp instead of
default date.

**Be tolerant with duplicate parents in _writeInheritanceData**

| PR: https://pagure.io/koji/pull-request/2782

Regression fix - call will now not raise an exception if there are duplicated
parents in inheritance chain.

**with_owners options for readPackageList and listPackages**

| PR: https://pagure.io/koji/pull-request/2791

Performance improvement. Most of the calls to these functions don't need
information about the package owner. Dropping this data simplifies underlying
query to faster one. If you're using this call in your automation give it a
chance to lower your database load.

System Changes
--------------
**Task priority policy**

| PR: https://pagure.io/koji/pull-request/2711

There is a new ``priority`` policy which can be used to alter task priorities
based on data about task/build. See documentation for details.

**Python egginfo**

| PR: https://pagure.io/koji/pull-request/2821

After years of struggling with pip/setuptools/rpm packaging we should finally
have something compatible. So, now egginfo, etc. should  be properly installed
and usable in virtualenvs.

**Task ID for repos**

| PR: https://pagure.io/koji/pull-request/2802
| PR: https://pagure.io/koji/pull-request/2823

When debugging buildroot content issues it is often important to find out which
repo was used and when it was created, investigate createrepo and mergerepo
logs, etc. It was not easiest to find corresponding task to given repodata.
We've added this information to database (so you can see it in web and CLI) and
also to ``repo.json`` file in repodata directory.

**Add squashfs-only and compress-arg options to livemedia**

| PR: https://pagure.io/koji/pull-request/2833

Livemedia tasks can now use these options for passing to ImageFactory.

Web
---
**Show VCS and DistURL tags as links when appropriate**

| PR: https://pagure.io/koji/pull-request/2756

**Don't use count(*) on first tasks page**

| PR: https://pagure.io/koji/pull-request/2827

Tasks list page was quite slow in many cases. Reason was pagination and
underlying ``count(*)`` for given filter. As PostgreSQL is very slow for this
type of query we've removed number of total results and listing of all pages on
first page which is loaded most often. If you use link to next page you'll see
everything as before this change.

**Additional info on API page**

| PR: https://pagure.io/koji/pull-request/2828

We've added simple client code to API page, so users can start with something
and don't need to dig through the rest of documentation.


Plugins
-------
**Configurable sidetags suffixes**

| PR: https://pagure.io/koji/pull-request/2730

Sidetag plugin now allows to define set of allowed suffixed which can be used
when creating the sidetag. You can distunguish between diffent types (private,
gating, ...)

**Protonmsg: fixes for persistent queue**

| PR: https://pagure.io/koji/pull-request/2844

Persistent message storage was broken. Now it should work correctly.


Utilities
---------

Kojira
......
**Faster startup**

| PR: https://pagure.io/koji/pull-request/2764

Multicall is used to prefetch tag data from hub. It significantly improves
startup time for bigger installations.

**Check repo.json before deleting**

| PR: https://pagure.io/koji/pull-request/2765

Previusly kojira refused to delete repositories which used different name than
actual tag. It could have happened when tag was renamed from some reason. Now we
consult also ``repo.json`` which limits this insecurity and allows kojira to
delete more directories.

**Tolerate floats in metadata timestamps**

| PR: https://pagure.io/koji/pull-request/2784

External repositories sometimes can use float timestamp. We now correctly parse
that.

Garbage Collector
.................
**Allow specifying all CLI options in config**

| PR: https://pagure.io/koji/pull-request/2816

Everything what can be specified on command-line can now be also put into the
configuration file.

**Implement hastag policy for koji-gc**

| PR: https://pagure.io/koji/pull-request/2817

There was no way to mark some builds which shouldn't be deleted from tag. Now
you can tag it with some additional special 'dont-delete-me' tag and make
``hastag`` policy for that.

Documentation
-------------
**Updated docs and devtools**

| PR: https://pagure.io/koji/pull-request/2724
| PR: https://pagure.io/koji/pull-request/2725
| PR: https://pagure.io/koji/pull-request/2772
| PR: https://pagure.io/koji/pull-request/2843
| PR: https://pagure.io/koji/pull-request/2799
