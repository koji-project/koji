Koji Utilities
==============

Basic koji is equipped with few handy utilities for maintaining
healthy build environment. They are packaged in ``koji-utils`` rpm and
can be installed as such.

.. _utils-kojira:

Kojira
------

Kojira is stand-alone server which handles buildroot repos. It checks
if any builds were added to buildroots or build tag configuration has
changed. In such case it will trigger ``newRepo`` tasks to get build
repos actual once more. It is worth to create separate usera for
kojira with only ``repo`` permission.

Its usage is straightforward. It is being installed as system service
``kojira``, so standard systemctl commands like ``enable`` ``start``
and ``restart`` simply works.

``/etc/kojira/kojira.conf`` contains basic configuration for this
service. Standard connection options are defined there (keytab,
server, ...) and few options which affects, how kojira works,
especially in relation to throttling in creating ``newRepo`` tasks.

``deleted_repo_lifetime = one week (604800)``
    This time (in seconds) is uses to clean up expired repositories.
    It makes sense, that you don't want only the latest repodata. In
    case of debugging some older build. Even in case you don't want to
    do this, it is recommended to set it at least to few hours in
    case, there is some running build, which is still using these
    older data.

``dist_repo_lifetime = one week (604800)``
    This is similar to previous one. The only difference is that while
    previous is for buildroots, this one is affecting dist repos.

``recent_tasks_lifetime = 600``
    kojira is buffering recent ``newRepo`` finished tasks to avoid
    some race conditions. Generally, there is no reason to change this
    default.

``ignore_tags = ''``
    Comma-separated globs for tag names. These tags are simply ignored
    by kojira (but they can still be manually regenerated via ``koji
    regen-repo`` command.

``debuginfo_tags = ''``
    Comma-separated globs for tag names. Regenerated repos will have
    separate directory/repodata with corresponding debuginfo RPMs.

``source_tags = ''``
    Comma-separated globs for tag names. Regenerated repos will
    contain also corresponding SRPMs.

``separate_source_tags = ''``
    Comma-separated globs for tag names. Regenerated repos will have
    separate directory/repodata with corresponding SRPMs.

``ignore_stray_repos = False``
    In some strange cases (someone manually deleted repo via API, but
    not corresponding directories), there could stay some repo
    directories. If this is set to False, kojira will just skip these.
    Otherwise, it will remove them as if they would be normal
    repodata referenced from db.

``max_delete_processes = 4``
    How many threads are used for deleting data on disk.

``max_repo_tasks = 4``
    The largest hub impact is from the first part of the ``newRepo``
    task. Once it is waiting on subtasks (spawned createrepo), that
    part is over. So, it makes sense to limit running ``newRepo``
    tasks to not exhaust hub's capacity.

``max_repo_tasks_maven = 2``
    Maven repo regeneration is ways more resource-demanding than rpm
    ones. So, we've separate limit on this.

``repo_tasks_limit = 10``
    Overall limit on running tasks is set here. It involves all
    ``newRepo`` tasks spawned by kojira and also by other users.

``check_external_repos = false``
    If True, monitor external repos and trigger the appropriate Koji repo
    regenerations when they change.
    Note that you need to have your database set to use UTC, as otherwise
    you can end with weird behaviour. For details see
    https://pagure.io/koji/issue/2159
    
``queue_file = None``
    Writable path could be set here. In such case, kojira will write a
    list of currently monitored tags there with simple statistics in
    every cycle. File would contain information about how long these
    tags are expired and what is the computed score for them. This can
    be used to debug and check in realtime the actual performance.

Garbage Collector
-----------------

There are tons of builds, which will be never used for anything. GC is
caring to get rid of these, so they'll not exhaust disk space. As it
is a sensitive task to not remove something what will be needed in
future, everything is driven by policy with same language as hub's
one.

Note, that GC removes only physical content. Every build will stay in
database, only build artifacts and logs get deleted.

GC runs all of the following actions (if they are not overriden via
``--action``):

``delete``
    Delete builds that have been in the trashcan for long enough.
    Builds satisfying any of following conditions, will be exempted
    from deletion:

      * package is on blacklist ``pkg_filter``
      * they are not tagged with any other tag
      * their signatures are not in ``protected_sig`` or they are
        unknown
      * they are tagged in trashcan for shorter time than
        ``grace_period``

``prune``
    This action goes through all tags and checks tagged builds
    according to ``prune`` policy from config. Policy can result in
    ``keep``, ``untag`` or ``skip`` actions. First two are
    self-evident, last one is similar to ``keep``, but these builds
    are also ignored in tagged builds ordering.

    Prune policy is not run against trashcan tag itself, also locked
    tags are ignored if ``bypass_locks`` is not specified.

    With ``purge`` option, untagged builds can be immediately deleted.

``trash``
    Runs through all builds without any tags (for longer than
    ``delay``) and put them to trashcan (effectively scheduling them
    for deletion after additional ``grace_period`` time).

    Following builds can't be put to trashcan during this action:
      * build was tagged somewhere meanwhile (race condition)
      * build was used inside some build's buildroot. We don't want to
        delete such build, so we have reproducible build.
      * build is part of any image or archive
      * build was untagged later than before ``max_age`` seconds.
      * build has some protected or unknown signature(s) ``protected_sig``

``salvage``
     Untags builds from trashcan, which now have some protected or
     unknown key. (Note, that you can always remove trashcan tag
     from any build - it is normal tag as any other)

Prune Policy
............

Policy is part of config and without it, ``prune`` action will refuse
to work. Best documentation here would be part of example config with
comments.

.. code-block::

  [prune]
  policy =
      # stuff to protect
      # note that tags with master lock engaged are already protected
      tag *-updates :: keep
      age < 1 day :: skip
      sig fedora-gold :: skip
      sig fedora-test && age < 12 weeks :: keep

      # stuff to chuck semi-rapidly
      tag *-testing *-candidate :: {  # nested rules
          order >= 2 :: untag
          order > 0 && age > 6 weeks :: untag
      } # closing braces must be on a line by themselves (modulo comments/whitespace)
      tag *-candidate && age > 60 weeks :: untag

      # default: keep the last 3
      order > 2 :: untag

GC Options
..........
``delay = 5 days``
    Time, after which untagged builds can go to trashcan via
    ``trashcan`` action.

``grace_period = 4 weeks``
    How long builds are staying in trashcan before final deletion.

``unprotected_keys = ''``
    Set of signing keys, which are treated as in same way as
    "unsigned" packages.

``tag_filter = ''``
    If defined, only tags corresponding to these globs are checked.

``ignore_tags = ''``
    Tags corresponding to these globs are ignored.

``pkg_filter = ''``
    Globs for package names which should be processed.

``bypass_locks = ''``
    If tag is locked and ``bypass_locks`` is set and GC user has
    sufficient permissions, even locked tags are pruned.

``purge = False``
    If set, delete packages immediately during pruning action
    (effectively skipping ``delay`` + ``grace_period`` safety period)

``trashcan_tag = trashcan``
    Default name for trashcan tag, you can use other tags for testing
    policies, or deploy multiple configuration in cascade-like
    workflows (anyway, not recommended)

``key_aliases = None``
    Keys are normally defined by their hashes, which could be
    inconvenient while reading configs. This option (pairs of
    hash/name) make it more readable.


Notification related options
............................
``smtp_host = None``
   Connection parameters

``mail = True``
   Send / don't send e-mail notifications

``email_domain = fedoraproject.org``
   Append this domain to usernames

``from_addr = Koji Build System <buildsys@example.com>``
    Sender address

``email_template = /etc/koji-gc/email.tpl``
    Simple template which can contain python formatting (via
    ``string.Template``) with ``owner`` (owner name) and ``builds``
    (pre-generated list of builds).

Koji Shadow
-----------

Koji DB Sweeper
---------------
