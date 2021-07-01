Koji 1.25.1 Release notes
=========================

All changes can be found at `pagure <https://pagure.io/koji/roadmap/1.25.1/>`_.
Most important changes are listed here.

Migrating from Koji 1.25
------------------------

No special actions are needed.

Security Fixes
--------------

None

Library changes
---------------

**return taskLabel for unknown tasks**

Regression fix - some external plugins was represented in web/console UI by
"malformed task" description. Now we're back with proper method name and
architecture.

| PR: https://pagure.io/koji/pull-request/2906


Hub Changes
-----------

**fix SQL condition**

| PR: https://pagure.io/koji/pull-request/2898

Change in 1.25 caused an error in ``listTagged`` with ``type`` option. Fixed.

**use "name" in result of lookup_name for CGs**

| PR: https://pagure.io/koji/pull-request/2916

New ``cg_match`` policy test returned dicts not cg names, so checking was not
working correctly.

**clean noisy error log**

| PR: https://pagure.io/koji/pull-request/2932

Removed debug message which cluttered httpd logs in 1.25.

Web Changes
-----------

**Drop download link from deleted build**

| PR: https://pagure.io/koji/pull-request/2896

If build is deleted we don't display download links to not confue the users.

**Fix getting tag ID for buildMaven taskinfo page.**

| PR: https://pagure.io/koji/pull-request/2900

``buildMaven`` taskinfo page was broken for deleted builds.

Documentation/DevTools Changes
------------------------------
**update .coveragerc to ignore p3 code**

| PR: https://pagure.io/koji/pull-request/2881

**docs for KojiHubCA/ClientCA**

| PR: https://pagure.io/koji/pull-request/2888

**tests - Add support for running tox with specific test(s)**

| PR: https://pagure.io/koji/pull-request/2890
