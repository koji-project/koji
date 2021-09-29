Koji 1.26.1 Release notes
=========================

All changes can be found at `pagure <https://pagure.io/koji/roadmap/1.26.1/>`_.
Most important changes are listed here.

Migrating from Koji 1.26
------------------------

No special actions are needed.

Security Fixes
--------------

None

Client changes
--------------

**CLI channels, hosts methods works with older hub**

| PR: https://pagure.io/koji/pull-request/2991

Backward compatibility of new CLI and older hubs


**Fix disabled/enabled option for empty results**

| PR: https://pagure.io/koji/pull-request/3016

Simple fix for list-hosts filters resulting in empty set.


Hub Changes
-----------

**move btypes from headers to body of proton message**

| PR: https://pagure.io/koji/pull-request/3022

AMQP-compatible headers. New values (btypes dicts) were moved to message body.


**create symlink before import and check spec_url for wrapperRPM task**

| PR: https://pagure.io/koji/pull-request/3004
| PR: https://pagure.io/koji/pull-request/3047

``wrapperRPM`` method needed to be updated due to previous policy handling changes.

Builder changes
---------------
**import guestfs before dnf**

| PR: https://pagure.io/koji/pull-request/2993

Problems in jsonc/jansson libraries symbol handling led us to workaround this
issue (until it is solved in upstream libs) so docker images can be built again.


Kojivmd
-------

**change opts allowed_scms_by_* to allowed_scms_use_***

| PR: https://pagure.io/koji/pull-request/3050

Fix for new ``allowed_scm_*`` options.

Documentation/DevTools Changes
------------------------------

 * `README: add koji-hs project <https://pagure.io/koji/pull-request/2997>`_
 * `add instructions for SSL DB connections <https://pagure.io/koji/pull-request/2996>`_
 * `fix "koji" CLI command name in signing instructions <https://pagure.io/koji/pull-request/2994>`_
 * `fix "an user" -> "a user" grammar in help text and errors <https://pagure.io/koji/pull-request/2995>`_
 * `update profiles documentation <https://pagure.io/koji/pull-request/3029>`_
 * `document listHosts method <https://pagure.io/koji/pull-request/3013>`_
 * `fix getBuild documented parameter name <https://pagure.io/koji/pull-request/3021>`_
 * `add all types to docs latest-build and readTaggedBuilds <https://pagure.io/koji/pull-request/3000>`_
 * `fix docs for listBuilds "state" parameter name <https://pagure.io/koji/pull-request/3023>`_
 * `add warnings for remove-sig <https://pagure.io/koji/pull-request/3026>`_
