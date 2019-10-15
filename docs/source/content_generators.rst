=======================
Koji Content Generators
=======================

A Koji Content Generator is an external service that generates content
(jars, zips, tarballs, .npm, .wheel, .gem, etc) which is then passed to
Koji for management and delivery to other processes in the release
workflow. Content Generators can evolve independently of the Koji
codebase, enabling the build process to be more agile and flexible to
changing requirements and new technologies, while allowing Koji to
provide stable APIs and interfaces to other processes.

Along with the content to be managed by Koji, a Content Generator will
provide enough metadata to enable a reasonable level of auditing and
reproducibility. The exact data provided and the format used is being
discussed, but will include information like the upstream source URL,
build tools used, build environment contents, and any
container/virtualization technologies used.

The intention is that a team dedicated to managing a specific content
type will design and maintain their own Content Generator, in
coordination with the Koji developers. Once the Content Generator is
ready for production use it will be given permission to import content
and metadata it produces into Koji. Policies on the Koji hub will
validate imported content and metadata and ensure that it is complete
and consistent.

Requirements for writing a Content Generator
============================================

From an implementation perspective, content generators have wide
latitude in how they perform builds. To ensure sanity in the build
process, we strongly recommend that administrators of Koji systems set
policies about what content generators are allowed to do, and make sure
that those policies are followed before the content generator is granted
authorization in their Koji system.

Below are some examples of the sorts of policies that one might require.
Content Generators should be designed and implemented with these
requirements in mind. Please note that the list below is not complete.

Avoid Using the Host's Software
-------------------------------

During the building process, the code should avoid using the host's
installed software. The more reliance on installed software, the more
risk in the future that changes (such as upgrading a builder) will break
the build processes. Use mock chroots, VM guests, or containers wherever
possible to insulate against changes. Isolating the build environment
from the host environment makes reproducing work much easier and
predictable.

Source of build environment content
-----------------------------------

The build environment must come from somewhere. In a standard Koji
build, it comes from content already in Koji, or from configured
external repositories.

CG authors will likely want to pull content from sources outside of
Koji. Koji administrators should set a clear policy about which sources
are acceptable. The use of arbitrary sources can make it difficult or
impossible to reproduce build environments.

Binaries (or other compiled content) from Upstream May Not become included in output
------------------------------------------------------------------------------------

If tools or other content downloaded from external sources are used in
the build, they may not be included in CG build output, and may not be
imported into Koji. In other words, output must be built from sources in
the CG or Koji, not retrieved from the internet. Tools necessary to
build product content can be downloaded and cached in the CG.

Log all Transformations of Content
----------------------------------

When the content is building, as much should be logged as possible. In
addition to compilation, if the content goes through other
transformations, perhaps changing formats, that should be logged as
well. There can be no black-box transformations of the output. Imagine
having to figure out how a piece of content was built 5 years into the
future to understand the motivation behind this requirement. Details of
the build environment and tools used in the environment should be
recorded too.

Preserve All Inputs
-------------------

All inputs to a build task should be preserved either as logs, a
database, or as output of the build itself.

Preserve All Outputs
--------------------

Naturally the outputs of a build should be preserved too. Transient
artifacts are not strictly required, but if they're not onerous to
maintain, they should be included. It must not be necessary to further
transform the content to make it usable.

Do Not Use Caching Mechanisms
-----------------------------

Content Generators must build without caching mechanisms (in compilers
or DNF\ \|\ YUM) wherever possible. Caches make
reproducing results in the future more difficult, and also introduce
layers of indirection that can make debugging a build more difficult.
Consider the risk of re-shipping a security flaw that is compiled in
because an outdated library was cached in the Content Generator, this is
why we have this requirement.

Metadata
========

Metadata will be provided by the Content Generator as a JSON file. There
is a proposal of the :doc:`Content Generator
Metadata <content_generator_metadata>` format available for review.

.. _cg_api:

API
===

Relevant API calls for Content Generator are:

- ``CGImport(metadata, directory, token=None)``: This is basic integration point
  of Content Generator with koji. It is supplied with metadata as json encoded
  string or dict or filename of metadata described in previous chapter and
  directory with all uploaded content referenced from metadata. These files
  needs to be uploaded before ``CGImport`` is called.

  Optionally, ``token`` can be specified in case, that build ID reservation was
  done before.

- ``CGInitBuild(cg, data)``: It can be helpful in many cases to reserve NVR for
  future build before Content Generator evend starts building.  Especially, if
  there is some CI or other workflow competing for same NVRs.  This call creates
  special ``token`` which can be used to claim specific build (ID + NVR). Such
  claimed build will be displayed as BUILDING and can be used by ``CGImport``
  call later.

  As an input are here Content Generator name and `data` which is basically
  dictionary with name/version/release/epoch keys. Call will return a dict
  containing ``token`` and ``build_id``. ``token`` would be used in subsequent
  call of ``CGImport`` while ``build_id`` needs to be part of metadata (as item
  in ``build`` key).
