===============
Access Controls
===============

Koji is complex system, so there are many places where some kind of access
control is used. Here is the documentation hub for all the mechanisms in place.

Perimeter
=========

This can't be covered here as it highly depends on architecture and usage of the
system. Nevertheless, the best option would be global (or company-wide) access
to web and hub https ports, so clients and builders can connect there.

Builders should be restricted on external level (firewalls outside of builders
themselves) to contact only hub and allowed SCMs.  There should be no allowed
access to the internet if there is no good reason to do that and these accessess
are monitored. Otherwise koji can't ensure reproducibility of the build (e.g. if
spec is downloading *something* from the internet - we're doomed). Secluded
intranet segment with nothing able to interfere here is a worthy thing.

Only builders from createrepo channel (and runroot if you're using that plugin)
should have mounted koji volumes in read-write mode. Other builders don't need
that and from security/safety reasons it is not recommended to have it mounted
at all.

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

Hub policies are core system of access controls. It can define specialized
policies for many things ranging from permissions to tag specific builds to
specific tag to e.g. assigning builds to specific builders (channels) or storing
results on different disk volumes.

There is whole document :doc:`defining_hub_policies` covering this.

User Permissions
================

Specific chapter are user permissions. Every user can have set of permissions
which allow him to do some actions directly (typically ``admin`` permission) or
these permissions can be referenced in hub policies.

See :doc:`permissions` for details.
