Koji 1.16.1 Release Notes
=========================

Koji 1.16.1 is a point release for Koji 1.16. The major changes include:

- Allow target info to be read for different type tasks in channel policy.
- Create symlinks for builds imported onto non-default volumes.
- Fix RPMdiff issues found in Koji 1.16.0.

Please see: :doc:`release_notes_1.16`

Issues fixed in 1.16.1
----------------------

- `Issue 847 <https://pagure.io/koji/issue/847>`_ --
  spin-livecd failed with "Could not resolve host"

- `Issue 932 <https://pagure.io/koji/issue/932>`_ --
  Fix use_host_resolv with new mock version

- `Issue 1010 <https://pagure.io/koji/issue/1010>`_ --
  koji fails runroot because of `UnicodeDecodeError`

- `Issue 998 <https://pagure.io/koji/issue/998>`_ --
  cancel build doesn't work for images

- `Issue 994 <https://pagure.io/koji/issue/994>`_ --
  rpmdiff calculate wrong results

- `Issue 1025 <https://pagure.io/koji/issue/1025>`_ --
  missing default volume symlink for imported builds affected by volume policy

- `Issue 1007 <https://pagure.io/koji/issue/1007>`_ --
  decode_args() might result in --package parameter missing in runroot command

- `Issue 150 <https://pagure.io/koji/issue/150>`_ --
  no target info in channel policy for non-rpm tasks

- `PR: 973 <https://pagure.io/koji/pull-request/973>`_ --
  Check empty arches before spawning dist-repo

- `Issue 958 <https://pagure.io/koji/issue/958>`_ --
  Notification for tagBuildBypass is writing message untagged from, expected message tagged into

- `Issue 968 <https://pagure.io/koji/issue/968>`_ --
  Default enable python3 on RHEL8

- `Issue 916 <https://pagure.io/koji/issue/916>`_ --
  `clone-tag` doesn't preserve tagging order

- `Issue 949 <https://pagure.io/koji/issue/949>`_ --
  cli: [rpminfo] KeyError: 'license' for external RPM

- `Issue 876 <https://pagure.io/koji/issue/876>`_ --
  koji clone-tag raises "UnboundLocalError"

- `Issue 945 <https://pagure.io/koji/issue/945>`_ --
  Koji build fail due to ambiguous python shebang
