
Koji 1.35.1 Release notes
=========================

All changes can be found in `the roadmap <https://pagure.io/koji/roadmap/1.35.1/>`_.
Most important changes are listed here.


Migrating from Koji 1.35.0
--------------------------

No special actions are needed.


Security Fixes
--------------

**web: XSS vulnerability**

| CVE: :doc:`../CVEs/CVE-2024-9427`
| Issue: https://pagure.io/koji/issue/4204

An unsanitized input allows for an XSS attack. Javascript code from a malicious
link could be reflected in the resulting web page. At present, we do not
believe that this can be used to submit an action or make a change in Koji due
to existing XSS protections in the code. Even so, this is a serious issue and
we recommend applying this update promptly.


Other Changes
-------------

There are no other significant changes in this release.
All changes can be found in `the roadmap <https://pagure.io/koji/roadmap/1.35.1/>`_.
