Koji 1.27.1 Release notes
=========================

All changes can be found in `the roadmap <https://pagure.io/koji/roadmap/1.27.1/>`_.
Most important changes are listed here.

Migrating from Koji 1.27
------------------------

No special actions are needed.


Security Fixes
--------------

None

Client Changes
--------------
**Return mistakenly dropped option (--keytab)**

| PR: https://pagure.io/koji/pull-request/3172

In 1.27.0 improper merge led to this missing option.

**Use error function instead of print with sys.exit in CLI commands**

| PR: https://pagure.io/koji/pull-request/3113

Internal-only change unifying handling of CLI exit.

Hub Changes
-----------
**Don't fail on missing buildroot tag in policies**

| PR: https://pagure.io/koji/pull-request/3186

buildtag and buildtag_inherits_from will fail in case build doesn't have it.
Such situation can easily happen with content generators.

**Only raise error when authtype is not proxyauthtype**

| PR: https://pagure.io/koji/pull-request/3164

Backward compatibility for new proxyauthtype option.

**Handle dictionary parameter in get_tag()**

| PR: https://pagure.io/koji/pull-request/3118

Unification of internal handling of get_tag/getTag parameters.

Kojira
------
**Don't fail on deleted items**

| PR: https://pagure.io/koji/pull-request/3166

In case that tag was deleted during last run unnecessary error was raised as
relict of py2->py3 conversion.

Web Changes
-----------

**Style channelinfo hosts table**

| PR: https://pagure.io/koji/pull-request/3139

Default CSS was not handling this page well.

Documentation/DevTools Changes
------------------------------

 * `buildtag_inherits_from docs <https://pagure.io/koji/pull-request/3189>`_
 * `Make setup.py executable <https://pagure.io/koji/pull-request/3104>`_
 * `Add unit test for get_options <https://pagure.io/koji/pull-request/3180>`_
 * `Add all options to hub_conf.rst <https://pagure.io/koji/pull-request/3098>`_
 * `Document getBuildLogs method <https://pagure.io/koji/pull-request/3174>`_
 * `Pytest instead of nose in unittest <https://pagure.io/koji/pull-request/3157>`_
 * `Fix spelling in comments for archive handling <https://pagure.io/koji/pull-request/3161>`_
 * `Add and update CLI unit tests <https://pagure.io/koji/pull-request/3115>`_
 * `Print fakeweb listening URL <https://pagure.io/koji/pull-request/3142>`_
 * `Improve protonmsg SSL parameter descriptions <https://pagure.io/koji/pull-request/3138>`_
 * `Rewrite Acceptable keys to Requested keys in missing_signatures log <https://pagure.io/koji/pull-request/3150>`_
