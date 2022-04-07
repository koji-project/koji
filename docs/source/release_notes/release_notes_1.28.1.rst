Koji 1.28.1 Release notes
=========================

All changes can be found in `the roadmap <https://pagure.io/koji/roadmap/1.28.1/>`_.
Most important changes are listed here.

Migrating from Koji 1.28
------------------------

No special actions are needed.


Security Fixes
--------------

None

Library Changes
---------------
**Fix parsing of URLs with port numbers**

| PR: https://pagure.io/koji/pull-request/3262

1.28 feature allowing authentication tokens as part of git urls broke urls with
specified port.

Client Changes
--------------
**Same format output for list-buildroot with --verbose for py3/py2**

| PR: https://pagure.io/koji/pull-request/3300

Output format for python 2.x and 3.x were unified.

Hub Changes
-----------
**Fix type option handling in readTaggedRPMS**

| PR: https://pagure.io/koji/pull-request/3298

As option is called ``type`` it masked builtins.type call used in exception
handling.

**Improve inheritance priority collision error message**

| PR: https://pagure.io/koji/pull-request/3208

More descriptive exception message.

**Set dst permissions same as src permissions**

| PR: https://pagure.io/koji/pull-request/3265

Another regression introduced in 1.28 - newly header/payload split rpms were not
writtend with the same file permissions so they weren't readable for some tasks.

Kojira
------
**Don't call listTags more than once**

| PR: https://pagure.io/koji/pull-request/3259

Speed improvement - one of the caching calls is now run only at the start and
not in every check cycle. It should bring a less more stress to the hub and a
bit faster kojira noticing repo changes.

Web Changes
-----------
**Fix syntax error**

| PR: https://pagure.io/koji/pull-request/3263

Broken HTML at hostedit page.

**Fix attribute test**

| PR: https://pagure.io/koji/pull-request/3303

Search with empty field led to traceback - 1.28 regression.

**Encode filename as UTF-8**

| PR: https://pagure.io/koji/pull-request/3290

Fix for rpminfo page.

**Fix tag and target shows as string, not as dict to string**

| PR: https://pagure.io/koji/pull-request/3252

Fixed wrong target representation for some tasks in tasks overview page.

Documentation/DevTools Changes
------------------------------

 * `Task flow diagram <https://pagure.io/koji/pull-request/3292>`_
 * `Fix readTaggedRPMs rpmsigs option description <https://pagure.io/koji/pull-request/3297>`_
 * `Increase CLI test cases <https://pagure.io/koji/pull-request/3270>`_
