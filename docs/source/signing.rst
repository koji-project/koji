RPM Signing with Koji
=====================

What is a GPG keypair?
----------------------

A GPG keypair has a public key that you can share with the world and a private key that you keep secret.

Here are some example commands for working with RPM and GPG.

Example of generating a GPG keypair for testing::

    gpg --quick-generate-key security@example.com
    # For testing, simply press "Enter" when prompted for a password.

Exporting your public key::

    gpg --armor --export --output /path/to/my-signing-key.asc

Signing all RPMs in the current directory with this key::

    rpmsign --define "_gpg_name security@example.com" --addsign *.rpm

Inspecting an RPM signature
---------------------------

In order to install a signed RPM on clients, each client must trust (import)
the public GPG key into their RPMDB::

    rpm --import /path/to/my-signing-key.asc

*Example: No GPG signature at all (an unsigned RPM)*::

    rpm -Kv python3-cherrypy-18.6.0-1.fc33.noarch.rpm
    python3-cherrypy-18.6.0-1.fc33.noarch.rpm:
      Header SHA256 digest: OK
      Header SHA1 digest: OK
      Payload SHA256 digest: OK
      MD5 digest: OK

Note there are only "digest" fields here, no "Signature" fields since this RPM
is unsigned.

*Example: A GPG signature that rpmdb DOES trust*::

    rpm -Kv python3-cherrypy-18.4.0-4.fc32.noarch.rpm
    python3-cherrypy-18.4.0-4.fc32.noarch.rpm:
      Header V3 RSA/SHA256 Signature, key ID 12c944d0: OK
      Header SHA256 digest: OK
      Header SHA1 digest: OK
      Payload SHA256 digest: OK
      V3 RSA/SHA256 Signature, key ID 12c944d0: OK
      MD5 digest: OK

*Example: A GPG signature that rpmdb does NOT trust*::

    rpm -Kv python-cherrypy-18.6.0-1.el8.src.rpm
    python-cherrypy-18.6.0-1.el8.src.rpm:
      Header V4 RSA/SHA256 Signature, key ID 782096ac: NOKEY
      Header SHA256 digest: OK
      Header SHA1 digest: OK
      Payload SHA256 digest: OK
      V4 RSA/SHA256 Signature, key ID 782096ac: NOKEY
      MD5 digest: OK

Note the signature is syntatically valid here, but "NOKEY" here means RPMDB
does not trust the GPG key that signed this RPM.

A lower-level command that shows the signature on an RPM file (the
``RSAHEADER`` field piped through RPM's ``pgpsig`` formatter)::

    rpm -q --qf '%{NAME} %{RSAHEADER:pgpsig}\n' -p python-routes-2.5.1-1.el8.src.rpm

Learn more about RPM signatures and digests in `RPM's reference manual
<https://rpm-software-management.github.io/rpm/manual/signatures_digests.html>`_.

Uploading signed RPMs to Koji
-----------------------------

Koji does not sign RPMs. Instead, Koji imports RPMs that are signed with a separate key.

To sign an RPM from Koji, you should make a copy of the file, sign it
with the appropriate rpm command, and import the signature. Note that you
should not simply sign the file directly under /mnt/koji, as this causes an
inconsistency between the filesystem and the database (hence the copy step).

In this example, we download an unsigned build from Koji, then sign it, and
then upload the signed copy with ``koji import-sig``::

    koji download-build --debuginfo bash-5.0.17-2.fc32
    rpmsign --define "_gpg_name security@example.com" --addsign *.rpm
    koji import-sig *.rpm

The ``koji import-sig`` command uploads the signed RPM headers to the Koji
Hub, which stores the headers on disk alongside the main unsigned RPM.
It also writes out a full signed RPM.

Another variant is to import whole signed rpms (e.g. during :doc:`bootstrapping
<server_bootstrap>` via ``koji import`` command.) If such an imported rpm
contains an rpm signature, the import does not automatically write out a signed
copy for that signature (in contrast with ``import-sig``). The primary copy will
be the signed rpm, and the signature will be noted. If a signed copy is desired
(e.g. for generating :doc:`distrepos <exporting_repositories>`), you can use the
koji write-signed-rpm command.

Downloading a signed RPM from Koji
----------------------------------

Specify the ``--key`` option to ``koji download-build``::

    koji download-build --key=3AF362BAB bash-5.0.17-2.fc32

Signing a build with multiple keys
----------------------------------

Currently RPM's file format only allows one single GPG signature per file.

Koji allows users to upload multiple GPG signatures for a single RPM. it
stores each signature alongside the RPM build and splices the signature
headers in to generate full signed RPMs. Here are some use-cases of this
feature:

- Sign a set of RPMs with a "beta" key, and later sign those same RPMs with a
  "main" key.

- Sign the same Fedora RPMs with multiple keys, one per Fedora release.

- Sign the same CentOS RPMs with multiple keys, one per CentOS SIG.

- In Fedora, after the developers stop supporting a Fedora version like "30",
  they can delete the full signed packages, which are many hundreds of GB, and
  just keep the signatures, which are only a few bytes.
  https://lists.fedoraproject.org/archives/list/devel@lists.fedoraproject.org/message/RWILIHQJEKIQM5LAH7UJ7KMRPZEXCKQL/

Creating repos of signed RPMs
-----------------------------

You can put signed RPMs into Yum repos three different ways.

1. Create dist-repos manually with the ``koji dist-repo`` command, that takes
   a GPG key argument.

2. Install and configure the `tag2distrepo
   <https://pagure.io/releng/tag2distrepo>`_ hub plugin to automatically
   export dist-repos for certain tags.

3. Pungi can create signed repos ("composes").

See :doc:`Exporting repositories <exporting_repositories>` for more
information.

How to automate signing?
------------------------

For a small testing environment, you can simply sign RPMs with a GPG key on a
workstation and run ``koji import-sig``. This is not secure and it does not
scale.

See the `Sigil <https://pagure.io/sigul>`_ and `Robosignatory
<https://pagure.io/robosignatory>`_ projects for more advanced workflows.

Koji cryptography best-practices
--------------------------------

- Use HTTPS everywhere (kojihub + kojiweb)
- Understand checksums (md5)
- Understand signatures (GPG)

How do RPM signatures relate to HTTPS?
--------------------------------------

HTTPS is transport-layer security. When you install a package over HTTPS you
verify that:

* The web server is who they say they are
* The information the web server sends is private

As soon as you download that build or copy it to another location, those
security guarantees are lost.

In a release pipeline, you end up copying builds to many locations, and while
it's important to use HTTPS for copying, it's even more important to have a
strong cryptographic signature follow each build.

This means that even if someone or some thing mirrors your build elsewhere,
that signature will go along with the build. In the case of RPMs, the GPG
signatures are actually embedded in the RPMs themselves that we deliver to
users.

Another reason this is important is for image-based artifacts that might use
many RPMs. If you think of cloud images or container images where you're
delivering an image with "preinstalled" RPMs, if you use signed RPMs in the
images you distribute, you're providing an extra layer of security.

How do RPM signatures relate to IMA signing?
--------------------------------------------

IMA stands for `"Integrity Measurement Architecture"
<https://www.redhat.com/en/blog/how-use-linux-kernels-integrity-measurement-architecture>`_.
It's a separate type of signature. RHEL-9 is the first release to have IMA
signing enabled. The change is still `under discussion
<https://fedoraproject.org/wiki/Changes/Signed_RPM_Contents>`_ for Fedora.

IMA does not replace RPM signing. RPM signing is orthogonal to IMA. Packages
can be both RPM-signed and IMA signed at the same time.
