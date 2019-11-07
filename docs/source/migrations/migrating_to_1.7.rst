Migrating to Koji 1.7
=====================

.. reStructured Text formatted

The 1.7 release of Koji contains changes that will require a little extra
work when updating. These changes are:

* DB schema updates to support storage volumes
* The change from mod_python to mod_wsgi
* The introduction of a separate configuration file for koji-web
* Changes to url options

DB Schema Updates
-----------------

The 1.7 release adds two new tables to the database. The ``volume`` table tracks
the names of available storage volumes, and the ``tag_updates`` table tracks
changes to tags that are not easily calculated from other tables. There is
also a new field in the ``build`` table, ``volume_id``, which indicates which
volume a build is stored on.

As in previous releases, we provide a migration script that updates the
database.

::

    # psql koji koji  </usr/share/doc/koji-1.7.0/docs/schema-upgrade-1.5-1.7.sql


mod_python and mod_wsgi
-----------------------

Koji now defaults to using mod_wsgi to interface with httpd. Support for
mod_python is _deprecated_ and will disappear in a future version of Koji.
Koji administrators can opt to stay on mod_python for now, but some minor
configuration changes will be required.

Migrating to mod_wsgi
^^^^^^^^^^^^^^^^^^^^^

The mod_wsgi package is now required for both koji-hub and koji-web. Folks
running RHEL5 can find mod_wsgi in EPEL.

You will need to adjust your http config for both koji-hub and koji-web. Our
example config files default to mod_wsgi. To adapt your existing config, you
will need to:

* For both the koji-hub and koji-web/scripts directories:
    * add ``Options ExecCGI``
    * change ``SetHandler`` from mod_python to wsgi-script
* Ensure that the koji-web Alias points to wsgi_publisher.py
* If you have not already, migrate all koji-hub PythonOptions to hub.conf
* Migrate all koji-web PythonOptions to web.conf (see later section)

Staying on mod_python
^^^^^^^^^^^^^^^^^^^^^

Support for mod_python is _deprecated_ and will disappear in a future version
of Koji.

While we have made efforts to maintain mod_python compatibility, there are
a few configuration changes you will need to make.

The koji-hub http config should continue to function without modification.

The koji-web http config will, at minimum, require the following changes:

* Ensure that the koji-web ``Alias`` points to wsgi_publisher.py
* Change koji-web's ``PythonHandler`` setting to wsgi_publisher

Our example http configurations contain commented examples of mod_python
configuration.

Even if you stay on mod_python, we recommend that you migrate away from using
PythonOptions and place your configuration in web.conf and hub.conf.


Web Configuration
-----------------

Starting with version 1.7, koji-web uses a separate configuration file, rather
than PythonOptions embedded in the httpd config. The location of the new file
is:

::

    /etc/kojiweb/web.conf

The web.conf file is an ini-style configuration file. Options should be placed
in the [web] section. All previous options accepted via PythonOptions are
accepted in web.conf. Please see the example web.conf file.


Custom Config File Location
^^^^^^^^^^^^^^^^^^^^^^^^^^^

The location of web.conf can be specified in the httpd configuration. To
specify the location under mod_wsgi, use:

::

    SetEnv koji.web.ConfigFile /path/to/web.conf

Under mod_python, use:

::

    PythonOption koji.web.ConfigFile /path/to/web.conf

If you opt to stay on mod_python, the server will continue to process the old
PythonOptions. To ease migration, it does so by default unless the
koji.web.ConfigFile PythonOption is specified. In order to use web.conf under
mod_python, you *must* specify koji.web.ConfigFile in your http config.

We strongly recommend moving to web.conf. The server will issue a warning at
startup if web.conf is not in use.


Changes to url options
----------------------

The pkgurl option has been removed from the koji command line tool and from
the build daemon (kojid). The url for packages is deduced from the topurl
option, which should point to the top of the /mnt/koji tree.

Any config files that specify pkgurl (e.g. ~/.koji/config, /etc/koji.conf, or
/etc/kojid/kojid.conf) will need to be adjusted.

Similarly, the kojiweb config options KojiPackagesURL, KojiMavenURL, and
KojiImagesURL have been dropped in favor of the new option KojiFilesURL.


Additional Notes
----------------

Split Storage
^^^^^^^^^^^^^

Apart from the schema changes, no other migration steps are required for the
split storage feature. By default, builds are stored in the normal location.

Web Themes
^^^^^^^^^^

Using the old method (httpd aliases for koji static content) should continue
to work. For (brief) instructions on the new method, see the README file under
koji-web/static/themes.
