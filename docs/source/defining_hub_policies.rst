=====================
Defining Hub Policies
=====================

Defining a policy on the hub allows you fine control over certain activities
in the system. At present, policy allows you to control:

* tag/untag/move operations
* allowing builds from srpm
* allowing builds from expired repos
* managing the package list for a tag
* managing which channel a task goes to

In the future, we expect to add more policy hooks for controlling more aspects
of the system.

Policy configuration is optional. If you don't define one, then by default:

* tag/untag/move operations are governed by tag locks/permissions
* builds from srpm are only allowed for admins
* builds from expired repos are only allowed for admins
* only admins and users with ``tag`` permission may modify package lists
* tasks go to the default channel
* vm tasks need ``admin`` or ``win-admin`` permission
* content generator import can be done by anyone
* all content ends in ``DEFAULT`` volume.

Configuration
=============

The hub policy is configured in the ``hub.conf`` file, which is an ini-style
configuration file. Policies are defined in the section named ``[policy]``.
Each ``name = value`` pair defines the policy of that name. With multiple line
policies, successive lines should be indented so that the parser treats them
as part of the whole.

Consider the following simple (and strict) example:

::

    [policy]
    tag =
        has_perm admin :: allow
        tag *-candidate :: allow
        all :: deny

This policy section defines a single policy (named 'tag'). The policy is a
series of rules, one per line. The rule lines must be indented. Each rule is
a test and an action, separated by a double colon. The valid actions for
current policies are 'allow' and 'deny'. There are many tests available,
though not all of them are applicable for all policies. Each test is specified
by giving the name of the test followed by any arguments the test accepts.

Each rule in the policy is checked until a match is found. Upon finding a
match, the action is applied. Our example above limits non-admins to tags
ending in -candidate.

Getting a bit more complicated
------------------------------

The example above is very simple. The policy syntax also supports compound
tests, negated tests, and nested tests. Consider the following example:

::

    [policy]
    tag =
        buildtag *epel* :: {
            tag *epel* !! deny
        }
        tag *-updates :: {
            operation move :: {
                fromtag *-updates-candidate :: allow
                fromtag *-updates-testing :: allow
                all :: deny Tagging from some tags to *-updates is forbidden.
            }
            operation tag && hastag *-updates-candidate *-updates-testing :: deny
        }
        all :: allow

This policy sets up some rules concerning tags ending in -updates and tags
containing epel, but is otherwise permissive.

The first nested rule limits builds built from a tag matching ``epel``  to only
such tags. Note the use of !! instead of :: negates the test.

For tags matching ``*-updates``, a particular work-flow is enforced. Moving is
only allowed if the move is coming from a tag matching ``*-updates-candidate``
or ``*-updates-testing``. Conversely, a basic tag operation (not a move) is
denied if the build also has such a tag (the policy requires a move instead).

For denied operations some clarifying message is sent to user. If there is no
specific message (everything after action keyword), only generic 'policy
violation (policy_name)' is sent, so it could be helpful to specify such
messages in more complicated cases.

General format
==============
The general form of a basic policy line is one of the following

::

    test [params] [&& test [params] ...] :: action-if-true
    test [params] [&& test [params] ...] !! action-if-false

And for nested rules:

::

    test [params] [&& ...] [::|!!] {
        test [params] [&& ...] [::|!!] action
        test [params] [&& ...] [::|!!] {
            ...
            }
    }

Note that each closing brace must be on a line by itself.
Using ``!!`` instead of ``::`` negates the entire test.
Tests can only be joined with &&, the syntax does not support ``||``.

Available policies
==================
The system currently looks for the following policies

* ``tag``: checked during tag/untag/move operations
* ``build_from_srpm``: checked when a build from srpm (not an SCM reference) is
  requested.
* ``build_from_repo_id``: checked when a build from a specified repo id is
  requested
* ``package_list``: checked when the package list for a tag is modified
* ``channel``: consulted when a task is created
* ``cg_import``: consulted during content generator imports
* ``volume``: determine which volume a build should live on

These policies are set by assigning a rule set to the given name in the policy
section.

Note that the use of tag policies does not bypass tag locks or permissions

Note that an admin can bypass the tag policy by using ``--force``.

Actions
=======

Most of the policies are simply allow/deny policies. They have two possible
actions: ``allow`` or ``deny``.

The channel policy is used to determine the channel for a task. It supports
the following actions:

``use <channel>``
    * use the given channel

``req``
    * use the requested channel
    * generally this means the default, though some calls allow the client to
      request a channel

``parent``
    * use the parent's channel
    * only valid for child tasks
    * recommend using the ``is_child_task`` test to be sure

Available tests
===============
``true``
    * always true. no arguments

``all``
    * an alias of true

``false``
    * always false. no arguments

``none``
    * an alias of false

``operation``
    * for tag operations, the operation is one of: tag, untag, move. This test
      checks its arguments against the name of the operation and returns true if
      there is a match. Accepts glob patterns.
    * only applicable to the tag policy

``package``
    * Matches its arguments against the package name. Accepts glob patterns.

``version``
    * Matches its arguments against the build version. Accepts glob patterns.

``release``
    * Matches its arguments against the build release. Accepts glob patterns.

``tag``
    * matches its arguments against the tag name. Accepts glob patterns.
    * for move operations, the tag name tested is the destination tag (see
      fromtag)
    * for untag operations, the tag name is null and this test will always be
      false (see fromtag)
    * for the build_from_* policies, tests the destination tag for the build
      (which will be null is --skip-tag is used)

``fromtag``
    * matches against the tag name that a build is leaving. Accepts glob
      patterns
    * for tag operations, the tag name is null and this test will always be
      false
    * for move operations, the tag name test is the one that the build is
      moving from
    * for untag operations, tests the tag the build is being removed from
    * only applicable to the tag policy

``target``
    * matches against the build's target name. Accepts glob patterns.

``hastag``
    * checks the current tags for the build in question against the arguments.

``buildtag``

    * checks the build tag name against the arguments
    * for the build_from_* policies the build tag is determined by the build
      target requested
    * for the tag policies, determines the build tag from the build data,
      which will by null for imported builds

``buildtype``
    * checks the build type(s) against the arguments

``skip_tag``
    * checks to see if the --skip-tag option was used
    * only applicable to the build_from_* policies

``imported``
    * checks to see if the build in question was imported
    * takes no arguments
    * true if any of the component rpms in the build lacks buildroot data
    * only applicable to the tag policy

``is_build_owner``
    * Check if requesting user owns the build (not the same as package
      ownership)
    * take no arguments

``user_in_group``
    * matches the users groups against the arguments
    * true if user is in /any/ matching group

``has_perm``
    * matches the user's permissions against the arguments
    * true is user has /any/ matching permission

``source``
    * test the build source against the arguments
    * for the build_from_* policies, this is the source specified for the build
    * for the tag policy, this comes from the task corresponding to the build
      (and will be null for imported builds)

``policy``
    * takes a single argument, which is the name of another policy to check
    * checks the named policy. true if the resulting action is one of: yes,
      true, allow
    * additional policies are defined in the [policy] section, just like the
      others

``is_new_package``
    * true if the package being added is new to the system
    * intended for use with the package_list policy

``is_child_task``
    * true if the task is a child task
    * for use with the channel policy

``method``
    * matches the task method name against glob pattern(s)
    * true if the method name matches any of the patterns
    * for use with the channel policy

``user``
    * checks the username against glob patterns
    * true if any pattern matches
    * the user matched is the user performing the action

``match``
    * matches a field in the data against glob patterns 
    * true if any pattern matches
