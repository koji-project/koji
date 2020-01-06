===============================
Koji Content Generator Metadata
===============================

This document describes the Koji Content Generator Metadata
Format (version 0). This is the metadata that should be provided by a
Content Generator in order for the content to be imported and managed by
Koji. If you have further questions about :doc:`Content
Generators <content_generators>`, please email
koji-devel@lists.fedorahosted.org.

Format
======

Content Generator Metadata for a single build is provided as a JSON map.
The map has four top-level entries:

-  metadata\_version: The version of the metadata format used. Currently
   must be 0.
-  build: A map containing information about the build.
-  buildroots: A list of maps, one for each environment in which build
   output was generated, containing information about that environment.
-  output: A list of maps, one map for each file that will be imported
   and managed by Koji.

metadata\_version
-----------------

This is an integer which indicates the version of the metadata format
contained in this file. It will start at 0 and be incremented as the
metadata format evolves.

build
-----

The build map contains the following entries:

-  name: The name of the build.
-  version: The version of the build.
-  release: The release of the build.
-  source: The SCM URL of the sources used in the build.
-  start\_time: The time the build started, in seconds since the epoch.
-  end\_time: The time the build was completed, in seconds since the
   epoch.
-  owner: The owner of the build task in username format. This field
   is optional.
-  build_id: Reserved build ID. This field is optional.
-  extra: A map of extra metadata associated with the build, which
   must include at least one of:

   - typeinfo: A map whose entries are the names of the build types used for
     this build, which are free form maps containing type-specific information
     for this build.
   - maven, win, or image: Legacy build type names which appear at this level
     instead of inside typeinfo.

buildroots
----------

Each map in the buildroots list contains the following entries:

-  id: An id for this buildroot entry. Only needs to be consistent
   within this file (it will be referenced by the output). Can be
   synthetic/generated/random.
-  host: Map containing information about the host where the build was
   run.

   -  os: The operating system that was running on the host.
   -  arch: The processor architecture of the host.

-  content\_generator: Map containing information about the Content
   Generator which ran the build.

   -  name: The short name of the Content Generator.
   -  version: The version of the Content Generator.

-  container: Map containing information about the container in which
   the build was run.

   -  type: The type of container that was used, eg. none, directory,
      chroot, mock-chroot, kvm, docker
   -  arch: The architecture of the container. May be different than the
      architecture of the host, eg. i686 container on x86\_64 host.

-  tools: List of maps containing information about the tools used to
   run the build. Each map contains:

   -  name: Name of the tool used.
   -  version: Version of the tool used.

-  components: List of maps containing information about content
   installed in the build environment (if any). Each map is guaranteed
   to contain a **type** field, which determines what other fields are
   present in the map. For maps where **type = rpm**, the following
   fields will be present:

   -  name: The rpm name.
   -  version: The rpm version.
   -  release: The rpm release.
   -  epoch: The rpm epoch.
   -  arch: The rpm arch.
   -  sigmd5: The SIGMD5 tag from the rpm header.
   -  signature: The signature used to sign the rpm (if any).

-  For maps where **type = file**, the following fields will be present:

   -  filename: The name of the file.
   -  filesize: The size of the file.
   -  checksum: The checksum of the file.
   -  checksum\_type: The checksum type used.

.. _metadata-kojifile:

-  For maps where **type = kojifile**, the following fields will be present:

   -  filename: The name of the file.
   -  filesize: The size of the file.
   -  checksum: The checksum of the file.
   -  checksum\_type: The checksum type used.
   -  nvr: Build nvr from which this file origins.
   -  archive\_id: ID of archive from specified build.

-  The format may be extended with other types in the future.
-  extra: A map containing information specific to the Content Generator
   that produced the files to import. For OSBS, the extra map should
   contain a osbs entry, which is a map with the following fields:

   -  build\_id: The ID of the build in OSBS.
   -  builder\_image\_id: The ID of the image in OSBS that was used to
      run the build.

output
------

Each map in the output list contains the following entries:

-  buildroot\_id: The id of the buildroot used to create this file. Must
   match an entry in the buildroots list.
-  filename: The name of the file.
-  filesize: The size of the file.
-  arch: The architecture of the file (if applicable).
-  checksum: The checksum of the file.
-  checksum\_type: The checksum type used.
-  type: The type of the file. Log files should use "log".
-  components: If the output file is composed from other units, those
   should be listed here. The format is the same as the **components**
   field of a buildroot map.
-  extra: Free-form, but should contain IDs that allow tracking the
   output back to the system in which it was generated (if that system
   retains a record of output). For docker, the extra map should contain
   a docker entry, which is a map with the following fields:

   -  id: The ID of the docker image produced in the repo used by the
      build tool
   -  parent\_id: The parent ID of the docker image produced (if
      applicable).
   -  repositories: A list of repository locations where the image is
      available.
   -  digests: A map of media type (such as
      "application/vnd.docker.distribution.manifest.v2+json") to
      manifest digest (a string usually starting "sha256:"), for each
      available media type.

Example Metadata JSON
=====================

The below JSON is based loosely on the output of a docker image build.

::

    {"metadata_version": 0,
     "build": {"name": "rhel-server-docker",
               "version": "7.1",
               "release": "4",
               "source": "git://git.engineering.redhat.com/users/vpavlin/tdl_templates.git#a14f145244",
               "extra": {},
               "start_time": 1423148398,
               "end_time": 1423148828,
               "owner": "jdoe"},
     "buildroots": [{"id": 1,
                     "host": {"os": "rhel-7",
                              "arch": "x86_64"},
                     "content_generator": {"name": "osbs",
                                           "version": "0.2"},
                     "container": {"type": "docker",
                                   "arch": "x86_64"},
                     "tools": [{"name": "docker",
                                "version": "1.5.0"}],
                     "components": [{"type": "rpm",
                                     "name": "glibc",
                                     "version": "2.17",
                                     "release": "75.el7",
                                     "epoch": null,
                                     "arch": "x86_64",
                                     "sigmd5": "a1b2c3...",
                                     "signature": "fd431d51"},
                                    {"type": "rpm",
                                     "name": "openssl",
                                     "version": "1.0.1e",
                                     "release": "42.el7",
                                     "epoch": null,
                                     "arch": "x86_64",
                                     "sigmd5": "d4e5f6...",
                                     "signature": "fd431d51"},
                                    {"type": "rpm",
                                     "name": "bind-libs",
                                     "version": "9.9.4",
                                     "release": "18.el7",
                                     "epoch": 32,
                                     "arch": "x86_64",
                                     "sigmd5": "987abc...",
                                     "signature": null},
                                    {"type": "rpm",
                                     "name": "python-urllib3",
                                     "version": "1.5",
                                     "release": "8.el7",
                                     "epoch": null,
                                     "arch": "noarch",
                                     "sigmd5": "123hgf...",
                                     "signature": null},
                                    {"type": "file",
                                     "filename": "jboss-eap-6.3.3-full-build.zip",
                                     "filesize": 12345678,
                                     "checksum": "5ec2f29c4e1c2e2aa6552836e236a158",
                                     "checksum_type": "md5"}],
                     "extra": {"osbs": {"build_id": 12345,
                                        "builder_image_id": 67890}}
                     }],
     "output": [{"buildroot_id": 1,
                "filename": "rhel-server-docker-7.1-4.x86_64.tar.xz",
                "filesize": 34440656,
                "arch": "x86_64",
                "checksum_type": "md5",
                "checksum": "275ae42a45cfedbdb0c0a1acc0b55a1b",
                "type": "docker-image",
                "components": "",
                "extra": {"docker": {"id": "987654...",
                                     "parent_id": "a1b2c3...",
                                     "repositories": ["repository.example.com/username/imagename:7.1-4",
                                                      "repository.example.com/username/imagename@sha256:100000...",
                                                      "repository.example.com/username/imagename@sha256:200000..."],
                                     "digests": {"application/vnd.docker.distribution.manifest.v1+json": "sha256:100000...",
                                                 "application/vnd.docker.distribution.manifest.v2+json": "sha256:200000..."}
                                     }}},
               {"buildroot_id": 1,
                "filename": "checkout.log",
                "filesize": 85724,
                "arch": "noarch",
                "checksum_type": "md5",
                "checksum": "a1b2c3...",
                "type": "log"},
               {"buildroot_id": 1,
                "filename": "os-indirection.log",
                "filesize": 27189,
                "arch": "noarch",
                "checksum_type": "md5",
                "checksum": "d4f5g6...",
                "type": "log"}
               ]
    }
