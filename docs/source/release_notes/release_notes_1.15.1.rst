Koji 1.15.1 Release Notes
=========================

Koji 1.15.1 is a bugfix release for Koji 1.15. The most important change
is the fix for :doc:`../CVEs/CVE-2018-1002150`.

Please see: :doc:`release_notes_1.15`

Issues fixed in 1.15.1
----------------------

- `Issue 850 <https://pagure.io/koji/issue/850>`_ --
  CVE-2018-1002150

- `Issue 846 <https://pagure.io/koji/issue/846>`_ --
  error occurs in SCM.get_source since subprocess.check_output is not supported by python 2.6-

- `Issue 724 <https://pagure.io/koji/issue/724>`_ --
  buildNotification of wrapperRPM fails because of task["label"] is None

- `Issue 786 <https://pagure.io/koji/issue/786>`_ --
  buildSRPMFromSCM tasks fail on koji 1.15

- `Issue 803 <https://pagure.io/koji/issue/803>`_ --
  Email notifications makes build tasks fail with "KeyError: 'users_usertype'"

- `Issue 742 <https://pagure.io/koji/issue/742>`_ --
  dict key access fail in koji_cli.commands._build_image

- `Issue 811 <https://pagure.io/koji/issue/811>`_ --
  AttributeError: 'dict' object has no attribute 'hub.checked_md5'

- `Issue 813 <https://pagure.io/koji/issue/813>`_ --
  cg imports fail with "Unsupported checksum type"
