
Koji 1.34.3 Release notes
=========================

This is a security update to backport the fix for :doc:`../CVEs/CVE-2024-9427`
to Koji 1.34.


Migrating from Koji 1.34.x
--------------------------

No special actions are needed to migrate from earlier 1.34 point releases.


Security Fixes
--------------

**web: XSS vulnerability**

| CVE: :doc:`../CVEs/CVE-2024-9427`
| Issue: https://pagure.io/koji/issue/4211

An unsanitized input allows for an XSS attack. Javascript code from a malicious
link could be reflected in the resulting web page. At present, we do not
believe that this can be used to submit an action or make a change in Koji due
to existing XSS protections in the code. Even so, this is a serious issue and
we recommend applying this update promptly.


Other Changes
-------------

There are no other significant changes in this release.
All changes can be found in `the roadmap <https://pagure.io/koji/roadmap/1.34.3/>`_.
