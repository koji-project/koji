How tag inheritance works
-------------------------

Almost everything in koji is dealing with tag and their inheritance.
What is it good for and how can it be configured?

Every tag handles its own configuration and as an administrator you
can live with just this. But true power of tag structure is hidden in
inheritance. You can compose tags, use parent products from which are
data inherited to new versions or other layered products and more.

Each tag has this set of data:

tag data
   1. architectures - here is the set of architectures which will be
      used in the moment, when given tag is used as a buildroot (in
      other words, when it is used in target definition)
   2. comps groups - similar to architectures, this data are used as
      installation groups, when tag is used as a buildroot. Generally,
      ``srpm-build`` and ``build`` groups are required in almost all
      cases. There could be also some additional groups like
      ``maven-build`` or ``livemedia-build`` for other operations,
      than just building rpms. Groups can be created and edited via
      ``*-group-*`` koji commands.
   3. maven options - If maven builds are enabled in koji environment
      (needs setup on hub's side), ``maven_support`` and
      ``include_all`` are options related to it. First says, that
      maven repositories should be generated and second one limits if
      all tagged versions of some artifact should be present in such
      repository.
package list
   Every tag carries a list of allowed packages, which can be tagged
   there and also owner of such package/tag combination. Note, that
   owner doesn't mean much in respect to who can do what. It is just a
   default recipients of notifications and can be changed in any time.
   Ownership doesn't limit anybody in un/tagging builds for that
   tag/package. This is on the other hand driven by hub policies.
   Package list simply says, what is allowed in tag (even if there is
   no build for given package).
tagged builds list
   This is the last component of tag. Obviously it is a list of builds
   for packages from previous point. It will never happen, that you'll
   see some builds for which is not package listed above.

All these three groups of data can be inherited and propagated through
inheritance chains.

Inheritance options
___________________

Whole inheritance can be edited via CLI's commands
``add-tag-inheritance`` and ``edit-tag-inheritance``. They have same
options which are described with examples here:

Simple ``add-tag-inheritance`` requires two existing tags which will
be linked together in inheritance chain.

::

   $ koji add-tag parent
   $ koji add-tag child
   $ koji add-tag-inheritance child parent
   $ koji list-tag-inheritance child
          child (168)
     ....  └─parent (167)

In the example you can see basic inheritance chain. You see ``child``
tag which is inheriting data from ``parent`` tag. Numbers behind tag
names are numeric ids, which you don't need to care about in normal
situations, but which can be useful in scripting koji. Four dots in
the beginning of line are placeholders for different inheritance
flags. These can be: M, F, I, N which denotes ``maxdepth``,
``pkg_filter``, ``intransitive`` and ``noconfig`` respectively.  All
these options can specified via CLI.

``priority``
    When you're adding new inheritance line to tag, which already has
    some parent, you would like to denote, in which part of
    inheritance chain new parent should appear. Let's continue with
    previous example.

    ::

     $ koji add-tag less-significant-parent
     $ koji add-tag-inheritance child less-significant-parent --priority 100
     $ koji list-tag-inheritance child
          child (168)
     ....  ├─parent (167)
     ....  └─less-significant-parent (169)

    What happened here is, that ``parent`` has default priority 0,
    while new one is priority 100. Lower number wins here. If you
    change your mind, you can always use ``edit-tag-inheritance`` to
    change the priority.

    .. note::
      Good rule of thumb is to not create inheritance without priority
      and use 10's or 100's steps. In such case you shouldn't need to
      update priorities, when adding something in the middle (where you
      can use e.g. priority 15 like in good old Basic times).

``maxdepth``
   For longer inheritance chains you may not want to treat whole
   chain. Let's leave our example and get more real-life situation.

   ::

    $ koji list-tag-inheritance linux3-build
         linux3-build (4380)
    ....  └─linux3-override (4379)
    ....     └─linux3-updates (4373)
    ....        └─linux2 (4368)
    ....           └─linux1 (4350)
    ....              └─linux0 (4250)

    $ koji add-tag linux4-build
    $ koji add-tag-inheritance linux4-build linux3-build --maxdepth 0
    $ koji list-tag-inheritance linux4-build
         linux4-build (4444)
    M...  └─linux3-build (4380)

   This is not, what you would see in Fedora's koji, because Fedora is
   not reusing anything from previous releases and is doing mass
   rebuilds instead, but it could have. In this case, we only want
   packages from ``linux3-build``, but not anything inherited into it.
   ``maxdepth`` does exactly this and strips the rest of inheritance
   chain.

``intransitive``
    Intransitive inheritance links are as what they say. If they are
    used somewhere deeper in inheritance chain, they will be ignored.
    It can be used for ensuring, that something will not be propagated
    by mistake. In combination with ``maxdepth`` it can mean hard stop
    even before ``maxdepth`` is reached.

``noconfig``
    While `normal` inheritance inherits everything - it means tag
    configuration, package list and tagged builds, links with this
    option are used only for propagating list of packages and builds.
    Everything else is ignored (architectures, locks, permissions,
    maven support).

``pkg-filter``
    Package filter is defined as regular expression and limits which
    packages are propagated through this link.
