
Draft Builds
============

Draft builds allow for a workflow of building the name rpm NVR multiple times and then choosing
one of those builds to promote.

The draft build feature was added in :doc:`version 1.34.0 <release_notes/release_notes_1.34>`

What is a draft build?
----------------------

In the simplest terms, draft builds are builds with the ``draft`` flag set to True.
This flag has multiple implications:

1. Koji adds a *draft suffix* to the release value for draft builds. The format of this suffix
   is ``,draft{build_id}``. This ensures that the NVR of draft builds is unique, even if the
   base NVR (without the suffix) is not.
2. The NVRA values for rpms included in a draft build are not required to be unique.
3. System policy (notably the tag policy) may set different rules for draft builds.

Draft builds should not be confused with scratch builds. Scratch builds are
simply stored as files and cannot be tagged in Koji. Draft builds, on the other
hand, are actual builds. They can be tagged (subject to policy) and hence potentially
used in buildroots. They can be promoted to become normal builds.


Building a draft build
----------------------

A draft build is triggered simply by passing the ``--draft`` option to the ``build`` command.
The resulting build will be a imported as a draft build.
Otherwise the build process is identical.

At the moment, this feature is only relevant for rpm builds, but it may be extended in the future.


Promoting a draft build
-----------------------

Draft builds can be "promoted" to non-draft using the ``promote-build`` cli
command.

When a draft build is promoted, it is renamed to remove the draft suffix.
The build directory is moved to its new location, and the original
path (the one that is includes the draft suffix) is replaced with a symlink to the new location.

Build promotion is a one-time transition, i.e. builds cannot be "unpromoted".
Only one draft build for a given NVR can be promoted, and once Koji has a
non-draft build for a given NVR, further draft builds for that NVR are blocked.


An Example
----------

You could trigger a draft build with a command like the following:

::

    $ koji build --draft f39-candidate mypackage-1.1-35.src.rpm

Once the build completes, you would have a build named something like:

::

    mypackage-1.1-35,draft_51515

The number in the draft suffix will be the same as the build id.
This makes draft builds stand out.
However, note that the component rpms *do not* have the draft suffix added.

::

    $ koji buildinfo 51515
    BUILD: mypackage-1.1-35,draft_51515 [51515]
    Draft: YES
    State: COMPLETE
    Built by: kojiuser
    Source: mypackage-1.1-35.src.rpm
    Volume: DEFAULT
    Task: 12082 build (f39-candidate, mypackage-1.1-35.src.rpm)
    Finished: Thu, 04 Jan 2024 20:02:18 EST
    Tags: f39-candidate
    Extra: {'source': {'original_url': 'mypackage-1.1-35.src.rpm'}}
    RPMs:
    /mnt/koji/packages/mypackage/1.1/35,draft_51515/noarch/mypackage-1.1-35.noarch.rpm
    /mnt/koji/packages/mypackage/1.1/35,draft_51515/noarch/mypackage-devel-1.1-35.noarch.rpm
    /mnt/koji/packages/mypackage/1.1/35,draft_51515/noarch/mypackage-1.1-35.src.rpm

You can build the same NVR as a draft multiple times.

::

    $ koji build --draft f39-candidate mypackage-1.1-35.src.rpm

::

    $ koji buildinfo 51516
    BUILD: mypackage-1.1-35,draft_51516 [51516]
    Draft: YES
    State: COMPLETE
    ...

Once you have a build that is satisfactory, you can promote it.

::

    $ koji promote-build mypackage-1.1-35,draft_51516
    mypackage-1.1-35,draft_51516 has been promoted to mypackage-1.1-35

::

    $ koji buildinfo mypackage-1.1-35
    BUILD: mypackage-1.1-35 [51516]
    State: COMPLETE
    Built by: kojiuser
    Source: mypackage-1.1-35.src.rpm
    Volume: DEFAULT
    Task: 12082 build (f39-candidate, mypackage-1.1-35.src.rpm)
    Finished: Thu, 04 Jan 2024 20:02:18 EST
    Promoted by: kojiuser
    Promoted at: Tue, 09 Jan 2024 14:13:48 EST
    Tags: f39-candidate
    Extra: {'source': {'original_url': 'mypackage-1.1-35.src.rpm'}}
    RPMs:
    /mnt/koji/packages/mypackage/1.1/35,draft_51515/noarch/mypackage-1.1-35.noarch.rpm
    /mnt/koji/packages/mypackage/1.1/35,draft_51515/noarch/mypackage-devel-1.1-35.noarch.rpm
    /mnt/koji/packages/mypackage/1.1/35,draft_51515/noarch/mypackage-1.1-35.src.rpm



Dealing with duplicate NVRAs
----------------------------

The NVRAs for all *non-draft* rpms in Koji are required to be unique.
This is enforced by a database constraint.
However, this constraint does not apply to draft builds.
So, it is possible to have rpms of the same name in Koji if draft builds are used.

When Koji is asked to look up an rpm by name, it will report the non-draft rpm if it exists.
Otherwise, it will chose the matching draft rpm with the highest id.

Because of this, the *safest* way to specify an rpm is to use its rpm id.


Policies for draft builds
-------------------------

The ``is_draft`` policy test returns True if the build in question is a draft and False otherwise.
This is primarily useful in the ``tag`` policy to limit where draft builds can go.

Note that Koji's default policies do not include special rules for draft builds, so by default
draft builds can be used anywhere a regular build can.
Koji administrators can adjust their policies to match their own workflows.

For example, you could use the tag policy to restrict draft builds to only certain tags.
E.g.

::

    [policy]
    tag =
        is_draft && operation move tag :: {
            tag *-draft *-draft-* !! deny draft builds are only allowed in draft tags
        }
        ...

For further information on Koji policies,
see the :doc:`policy documentation <defining_hub_policies>`
