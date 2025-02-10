Koji 1.35.2 Release notes
=========================

All changes can be found in `the roadmap <https://pagure.io/koji/roadmap/1.35.2/>`_.
Most important changes are listed here.

Major change is this release is kojira rewrite and repos on-demand.

Migrating from Koji 1.35.0/1.35.1
---------------------------------

No special action are needed.


Security Fixes
--------------

None


Client Changes
--------------
**Avoid malformed tasks for updated signatures**

| PR: https://pagure.io/koji/pull-request/4210

Older clients displayed scary warnings even for correct (new) API signatures.

**Adjust download-build messages**

| PR: https://pagure.io/koji/pull-request/4286

Better user communication in ``download-build``.

**Print client version when unable to connect to server**

| PR: https://pagure.io/koji/pull-request/4155

``version`` command displayed nothing when server couldn't be reached. It
displays at least its own version.

**wait-repo: wait for a current repo by default**

| PR: https://pagure.io/koji/pull-request/4228

Improved backward compatibility for ``wait-repo`` default behaviour.

System Changes
--------------
**Include tag name in newRepo args**

| PR: https://pagure.io/koji/pull-request/4209

Better readibility in UIs.

**RawHeader: fix store offsets when duplicate tags are present**

| PR: https://pagure.io/koji/pull-request/4202

Improved handling of duplicate rpm headers (which sometimes happened in old rpm
versions).

**Drop cvs requirement.**

| PR: https://pagure.io/koji/pull-request/4271

CVS is now not a hard install requirement as most instances will probably never
see it again. If you are expecting to builds from cvs, just install it on
builders manually.

**Don't prepopulate log list for mavenBuild**

| PR: https://pagure.io/koji/pull-request/4274

Bug fix for handling upload of maven log files.

**Fix for reading config files when contains UTF-8 chars**

| PR: https://pagure.io/koji/pull-request/4214

Better support for unicode in config files.

**Improve min_event handling in RepoWatcher**

| PR: https://pagure.io/koji/pull-request/4285

``RepoWatcher`` could have returned older repo in some cases.

**Wrong types in default hub values**

| PR: https://pagure.io/koji/pull-request/4309

New repo-related configuration values have wrong type casting, so hub could
have complained about string vs integer values there.

**F42: sbindir is now bindir**

| PR: https://pagure.io/koji/pull-request/4297

Fedora is unifying ``bin`` and ``sbin`` directories, so from this release up
we're installing programs to ``bin``.

API Changes
-----------
**newRepo: support hints for oldrepo value**

| PR: https://pagure.io/koji/pull-request/4021

Performance improvement for some situation like ``clone-tag`` initial repo.

**Fix repo handing for bare wrapperRPM task**

| PR: https://pagure.io/koji/pull-request/4267

``wrapper-rpm`` command wasn't requesting current repo under new repo
management.

**Stabilize order for listTagged**

| PR: https://pagure.io/koji/pull-request/4152

Return ``listTagged`` output ordered even for cases when two builds were tagged
in same event.

**Fix latest symlink check**

| PR: https://pagure.io/koji/pull-request/4207

Always preserver ``latest`` symlink for repos.

**Provide user for scm policy check**

| PR: https://pagure.io/koji/pull-request/4170

Additional ``user`` variable sent to scm policy check, so e.g. ``user`` test
can be used there now.

Kojira
------
**Adjust arches warning message for external repo check**

| PR: https://pagure.io/koji/pull-request/4167

Better message in kojira's log.

**Allow setting ccache in config**

| PR: https://pagure.io/koji/pull-request/4140

``ccache`` can now be set also in kojira's config.

**Consistent daemon exit codes**

| PR: https://pagure.io/koji/pull-request/4126

Exit codes are now consistent across ``kojid``, ``kojira`` and ``kojivmd``.

**Split currency and regen**

| PR: https://pagure.io/koji/pull-request/4277

If there is a lot of autoregenerated tags, some user-specified repo regen
requests could have been delayed. Now these are running in separate threads.

Web UI
------
**Drop cgi import**

| PR: https://pagure.io/koji/pull-request/4251

Python's ``cgi`` library is removed in 3.13, so dropping it also from koji
code.

**Fix for non-existent target_info**

| PR: https://pagure.io/koji/pull-request/4079

Deleted targets caused failing web pages.

**No hyperlink in title**

| PR: https://pagure.io/koji/pull-request/4136

HTML tag was present in title value.

Devtools and tests
------------------
**choose correct import machinery in unit test**

| PR: https://pagure.io/koji/pull-request/4307

**Update py2 tests**

| PR: https://pagure.io/koji/pull-request/4292

**combination of test-requirements(-py2).txt**

| PR: https://pagure.io/koji/pull-request/4245

**enable tests/test_lib for py2**

| PR: https://pagure.io/koji/pull-request/4249

**flake8 fix**

| PR: https://pagure.io/koji/pull-request/4196

**unittest: use unittest.mock instead of mock**

| PR: https://pagure.io/koji/pull-request/4239

**fix check-api for python3 bin and requirement of setuptools**

| PR: https://pagure.io/koji/pull-request/4241

Documentation
-------------
**migration notes for repo generation**

| PR: https://pagure.io/koji/pull-request/4197

**Update paths in migration docs**

| PR: https://pagure.io/koji/pull-request/4238
