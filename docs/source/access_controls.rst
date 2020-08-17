===============
Access Controls
===============

Koji is complex system, so there are many places where some kind of access
control is used. Here is the documentation hub for all the mechanisms in place.

User/Builder Authentication
===========================

Users (and builders) are authenticated via one of the following mechanisms. Most
preferred is GSSAPI/Kerberos authentication. Second best is authentication via
SSL certificates. Mostly for testing environments we also support authenticating via
username/password but it has its limitations which you should be aware of.

Details can be find at :ref:`auth-config`

SCM Permissions
===============

Most important data for koji are its inputs which equals to Source Control
Management systems (supported are CVS, SVN and GIT). Every production
environment should have limited set of trusted external sources. We're covering
this by ``alowed_scms`` option in builder's config. Admin can set there which
e.g. GIT repositories are allowed as inputs and can also instruct koji how to
create SRPM from such checkout.

Details of ``alowed_scms`` option is covered under :ref:`scm-config`


Hub Policies
============

Hub policies are core system of access controls. They can define specialized
policies for many things ranging from permissions to tag specific builds to
specific tag to e.g. assigning builds to specific builders (channels) or storing
results on different disk volumes. Policies allow user permissions (see below)
to be used in their rulesets.

Only some policies are for access control (allow/deny permissions checks) while
others like channel policy governs different areas of koji.

There is whole document :doc:`defining_hub_policies` covering this.

User Permissions
================

Specific chapter are user permissions. Every user can have set of permissions
which allow him to do some actions directly (typically ``admin`` permission) or
these permissions can be referenced in hub policies.

See :doc:`permissions` for details.
