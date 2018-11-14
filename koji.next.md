= Rough notes on koji.NEXT =

Taken originally from https://lists.fedorahosted.org/archives/list/koji-devel@lists.fedorahosted.org/thread/RVBX5QZX734NXDYYOCKQHLAWJMTREBJC/#RVBX5QZX734NXDYYOCKQHLAWJMTREBJC

Warning to the reader:

    Treat this document as a volatile working document.  We plan to expand on
    the ideas in here over time, as we have time.  Some items here might
    already be done, but we still need to mark them as such.  Just because an
    item appears here doesn’t mean that it will be implemented.  This file is
    meant to track ideas and goals.  Please submit updates as pull requests at
    https://pagure.io/koji


= High level goals =

- better documentation
- more community involvement
- refactor/modernize code
- more modular design
  - content generators
  - broader, better plugin framework
- better support for different types of build processes
- better support for for different types build output
- make hard-wired restrictions more configurable
- easier to deploy
- better qa process
- better release process
- better automated tests
- better reports


= Highlights/Major changes =

- python3 support
  - RHEL 5 support is gone in main Koji releases. (It is available in the "legacy-py24" Git branch.)
  - RHEL 6 is the oldest supported platform (so, Python 2.6 + python-six)
- drop xmlrpc in favor a json based rpc
- build namespaces
  - allow for use cases that require multiple builds of the same NVR (or NVRA)
- refactor task scheduling
- extend content generator support
  - content generators are available in 1.x, but in 2.0 they will be more integral
  - refactor kojid to use content generator calls
  - (possibly) tighter integration in the db
- unify handling of rpms with other build types in the db
  - e.g. unify rpminfo and archiveinfo tables
- support different ways of building (possibly via content generators)
- utilize jsonb fields in postgres
- modular auth
  - make it easier to add new auth mechanisms
  - support openid auth
- improve plugins
  - make the plugin framework cleaner and more pythonic
  - support plugins in cli and web ui
- improve/update web ui
  - drop cheetah templates in favor of python-jinja2
  - more parity with cli
  - history browsing
  - landing page search or history
  - support plugins
- change how tag pkglists (and blocking) work
- refactor package ownership
- refactor uploads
- more flexible gc
- introduce an ORM to do away with raw SQL queries.
- know how to manage dist repositories of RPMs
- know how to build installation media
- more granular access control/groups
  - things like Read, Execute, Execute scratch, Delete, Tag, so we can delegate
    building image scratch builds to non-core people for testing purposes.
  - also Read/NoRead acls for doing builds of sources under embargo.
- be able to spin up builders in amazon or openstack or libvirt as needed

= Yet more changes =

- store all task requests by named args
  - (for ease of inspection)
- get rid of tagBuild tasks
- drop odd event refererences in favor of timestamps
- streamlined cli options
- marker files for many things on disk
- more history data
- policy code
  - more robust syntax
    - test negation
    - OR
    - parentheses
    - quoted strings
   - multiple result policies (non-terminal actions)
   - all-matches policy (needed for scheduler?)
   - break action (breaks out of nesting)
   - stop action (halts processing of an all-matches policy)
- a metrics reporting page of build activity and perhaps downloads per build.
- consistency in the cli subcommands (see john florian’s post on the ML).
- reorganize db/files so that archiving some things is easier.  right now you
  have to have everything mixed on the same mount.
