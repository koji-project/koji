Koji 1.19.1 Release notes
=========================

This is a small bugfix release for significant 1.19 bugs.

Client Changes
--------------

**Fix permissions to check tag/target/host permissions**

| PR: https://pagure.io/koji/pull-request/1733

In previous release the tag/target/host permissions were not being properly checked
by the client, this change includes those checks.



System Changes
--------------

**Fix hub reporting of incorrect ownership data**

| PR: https://pagure.io/koji/pull-request/1753

This change fixes package owner listing; in previous release, information returned by ``list-pkgs``
was incorrect.


**Fix issue with listing users with old versions of Postgres**

| PR: https://pagure.io/koji/pull-request/1751

``array_remove`` was removed and replaced to support Postgres versions older than 9.4.
