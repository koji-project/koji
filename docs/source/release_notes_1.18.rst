Koji 1.18.0 Release notes
=========================


Migrating from Koji 1.17
------------------------

For details on migrating see :doc:`migrating_to_1.18`



Security Fixes
--------------



Client Changes
--------------

**cli: add option for custom cert location**

| PR: https://pagure.io/koji/pull-request/1253

The CLI no has an option for setting a custom SSL certificate, similar to the
options for Kerberos authentication.


**cli: load plugins from ~/.koji/plugins**

| PR: https://pagure.io/koji/pull-request/892


This change allows users to load their own cli plugins from ``~/.koji/plugins``
or from another location by using the ``plugin_paths`` setting.



Library Changes
---------------


Web UI Changes
--------------



Builder Changes
---------------

**use RawConfigParser for kojid**

| PR: https://pagure.io/koji/pull-request/1544

The use of percent signs is common in ``kojid.conf`` because of the
``host_principal_format`` setting.
This causes an error in python3 if ``SafeConfigParser`` is used, so we use
``RawConfigParser`` instead.


**handle bare merge mode**

| PR: https://pagure.io/koji/pull-request/1411
| PR: https://pagure.io/koji/pull-request/1516
| PR: https://pagure.io/koji/pull-request/1502


This feature adds a new merge mode for external repos named ``bare``.
This mode is intended for use with modularity.




System Changes
--------------



**API for reserving NVRs for content generators**

| PR: https://pagure.io/koji/pull-request/1464

Fixes: https://pagure.io/koji/issue/1463

..
    https://pagure.io/koji/issue/1463
    [RFE] Predeclare nvr for content generators

This feature allows content generators to reserve NVRs earlier in the build
process similar to builds performed by ``kojid``. The NVR is reserved by
calling ``CGInitBuild()`` and finalized by the ``CGImport()`` call.



**Add support for tag/target macros for Mageia**

| PR: https://pagure.io/koji/pull-request/898

This feature allows setting rpm macros via the tag extra field. These macros
will be added to the mock configuration for the buildroot. The system
looks for extra values of the form ``rpm.macro.NAME``.

For example, to set the dist tag for a given tag, you could use a command like:

::

    $ koji edit-tag f30-build -x rpm.macro.dist=MYDISTTAG



**set module_hotfixes=1 in yum.conf via tag config**

| PR: https://pagure.io/koji/pull-request/1524

Koji now handles the field ``mock.yum.module_hotfixes`` in the tag extra.
When set, kojid will set ``module_hotfixes=0/1`` in the yum portion of the
mock configuration for a buildroot.


**Allow users to opt out of notifications**

| PR: https://pagure.io/koji/pull-request/1417

This feature lets users opt out of notifications that they would otherwise
automatically recieve, such as build and tag notifications for:

- the build owner (the user who submitted the build)
- the package owner within the given tag

These opt-outs are user controlled and can be managed with the new
``block-notification`` and ``unblock-notificiation`` commands.



**Allow hub policy to match version and release**

| PR: https://pagure.io/koji/pull-request/1513


This feature adds new policy tests to match ``version`` and ``release``.
This tests are glob pattern matches.


**Rebuild SPMS before building**

| PR: https://pagure.io/koji/pull-request/1462

For rpm builds from an uploaded srpm, Koji will now rebuild the srpm in the
build environment first.
This ensures that the NVR is correct for the resulting build.

The old behavior can be requested by setting ``rebuild_srpm=False`` in the tag
extra data for the build tag in question.




**remove merge option from edit-external-repo**

| PR: https://pagure.io/koji/pull-request/1499

This option was mistakenly added to the command and never did anything.
It is gone now.


**New multicall interface**

| PR: https://pagure.io/koji/pull-request/957

This feature implements a new and much better way to use multicall in the Koji
library.
These changes create a new implementation outside of ClientSession.
The old way will still work.

With this new implementation:

* a multicall is tracked as an instance of `MultiCallSession`
* the original session is unaffected
* multiple multicalls can be managed in parallel, if desired
* `MultiCallSession` behaves more or less like a session in multicall mode
* method calls return a `VirtualCall` instance that can later be used to access the result
* `MultiCallSession` can be used as a context manager, ensuring that the calls are executed

Usage examples are availble in the :doc:`Writing Koji Code <writing_koji_code>`
document.




**New 'buildtype' test for policies**

| PR: https://pagure.io/koji/pull-request/1415


Koji added btypes in version 1.11 along with content generators.
Now, all builds have one or more btypes.

This change allows policies to check the btype value using the ``buildtype`` test.



**retain old search pattern in web ui**

| PR: https://pagure.io/koji/pull-request/1258

The search results page of the web ui now retains a search form with the
current search pre-filled.
This makes it easier for users to refine their searches.





**introduce host-admin permission + docs**

| PR: https://pagure.io/koji/pull-request/1454


I'm filing this as first of series to splitting admin permission to more granular ones. Adding some docs about permission system and `host`, `tag` and `target` permissions.



**createrepo_c is used by default now**

| PR: https://pagure.io/koji/pull-request/1278

Fixes: https://pagure.io/koji/issue/716

..
    https://pagure.io/koji/issue/716
    /usr/libexec/kojid/mergerepos ignores xml:base in location

If you add an external repo to a build tag, and the external repo uses the same xml:base trickery that Koji itself uses (that is, if the external repo you are pointing it is produced by another Koji instance for a tag which itself has an external repo configure), the xml:base attribute is lost by /usr/libexec/kojid/mergerepos and the resulting merged repodata ends up with incorrect URLs.

To give a hypothetical example, imagine your Koji is producing a repo from a build tag at:

http://thirdpartykoji.example.com/kojifiles/repos/beaker-harness-rhel-8-build/latest/x86_64/repodata/

It uses an external repo to pull packages from another Koji instance at:

http://download.bigcorp.com/brewroot/repos/rhel-8.0-build/latest/x86_64/repodata/

But that repo itself is pulling packages from an external repo:

https://kojipkgs.fedoraproject.org/repos/module-bootstrap-rawhide/latest/x86_64/repodata/

The download.bigcorp.com repodata will refer to the remote packages using xml:base, like this:

    <location xml:base="https://kojipkgs.fedoraproject.org/repos/module-bootstrap-rawhide/latest/x86_64/toplink/packages/audit/2.7.7/5.fc27/x86_64" href="audit-libs-2.7.7-5.fc27.x86_64.rpm"/>

Everything is fine so far. But now, when mergerepos runs on thirdpartykoji.example.com, I expect it to preserve the same <location/> so that the packages can be correctly downloaded no matter how many layers of external repos are involved. However mergerepos on thirdpartykoji.example.com instead produces this:

    <location xml:base="http://download.bigcorp.com/brewroot/repos/rhel-8.0-build/latest/x86_64" href="audit-libs-2.7.7-5.fc27.x86_64.rpm"/>

which fails to download because the package is not there. The original value of xml:base has been lost.

The end result is build failures with errors like this in mock_output.log as yum/dnf tries to download the packages from the wrong URL:

    http://download.bigcorp.com/brewroot/repos/rhel-8.0-build/latest/i386/audit-libs-2.7.7-5.fc27.i686.rpm: [Errno 14] HTTP Error 404 - Not Found
    Trying other mirror.



**show load/capacity in list-channels**

| PR: https://pagure.io/koji/pull-request/1449

Fixes: https://pagure.io/koji/issue/1448

..
    https://pagure.io/koji/issue/1448
    [RFE] show channel load/capacity in list-channels

list-channels can show overall number for load/capacity



**Allow taginfo cli to use tag IDs; fixed Inheritance printing bug**

| PR: https://pagure.io/koji/pull-request/1476

It would be useful to be able to use the koji cli's taginfo with tag IDs and not just the tag name since the python library allows for this.  Also there is a bug where Inheritance always uses the value of the last tag queried for.

Old behavior (ID bug):
```
❯❯❯ koji taginfo 6438
No such tag: 6438
```

Old behavior (Inheritance bug):
```
❯❯❯ koji taginfo rawhide f31 
Tag: rawhide [197]
Arches: aarch64 armv7hl i686 ppc64 ppc64le s390x x86_64
Groups: appliance-build, build, livecd-build, livemedia-build, srpm-build
LOCKED
Tag options:
Inheritance:
                                      <<<<< inheritance missing/incorrect

Tag: f31 [6438]
Arches: None
Groups: appliance-build, build, livecd-build, livemedia-build, srpm-build
Required permission: 'autosign'
Tag options:
  mock.new_chroot : 0
  mock.package_manager : 'dnf'
Inheritance:

```
New behavior:
```
❯❯❯ koji taginfo rawhide 6438        
Tag: rawhide [197]
Arches: aarch64 armv7hl i686 ppc64 ppc64le s390x x86_64
Groups: appliance-build, build, livecd-build, livemedia-build, srpm-build
LOCKED
Tag options:
Inheritance:
  0    .... f31 [6438]

Tag: f31 [6438]
Arches: None
Groups: appliance-build, build, livecd-build, livemedia-build, srpm-build
Required permission: 'autosign'
Tag options:
  mock.new_chroot : 0
  mock.package_manager : 'dnf'
Inheritance:
```

..
    https://pagure.io/koji/issue/1485
    taginfo shows wrong inheritance when multiple tags given

When multiple tags are requested, the inheritance data for the final tag is shown for all tags.

```
$ koji taginfo f31 f28-build
Tag: f31 [6438]
Arches: None
Groups: appliance-build, build, livecd-build, livemedia-build, srpm-build
Required permission: 'autosign'
Tag options:
  mock.new_chroot : 0
  mock.package_manager : 'dnf'
Inheritance:
  0    .... f28-override [1922]

Tag: f28-build [1928]
Arches: armv7hl i686 x86_64 aarch64 ppc64 ppc64le s390x
Groups: appliance-build, build, livecd-build, livemedia-build, srpm-build
Tag options:
Inheritance:
  0    .... f28-override [1922]
```

Here we see `f28`'s inheritance for both tags (in reality, `f31` has no inheritance).






**deprecate BuildRoot.uploadDir method**

| PR: https://pagure.io/koji/pull-request/1456

Fixes: https://pagure.io/koji/issue/839

..
    https://pagure.io/koji/issue/839
    deprecate BuildRoot.uploadDir()

Noticed while working on a patch that this method is not used



**check existence of tag_id in getInheritanceData**

| PR: https://pagure.io/koji/pull-request/1461

Fixes: https://pagure.io/koji/issue/1460

..
    https://pagure.io/koji/issue/1460
    getInheritanceData API call should raise GenericError exception for non existing tag ID

*Steps to Reproduce:*
Run a getInheritanceData(non_exist_tag_ID)

*Actual result:*

[]

*Expected result:*

GenericError exception should be raised






**Allow generating separate src repo for build repos**

| PR: https://pagure.io/koji/pull-request/1273

Fixes #1266

Currently Koji has an option that can be used to include source rpms in each of generated arch repos. Howewer it makes repositories significantly bigger and slower to generate. Source metadata is duplicated across all arch repos. Increased metadata size makes builds slower.

This pull request takes a slightly different approach - it makes it possible to generate build repos with source rpms in separate repos. Such repos don't change size of each arch repo and can be generated faster - generation is done in a separate createrepo task that can run on separate host. For example:

    newRepo
      ├  createrepo (src)
      ├  createrepo (aarch64)
      ├  createrepo (ppc64le)
      └  createrepo (x86_64)

CC @ignatenkobrain

..
    https://pagure.io/koji/issue/1266
    RFE: --with-separate-src for build-repos

In Fedora we want to have src in build repos, but in separate repo so the size of metadata for builds won't grow.





**add strict option to getTaskChildren**

| PR: https://pagure.io/koji/pull-request/1256

+ moving to QueryProcessor of used calls

..
    https://pagure.io/koji/issue/1199
    API Call getTaskChildren call should return GenericError for non existing taskID

*Steps to Reproduce:*

Run getTaskChildren(non_existing_id)

*Actual result:*

[]

*Expected result:*

Should be returning an error message that task id does not exist.


I suggest add a strict option for the getTaskChildren API call.



**fail runroot task on non-existing tag**

| PR: https://pagure.io/koji/pull-request/1257

Fixes: https://pagure.io/koji/issue/1139

..
    https://pagure.io/koji/issue/1139
    runroot API call should raise GenericError exception for non existing tag

*Steps to Reproduce:*

tag = 'non-existing-tag'
arch 'x86_64'
Run runroot(tag, arch, ['echo', 'hello', 'world'], )

*Actual result:*

API call doesn't return some message
Web interface returns this after the click to runroot task:

Error
An error has occurred while processing your request.
IndexError: list index out of range
Full tracebacks disabled

*Expected result:*

Should be returning an error message that tag is not existing and on web interface should be normal task info with the failed state.
[![Screenshot_from_2018-10-31_09-50-46.png](/koji/issue/raw/files/b1dde9720c1fac719c568be125886ae087ec391a9911ed2e30fc3c228d7c452d-Screenshot_from_2018-10-31_09-50-46.png)](/koji/issue/raw/files/b1dde9720c1fac719c568be125886ae087ec391a9911ed2e30fc3c228d7c452d-Screenshot_from_2018-10-31_09-50-46.png)




**check architecture names for mistakes**

| PR: https://pagure.io/koji/pull-request/1272

Fixes: https://pagure.io/koji/issue/1237

..
    https://pagure.io/koji/issue/1237
    Architectures field in build target uses 2 different separators

Koji returns inconsistent data for architectures from build target, because both space and comma separators are allowed. 

Could be possible to unify separators to space character only (at least in API responses)?

Ideally it would be great to get same order of the architectures no matter in which order they have been provided (e.g. sort them alphabetically).




**volume option for dist-repo**

| PR: https://pagure.io/koji/pull-request/1327

When the rpms live on a different volume, it's very inefficient to generate a dist repo on the main volume (because rpms will have to be copied instead of linked). This change allows the user to specify the volume for the repo.

Fixes: #1366

..
    https://pagure.io/koji/issue/1366
    volume option for dist-repo

mikem: When the rpms live on a different volume, it's very inefficient to generate a dist repo on the main volume (because rpms will have to be copied instead of linked). This change allows the user to specify the volume for the repo.

PR #1327



**delete_build: handle results of lazy build_references call**

| PR: https://pagure.io/koji/pull-request/1442

Fixes: https://pagure.io/koji/issue/1441

..
    https://pagure.io/koji/issue/1441
    delete_build does not handle results of lazy build_references call

The build references check was recently adjusted to be lazy, but delete_build errors when fields are missing in the return. E.g.

```
WARNING:koji.xmlrpc:Traceback (most recent call last):
  File "/usr/share/koji-hub/kojixmlrpc.py", line 228, in _wrap_handler
    response = handler(environ)
  File "/usr/share/koji-hub/kojixmlrpc.py", line 271, in handle_rpc
    return self._dispatch(method, params)
  File "/usr/share/koji-hub/kojixmlrpc.py", line 308, in _dispatch
    ret = koji.util.call_with_argcheck(func, params, opts)
  File "/usr/lib/python2.7/site-packages/koji/util.py", line 216, in call_with_argcheck
    return func(*args, **kwargs)
  File "/usr/share/koji-hub/kojihub.py", line 7215, in delete_build
    if refs['archives']:
KeyError: 'archives'
```



**add --show-channels listing to list-hosts**

| PR: https://pagure.io/koji/pull-request/1425

Fixes: https://pagure.io/koji/issue/1424

..
    https://pagure.io/koji/issue/1424
    Add channels to list-hosts

Add new option --show-channels for optional list of all channels host is subscribed to.



**py2.6 compatibility fix**

| PR: https://pagure.io/koji/pull-request/1432

Python 2.6 doesn't support context manager for GzipFile. Revert to
original behaviour.

Fixes: https://pagure.io/koji/issue/1431

..
    https://pagure.io/koji/issue/1431
    koji-builder-1.17.0 not compatible with python 2.6

When running kojid on a python2.6 system you receive the following message:

 	

Traceback (most recent call last):
  File "/usr/lib/python2.6/site-packages/koji/daemon.py", line 1295, in runTask
    response = (handler.run(),)
  File "/usr/lib/python2.6/site-packages/koji/tasks.py", line 311, in run
    return koji.util.call_with_argcheck(self.handler, self.params, self.opts)
  File "/usr/lib/python2.6/site-packages/koji/util.py", line 263, in call_with_argcheck
    return func(*args, **kwargs)
  File "/usr/sbin/kojid", line 1302, in handler
    broot.init()
  File "/usr/sbin/kojid", line 544, in init
    self.session.host.setBuildRootList(self.id,self.getPackageList())
  File "/usr/sbin/kojid", line 633, in getPackageList
    self.markExternalRPMs(ret)
  File "/usr/sbin/kojid", line 764, in markExternalRPMs
    with GzipFile(fileobj=fo, mode='r') as fo2:
AttributeError: GzipFile instance has no attribute '__exit__'

Alas, python2.6 does not have the fix that permits using GzipFile as a 'with' object.

https://pagure.io/koji/blob/master/f/builder/kojid#_768



**hub: fix check_fields and duplicated parent_id in _writeInheritanceData**

| PR: https://pagure.io/koji/pull-request/1434

fixes: #1433
fixes: #1435

..
    https://pagure.io/koji/issue/1435
    changes for writeInheritanceData should not contain duplicated parent_id

duplicated parent_ids will cause inconsistency like:
```
$ koji call getInheritanceData 48
[]
$ koji call setInheritanceData 48 --kwargs "{'data':[{'parent_id': 350, 'delete link': True, 'priority': 10, 'maxdepth': None, 'intransitive': False, 'noconfig': False, 'pkg_filter': ''},{'parent_id': 350, 'priority': 10, 'maxdepth': None, 'intransitive': False, 'noconfig': False, 'pkg_filter': ''}]}"
None
$ koji call getInheritanceData 48
[{'child_id': 48,
  'intransitive': False,
  'maxdepth': None,
  'name': 'test-parent-tag',
  'noconfig': False,
  'parent_id': 350,
  'pkg_filter': '',
  'priority': 10}]
$ koji call setInheritanceData 48 --kwargs "{'data':[{'parent_id': 350, 'delete link': True, 'priority': 10, 'maxdepth': None, 'intransitive': False, 'noconfig': False, 'pkg_filter': ''},{'parent_id': 350, 'priority': 10, 'maxdepth': None, 'intransitive': False, 'noconfig': False, 'pkg_filter': ''}]}"
None
$ koji call getInheritanceData 48
[]
```

..
    https://pagure.io/koji/issue/1433
    writeInheritanceData checks wrong field for "delete link"

`fields` should be `check_fields` in this case




**fix table name in build_references query**

| PR: https://pagure.io/koji/pull-request/1437

Fixes: https://pagure.io/koji/issue/1436

..
    https://pagure.io/koji/issue/1436
    buildReferences fails for non-rpm builds

There is a typo in the "most recent use" check in `build_references()` that results in an error like the following:



**build_srpm: Wait until after running the sources command to check for alt_sources_dir**

| PR: https://pagure.io/koji/pull-request/1410

In the RPM layout, it's possible that the SOURCES directory might be
completely empty save for the lookaside payload. In this case a SOURCES
directory wouldn't exist in SCM, and wouldn't be created until the
sources command is run.

Moving this code block down lets us run the sources command before we try to decide if we should look for the RPM layout or not.



**display task durations in webui**

| PR: https://pagure.io/koji/pull-request/1383

Fixes: https://pagure.io/koji/issue/1382

..
    https://pagure.io/koji/issue/1382
    [RFE] taskinfo page can show task durations

It could be useful to see duration on taskinfo page instead of computing them in the head over and over again.



**rollback errors in multiCall**

| PR: https://pagure.io/koji/pull-request/1358

Fixes: https://pagure.io/koji/issue/1357

..
    https://pagure.io/koji/issue/1357
    errors in multicall can result in partial db changes

The multicall handler catches errors from individual calls and returns the error in the result rather than re-raising it. This sidesteps Koji's normal behavior of rolling back the transaction if an uncaught error occurs in the call.

This is unlikely to be a problem for most calls, but there are possible cases where a call could make multiple updates, hit an error partway through, and leave those partial updates in place.










**fix mapping iteration in getFullInheritance**

| PR: https://pagure.io/koji/pull-request/1406

Fixes: https://pagure.io/koji/issue/1405

..
    https://pagure.io/koji/issue/1405
    CLI command koji list-tag-inheritance --stop=tag-52zov tag-mjckr returns none

** _Steps to reproduce:  _**
~~~~
 koji list-tag-inheritance --stop=tag-52zov tag-mjckr
~~~~


** _Current Output:  _**
~~~~
koji: Fault: <Fault 1: "<class \'RuntimeError\'>: dictionary changed size during iteration">\ntag-mjckr (21)\n')

~~~~


**_Expected Output:_**
~~~~
Show parents/children up to this tag
~~~~




**kojid: Download only 'origin'**

| PR: https://pagure.io/koji/pull-request/1398

We have pretty slow connection from s390x koji which helped to uncover
this part. Kojid downloads all files from repomd.xml (incl. filelists)
which is really big. What we really want is just 'origin' (used by Koji
only).

Signed-off-by: Igor Gnatenko <ignatenkobrain@fedoraproject.org>



**Check CLI arguments for enable/disable host**

| PR: https://pagure.io/koji/pull-request/1365

Fixes: https://pagure.io/koji/issue/1364

..
    https://pagure.io/koji/issue/1364
    enable-host, disable-host without parameters returns none

** _Steps to reproduce:  _**
~~~~
 koji  enable-host
 koji disable-host
~~~~


** _Current Output:  _**
~~~~
None
~~~~


**_Expected Output:_**
~~~~
Usage: koji enable-host...
Usage: koji disable-host...
~~~~




**CLI list-channels sorted output**

| PR: https://pagure.io/koji/pull-request/1390

None



**block_pkglist compatibility fix**

| PR: https://pagure.io/koji/pull-request/1389

On older hubs --force is not supported, so CLI will fail on unknown
parameter. This use force option only if it is explicitly required.

Fixes: https://pagure.io/koji/issue/1388

..
    https://pagure.io/koji/issue/1388
    koji-1.17.0-5.fc31 client with 1.16.1 server block doesnt work

➜  epel7 git:(epel7) koji block-pkg epel7 libdnf
2019-04-05 13:50:26,421 [ERROR] koji: ParameterError: pkglist_block() got an unexpected keyword argument 'force'

I'm not sure if this is expected or not, but when using the newest client against an older server (koji.fedoraproject.org) block doesn't seem to work from cli. 






**scale task_avail_delay based on bin rank**

| PR: https://pagure.io/koji/pull-request/1386

Currently task allocation in Koji is decentralized. The builders pick their next task from a list. The system prefers builders with higher available capacity via the algorithm that the builders use. For a given task, they look at the set of other ready builders for the given channel-arch bin. If the host is below the median, it will not take that task until a waiting period (`task_avail_delay`) has passed. This delay gives higher capacity hosts more of a chance to claim the task.

Unfortunately, if the set of hosts is very heterogeneous in capacity, the largest capacity hosts might not get used as much as they should because this algorithm does not distinguish any more finely than above/below the median.

This change generalizes the `task_avail_delay` behavior to scale with the rank of the host within the channel-arch bin. The hosts with highest capacity will take the task immediately, while hosts lower down will have a delay proportional to their rank. We calculate rank as a float between 0.0 and 1.0 and use that as a multiplier for the delay.

The end result will be that hosts with higher available capacity will be more likely to claim a task, resulting in better utilization of the highest capacity hosts.



**Use createrepo_update even for first repo run**

| PR: https://pagure.io/koji/pull-request/1363

createrepo_update is currently reusing only old repos from same tag.
Nevertheless, for first newRepo there is no old data, but there is a
high chance, that we inherit something. This inherited repo can be used
also for significant speedup.

Fixes: https://pagure.io/koji/issue/1354

..
    https://pagure.io/koji/issue/1354
    [RFE] use createrepo_c --update on new repos (when possible)

Currently, --update is only used when doing a repo regeneration, not the first time that a repo is generated.  

Let's say that you create the following:
tag: foo-build (inherits from f30-build)

with a corresponding target.  In this case, when generating the repo for foo-build, it would be possible to use --update pointing at f30-build and that would significantly speed up the process.







**honor mock.package_manager tag setting in mock-config cli**

| PR: https://pagure.io/koji/pull-request/1374

Fixes: #1167
Fixes: #339

This is more of a short term fix for this, but it does the job

..
    https://pagure.io/koji/issue/1167
    mock-config does not honor settings in extra data

The config returned by `koji mock-config` does not specify correct package manager even if the tag has it set in the extra data.

```
$ koji call getBuildConfig f29-build
{'arches': 'armv7hl i686 x86_64 aarch64 ppc64le s390x',
 'extra': {'mock.package_manager': 'dnf'},
 'id': 3428,
 'locked': False,
 'maven_include_all': False,
 'maven_support': False,
 'name': 'f29-build',
 'perm': None,
 'perm_id': None}
$ koji mock-config --tag f29-build --arch x86_64 | grep package_manager
$
```

For the CLI command this is definitely a bug, as there's no other way for caller to specify it.

It would be nice if `koji.genMockConfig` honored the setting as well or there was some other API that would simplify it. Right now to get proper config a user needs to call `getBuildConfig` and then `genMockConfig` ([example](https://pagure.io/rpkg/pull-request/396#request_diff)). This leaks a lot of details.

..
    https://pagure.io/koji/issue/339
    mock build hangs with f26 mock config

Today, I used ``koji`` to generate a f26 mock config file

```
koji mock-config --tag f26-build --arch=x86_64 --topurl=http://kojipkgs.fedoraproject.org/ -o f26-x86_64.cfg
```

and met an issue that following line does not appear in the config as well as repos

```
config_opts['package_manager'] = 'dnf'
```

BTW, after I added this line manually,

``mockbuild`` hangs at step

```
Start: dnf install
```




**Support tilde in search**

| PR: https://pagure.io/koji/pull-request/1297

Fixes https://pagure.io/koji/issue/1294

Signed-off-by: Miro Hrončok <miro@hroncok.cz>

..
    https://pagure.io/koji/issue/1294
    Cannot search build with tilde

I cannot search this valid build in Koji: **python38-3.8.0~a2-1.fc29**

https://koji.fedoraproject.org/koji/search?terms=python38-3.8.0~a2-1.fc29&type=build&match=glob

Bodhi uses this link in https://bodhi.fedoraproject.org/updates/python38-3.8.0~a2-1.fc29 cc @bowlofeggs 

The error is:

> Search terms may contain only these characters: a-zA-Z0-9 @.,_/\()%+-*?|[]^$

I poprose to **add `~` to the list**, as this is completely valid: https://docs.fedoraproject.org/en-US/packaging-guidelines/Versioning/#_versioning_prereleases_with_tilde





**kojira: fix iteration over repos in py3**

| PR: https://pagure.io/koji/pull-request/1356

Multiple threads loop over this data, which changes. These loops
need to use a copy. In py2 .keys() and .values() are copied data,
but in py3 they are references to the dict data.

Fixes: #1355

..
    https://pagure.io/koji/issue/1355
    kojira: dictionary changed size error in updateRepos()

Under python3, kojira seems to hit the following pretty easily.

```
Traceback (most recent call last):
  File "/usr/sbin/kojira", line 760, in main
    repomgr.updateRepos()
  File "/usr/sbin/kojira", line 520, in updateRepos
    for repo in self.repos.values():
RuntimeError: dictionary changed size during iteration
```




**Fix hub startup handling**

| PR: https://pagure.io/koji/pull-request/1347

Fixes: #875

In some environments, module loading can break after restarts. Here we take two steps to prevent that:

* disable mod_wsgi auto reloading
* use a thread lock for the server setup that happens on first call

..
    https://pagure.io/koji/issue/875
    hub plugins appear to break hub on code updates

In the past, we were able to apply hub changes with little or no downtime.

- upgrade koji packages
- restart httpd

Of late, we have been seeing errors pop up as soon as the packages update. They look like this:

```
2018-04-04 15:00:49,166 [ERROR] m=None u=None p=97080 r=?:? koji.plugins: Traceback (most recent call last):
   File "/usr/share/koji-hub/kojixmlrpc.py", line 496, in load_plugins
     tracker.load(name)
   File "/usr/lib/python2.6/site-packages/koji/plugin.py", line 75, in load
     raise koji.PluginError('module name conflict: %s' % mod_name)
 PluginError: module name conflict: _koji_plugin__runroot_hub
```

With similar errors for other configured hub plugins.

The problem goes away after an httpd restart.  We only load plugins on the first call for each http process, but I guess maybe something is persisting in the module namespace somehow? Or our firstcall check is flawed?



**Rely on ozif_enabled switch in BaseImageTask**

| PR: https://pagure.io/koji/pull-request/1346

Fixes: https://pagure.io/koji/issue/1345

..
    https://pagure.io/koji/issue/1345
    Missed ImageFactory detection

`BaseImageTask` uses IF, but it is not checking `ozif_enabled` flag resulting in:

    <Fault 1: \'Traceback (most recent call last):\
      File "/usr/lib/python2.7/site-packages/koji/daemon.py", line 1244, in runTask\
        response = (handler.run(),)\
      File "/usr/lib/python2.7/site-packages/koji/tasks.py", line 307, in run\
       return koji.util.call_with_argcheck(self.handler, self.params, self.opts)\
     File "/usr/lib/python2.7/site-packages/koji/util.py", line 216, in call_with_argcheck\
       return func(*args, **kwargs)\
     File "/usr/sbin/kojid", line 4109, in handler\
       ApplicationConfiguration(configuration=config)\
    NameError: global name \\\'ApplicationConfiguration\\\' is not defined\
    \'>',)



**add .tgz to list of tar's possible extensions**

| PR: https://pagure.io/koji/pull-request/1344

Fixes: https://pagure.io/koji/issue/1343

..
    https://pagure.io/koji/issue/1343
    archive extensions for tarball miss .tgz

.tgz is still sometimes used, let's add it to default set




**Remove 'keepalive' option**

| PR: https://pagure.io/koji/pull-request/1277

keepalive is not used anymore anywhere in koji

Fixes: https://pagure.io/koji/issue/1239

..
    https://pagure.io/koji/issue/1239
    Deprecate keepalive

`keepalive` is allowed in config files, while it is not used for anything. Let's deprecate it and remove in some future version.




**minor gc optimizations**

| PR: https://pagure.io/koji/pull-request/1337

An attempt to make gc a little faster without too much refactor.



