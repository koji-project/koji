# Enable Python 3 builds for Fedora + EPEL >5
# NOTE: do **NOT** change 'epel' to 'rhel' here, as this spec is also
%if 0%{?fedora} || 0%{?epel} > 5
%bcond_without python3
# If the definition isn't available for python3_pkgversion, define it
%{?!python3_pkgversion:%global python3_pkgversion 3}
%else
%bcond_with python3
%endif

# Compatibility with RHEL. These macros have been added to EPEL but
# not yet to RHEL proper.
# https://bugzilla.redhat.com/show_bug.cgi?id=1307190
%{!?__python2: %global __python2 /usr/bin/python2}
%{!?python2_sitelib: %global python2_sitelib %(%{__python2} -c "from distutils.sysconfig import get_python_lib; print(get_python_lib())")}
%{!?python2_sitearch: %global python2_sitearch %(%{__python2} -c "from distutils.sysconfig import get_python_lib; print(get_python_lib(1))")}
%{!?py2_build: %global py2_build %{expand: CFLAGS="%{optflags}" %{__python2} setup.py %{?py_setup_args} build --executable="%{__python2} -s"}}
%{!?py2_install: %global py2_install %{expand: CFLAGS="%{optflags}" %{__python2} setup.py %{?py_setup_args} install -O1 --skip-build --root %{buildroot}}}

%if 0%{?fedora} >= 21 || 0%{?redhat} >= 7
%global use_systemd 1
%else
%global use_systemd 0
%global install_opt TYPE=sysv
%endif

%define baserelease 1
#build with --define 'testbuild 1' to have a timestamp appended to release
%if "x%{?testbuild}" == "x1"
%define release %{baserelease}.%(date +%%Y%%m%%d.%%H%%M.%%S)
%else
%define release %{baserelease}
%endif
Name: koji
Version: 1.12.0
Release: %{release}%{?dist}
License: LGPLv2 and GPLv2+
# koji.ssl libs (from plague) are GPLv2+
Summary: Build system tools
Group: Applications/System
URL: https://pagure.io/koji
Source: https://releases.pagure.org/koji/koji-%{version}.tar.bz2
BuildRoot: %{_tmppath}/%{name}-%{version}-%{release}-root-%(%{__id_u} -n)
BuildArch: noarch
%if 0%{with python3}
Requires: python%{python3_pkgversion}-%{name} = %{version}-%{release}
Requires: python%{python3_pkgversion}-pycurl
Requires: python%{python3_pkgversion}-libcomps
%else
Requires: python2-%{name} = %{version}-%{release}
Requires: python2-pycurl
%if 0%{?fedora} || 0%{?rhel} >= 7
Requires: python2-libcomps
%endif
%endif
%if %{use_systemd}
BuildRequires: systemd
BuildRequires: pkgconfig
%endif

%description
Koji is a system for building and tracking RPMS.  The base package
contains shared libraries and the command-line interface.

%package -n python2-%{name}
Summary: Build system tools python library
%{?python_provide:%python_provide python2-%{name}}
BuildRequires: python2-devel
Requires: python-krbV >= 1.0.13
Requires: rpm-python
Requires: pyOpenSSL
Requires: python-requests
Requires: python-requests-kerberos
Requires: python-dateutil
Requires: python-six

%description -n python2-%{name}
desc

%if 0%{with python3}
%package -n python%{python3_pkgversion}-%{name}
Summary: Build system tools python library
%{?python_provide:%python_provide python%{python3_pkgversion}-%{name}}
BuildRequires: python%{python3_pkgversion}-devel
Requires: rpm-python%{python3_pkgversion}
Requires: python%{python3_pkgversion}-pyOpenSSL
Requires: python%{python3_pkgversion}-requests
Requires: python%{python3_pkgversion}-requests-kerberos
Requires: python%{python3_pkgversion}-dateutil
Requires: python%{python3_pkgversion}-six

%description -n python%{python3_pkgversion}-%{name}
desc
%endif

%package hub
Summary: Koji XMLRPC interface
Group: Applications/Internet
License: LGPLv2 and GPLv2
# rpmdiff lib (from rpmlint) is GPLv2 (only)
Requires: httpd
Requires: mod_wsgi
%if 0%{?fedora} >= 21 || 0%{?redhat} >= 7
Requires: mod_auth_gssapi
%endif
Requires: python-psycopg2
%if 0%{?rhel} == 5
Requires: python-simplejson
%endif
Requires: %{name} = %{version}-%{release}

%description hub
koji-hub is the XMLRPC interface to the koji database

%package hub-plugins
Summary: Koji hub plugins
Group: Applications/Internet
License: LGPLv2
Requires: %{name} = %{version}-%{release}
Requires: %{name}-hub = %{version}-%{release}
Requires: python-qpid >= 0.7
%if 0%{?rhel} >= 6
Requires: python-qpid-proton
%endif
%if 0%{?rhel} == 5
Requires: python-ssl
%endif
Requires: cpio

%description hub-plugins
Plugins to the koji XMLRPC interface

%package builder-plugins
Summary: Koji builder plugins
Group: Applications/Internet
License: LGPLv2
Requires: %{name} = %{version}-%{release}
Requires: %{name}-builder = %{version}-%{release}

%description builder-plugins
Plugins for the koji build daemon

%package builder
Summary: Koji RPM builder daemon
Group: Applications/System
License: LGPLv2 and GPLv2+
#mergerepos (from createrepo) is GPLv2+
Requires: %{name} = %{version}-%{release}
Requires: mock >= 0.9.14
Requires(pre): /usr/sbin/useradd
Requires: squashfs-tools
Requires: python2-multilib
%if %{use_systemd}
Requires(post): systemd
Requires(preun): systemd
Requires(postun): systemd
%else
Requires(post): /sbin/chkconfig
Requires(post): /sbin/service
Requires(preun): /sbin/chkconfig
Requires(preun): /sbin/service
%endif
Requires: /usr/bin/cvs
Requires: /usr/bin/svn
Requires: /usr/bin/git
Requires: python-cheetah
%if 0%{?rhel} == 5
Requires: createrepo >= 0.4.11-2
Requires: python-hashlib
Requires: python-createrepo
Requires: python-simplejson
%endif
%if 0%{?fedora} >= 9
Requires: createrepo >= 0.9.2
%endif

%description builder
koji-builder is the daemon that runs on build machines and executes
tasks that come through the Koji system.

%package vm
Summary: Koji virtual machine management daemon
Group: Applications/System
License: LGPLv2
Requires: %{name} = %{version}-%{release}
%if %{use_systemd}
Requires(post): systemd
Requires(preun): systemd
Requires(postun): systemd
%else
Requires(post): /sbin/chkconfig
Requires(post): /sbin/service
Requires(preun): /sbin/chkconfig
Requires(preun): /sbin/service
%endif
Requires: libvirt-python
Requires: libxml2-python
Requires: /usr/bin/virt-clone
Requires: qemu-img

%description vm
koji-vm contains a supplemental build daemon that executes certain tasks in a
virtual machine. This package is not required for most installations.

%package utils
Summary: Koji Utilities
Group: Applications/Internet
License: LGPLv2
Requires: python-psycopg2
Requires: %{name} = %{version}-%{release}
%if %{use_systemd}
Requires(post): systemd
Requires(preun): systemd
Requires(postun): systemd
%endif

%description utils
Utilities for the Koji system

%package web
Summary: Koji Web UI
Group: Applications/Internet
License: LGPLv2
Requires: httpd
Requires: mod_wsgi
%if 0%{?fedora} >= 21 || 0%{?redhat} >= 7
Requires: mod_auth_gssapi
%else
Requires: mod_auth_kerb
%endif
Requires: python-psycopg2
Requires: python-cheetah
Requires: %{name} = %{version}-%{release}
Requires: python-krbV >= 1.0.13

%description web
koji-web is a web UI to the Koji system.

%prep
%setup -q

%build

%install
rm -rf $RPM_BUILD_ROOT
make DESTDIR=$RPM_BUILD_ROOT %{?install_opt} install
%if 0%{with python3}
cd koji
make DESTDIR=$RPM_BUILD_ROOT PYTHON=python3 %{?install_opt} install
# alter python interpreter in koji CLI
sed -i 's/\#\!\/usr\/bin\/python/\#\!\/usr\/bin\/python3/' $RPM_BUILD_ROOT/usr/bin/koji
%endif

%clean
rm -rf $RPM_BUILD_ROOT

%files
%defattr(-,root,root)
%{_bindir}/*
%config(noreplace) /etc/koji.conf
%dir /etc/koji.conf.d
%doc docs Authors COPYING LGPL

%files -n python2-%{name}
%defattr(-,root,root)
%{python2_sitelib}/%{name}

%if 0%{with python3}
%files -n python%{python3_pkgversion}-koji
%{python3_sitelib}/%{name}
%endif

%files hub
%defattr(-,root,root)
%{_datadir}/koji-hub
%dir %{_libexecdir}/koji-hub
%{_libexecdir}/koji-hub/rpmdiff
%config(noreplace) /etc/httpd/conf.d/kojihub.conf
%dir /etc/koji-hub
%config(noreplace) /etc/koji-hub/hub.conf
%dir /etc/koji-hub/hub.conf.d

%files hub-plugins
%defattr(-,root,root)
%dir %{_prefix}/lib/koji-hub-plugins
%{_prefix}/lib/koji-hub-plugins/*.py*
%dir /etc/koji-hub/plugins
%config(noreplace) /etc/koji-hub/plugins/*.conf

%files builder-plugins
%defattr(-,root,root)
%dir /etc/kojid/plugins
%config(noreplace) /etc/kojid/plugins/*.conf
%dir %{_prefix}/lib/koji-builder-plugins
%{_prefix}/lib/koji-builder-plugins/*.py*

%files utils
%defattr(-,root,root)
%{_sbindir}/kojira
%if %{use_systemd}
%{_unitdir}/kojira.service
%else
%{_initrddir}/kojira
%config(noreplace) /etc/sysconfig/kojira
%endif
%dir /etc/kojira
%config(noreplace) /etc/kojira/kojira.conf
%{_sbindir}/koji-gc
%dir /etc/koji-gc
%config(noreplace) /etc/koji-gc/koji-gc.conf
%{_sbindir}/koji-shadow
%dir /etc/koji-shadow
%config(noreplace) /etc/koji-shadow/koji-shadow.conf

%files web
%defattr(-,root,root)
%{_datadir}/koji-web
%dir /etc/kojiweb
%config(noreplace) /etc/kojiweb/web.conf
%config(noreplace) /etc/httpd/conf.d/kojiweb.conf
%dir /etc/kojiweb/web.conf.d

%files builder
%defattr(-,root,root)
%{_sbindir}/kojid
%dir %{_libexecdir}/kojid
%{_libexecdir}/kojid/mergerepos
%if %{use_systemd}
%{_unitdir}/kojid.service
%else
%{_initrddir}/kojid
%config(noreplace) /etc/sysconfig/kojid
%endif
%dir /etc/kojid
%config(noreplace) /etc/kojid/kojid.conf
%attr(-,kojibuilder,kojibuilder) /etc/mock/koji

%pre builder
/usr/sbin/useradd -r -s /bin/bash -G mock -d /builddir -M kojibuilder 2>/dev/null ||:

%if %{use_systemd}

%post builder
%systemd_post kojid.service

%preun builder
%systemd_preun kojid.service

%postun builder
%systemd_postun kojid.service

%else

%post builder
/sbin/chkconfig --add kojid

%preun builder
if [ $1 = 0 ]; then
  /sbin/service kojid stop &> /dev/null
  /sbin/chkconfig --del kojid
fi
%endif

%files vm
%defattr(-,root,root)
%{_sbindir}/kojivmd
#dir %{_datadir}/kojivmd
%{_datadir}/kojivmd/kojikamid
%if %{use_systemd}
%{_unitdir}/kojivmd.service
%else
%{_initrddir}/kojivmd
%config(noreplace) /etc/sysconfig/kojivmd
%endif
%dir /etc/kojivmd
%config(noreplace) /etc/kojivmd/kojivmd.conf

%if %{use_systemd}

%post vm
%systemd_post kojivmd.service

%preun vm
%systemd_preun kojivmd.service

%postun vm
%systemd_postun kojivmd.service

%else

%post vm
/sbin/chkconfig --add kojivmd

%preun vm
if [ $1 = 0 ]; then
  /sbin/service kojivmd stop &> /dev/null
  /sbin/chkconfig --del kojivmd
fi
%endif

%if %{use_systemd}

%post utils
%systemd_post kojira.service

%preun utils
%systemd_preun kojira.service

%postun utils
%systemd_postun kojira.service

%else
%post utils
/sbin/chkconfig --add kojira
/sbin/service kojira condrestart &> /dev/null || :
%preun utils
if [ $1 = 0 ]; then
  /sbin/service kojira stop &> /dev/null || :
  /sbin/chkconfig --del kojira
fi
%endif

%changelog
* Tue Apr 18 2017 Mike McLean <mikem at redhat.com> - 1.12.0-1
- PR#373 backward-compatible try/except
- PR#365 handle buildroots with state=None
- PR#367 play nice with older hubs and new volume options
- PR#359 Add koji-tools link to docs
- PR#318 Signed repos, take two [dist repos]
- PR#200 Saving failed build trees
- PR#354 more runroot tests
- PR#232 Allow uploading files to non-default volumes
- PR#350 cli: clarify some "mismatch" warnings
- PR#351 cli: check # of args in handle_set_build_volume()
- PR#358 jenkins configuration update
- PR#260 Add debug and debug_xmlrpc to default koji config
- PR#304 unify KeyboardInterrupt behaviour for watch commands
- PR#341 Some more 2to3 python2.4 safe results
- PR#345 support removing extra values from tags
- PR#295 Set compatrequests defaults same as requests
- PR#348 remove unused function parse_timestamp
- PR#347 Return datetime objects in iso string format
- PR#343 Handle empty file upload
- PR#337 cli: move list-permissions to info category
- PR#332 remove has_key (not working in python3)
- PR#336 use alabaster theme for docs
- PR#333 Fix README link to mash project
- PR#331 use new exception syntax
- PR#330 formatting typo
- PR#226 print statement -> print function
- PR#319 Added support for CG provided owner
- PR#324 jenkins' docs
- PR#326 use multicall for clone tag
- PR#283 wrap sending email in try except
- PR#323 Honor excludearch and exclusivearch for noarch builds
- PR#322 fix encoding when parsing json data on the hub
- PR#278 mock_output.log not included with logs when importing rpm builds
- PR#321 hub: enforce strict in get_user()
- PR#309 Make --can-fail option working for make-image
- PR#243 add TrustForwardedIP and CheckClientIP for hubs behind proxies
- PR#307 Fix options.force in import_comps
- PR#308 fix a syntax error introduced by commit 6f4c576
- PR#303 check http request status before attempting to decode response
- PR#317 docs update - krbV configuration
- PR#310 Fix koji-devel mailing list address
- PR#311 Add indirectionimage to pull-down menu in webui
- PR#313 docs typo
- PR#316 update test requirements docs
- PR#281 web.conf options for specifying which methods will appear in filter
- PR#291 Missing --can-fail option for spin-appliance
- PR#209 add disttag handling to get_next_release
- PR#262 koji-shadow: allow use without certs
- PR#297 Fixed minor typo in writing koji code doc
- PR#289 Don't fail on unimported krbV
- PR#287 Update content generator metadata documentation
- PR#223 convert the packages page to use paginateMethod()
- PR#240 Convert from pygresql to psycopg2
- PR#239 Allow principal and keytab in cli config
- PR#263 Error message for missing certificates
- PR#274 Fix kojiweb error using getfile to download non-text files
- PR#177 allow tasks to fail on some arches for images/lives/appliances
- PR#264 unify CLI parsing of multiple architectures
- PR#265 fix poll_interval ref in list-history cmd
- PR#272 fix default values for buildroot.container_type
- PR#242 Make tests compatible with rhel7/centos7
- PR#267 more direct tag functions for the hub
- PR#256 update url and source in spec
- PR#257 Clarify purpose of cfgmap
- PR#245 Rewrite koji.util.rmtree to avoid forming long paths
- PR#244 Add krb_rdns to koji-shadow
- PR#246 Revert "default krb_rdns to True"
- PR#248 Make koji-gc also work with principal and keytab
- PR#253 Updated links in docs/code
- PR#254 Extended clone-tag
- PR#83 add support for putting scripts just before the closing </body> tag
- PR#141 Don't hide results in kojiweb
- PR#225 Also set WSGIApplicationGroup to %{GLOBAL} for the web
- PR#238 make the tlstimeout class compatible with newer versions of qpid

* Thu Dec  8 2016 Mike McLean <mikem at redhat.com> - 1.11.0-1
- content generator support
- generic build type support (btypes)
- use python-requests for client connections
- support gssapi auth
- unit tests
- protonmsg messaging plugin
- lots of code cleanup
- better documentation
- support building images with LiveMedia
- many other fixes and enhancements

* Thu Oct 29 2015 Mike McLean <mikem at redhat.com> - 1.10.1-1
- fixes for SSL errors
- add support for Image Factory generation of VMWare Fusion Vagrant boxes
- cli: add download-task command
- docs: Document how to write a plugin
- fix for a rare deadlock issue in taskSetWait
- use encode_int on rpm sizes
- check for tag existence in add-pkg
- Remove koji._forceAscii (unused)
- Resolve the canonical hostname when constructing the Kerberos server principal
- don't omit debuginfos on buildinfo page
- correct error message in fastUpload
- Check task method before trying to determine "scratch" status.

* Tue Jul 14 2015 Mike McLean <mikem at redhat.com> - 1.10.0-1
- 1.10.0 release

* Mon Mar 24 2014 Mike McLean <mikem at redhat.com> - 1.9.0-1
- 1.9.0 release

* Mon Apr  1 2013 Mike McLean <mikem at redhat.com> - 1.8.0-1
- refactor how images are stored and tracked (images as builds)
- delete repos in background
- limit concurrent maven regens
- let kojira delete repos for deleted tags
- check for a target before waiting on a repo
- don't append to artifact_relpaths twice in the case of Maven builds
- Use standard locations for maven settings and local repository
- Specify altDeploymentRepository for Maven in settings.xml NOT on command line
- rather than linking to each artifact from the Maven repo, link the version directory
- handle volumes in maven repos
- fix integer overflow issue in checkUpload handler
- koji-shadow adjustments
- change default ssl timeout to 60 seconds
- rewrite ensuredir function to avoid os.makedirs race
- rename -pkg commands to -build
- implement remove-pkg for the cli
- a little more room to edit host comments
- use wsgi.url_scheme instead of HTTPS
- handle relative-to-koji urls in mergerepos

* Mon Nov 19 2012 Mike McLean <mikem at redhat.com> - 1.7.1-1
- improved upload mechanism
- koji-shadow enhancements
- handle multiple topurl values in kojid
- fix form handling
- mount all of /dev for image tasks
- avoid error messages on canceled/reassigned tasks
- handle unauthenticated case in moshimoshi
- fix the tag_updates query in tag_changed_since_event
- stop tracking deleted repos in kojira
- don't die on malformed tasks
- fix bugs in our relpath backport
- avoid baseurl option in createrepo
- message bus plugin: use timeout and heartbeat
- add maven and win to the supported cli search types
- remove latest-by-tag command
- fix noreplace setting for web.conf
- add sanity checks to regen-repo command
- debuginfo and source options for regen-repo command
- make taginfo command compatible with older koji servers

* Thu May 31 2012 Mike McLean <mikem at redhat.com> - 1.7.0-1
- mod_wsgi support
- mod_python support deprecated
- kojiweb configuration file (web.conf)
- split storage support (build volumes)
- configurable resource limits (hub, web, and kojid)
- drop pkgurl in favor of topurl
- better approach to web themes
- more helpful policy errors
- clearer errors when rpc args do not match function signature
- avoid retry errors on some common builder calls
- don't rely on pgdb._quoteparams
- avoid hosts taking special arch tasks they cannot handle
- kojid: configure yum proxy
- kojid: configure failed buildroot lifetime
- kojid: literal_task_arches option
- support for arm hardware floating point arches
- maven build options: goals, envs, extra packages
- store Maven build output under the standard build directory
- make the list of files ignored in the local Maven repo configurable
- add Maven information to taginfo
- make kojira more efficient using multicalls and caching
- speed up kojira startup
- kojira: configurable sleep time
- kojira: count untracked newRepo tasks towards limits
- kojira: limit non-waiting newRepo tasks
- gssapi support in the messagebus plugin
- grant-permission --new
- improved argument display for list-api command
- moshimoshi
- download task output directly from KojiFilesURL, rather than going through getfile
- option to show buildroot data in rpminfo command
- show search help on blank search command
- wait-repo: wait for the build(s) to be the latest rather than just present

* Thu Dec 16 2010 Mike McLean <mikem at redhat.com> - 1.6.0-1
- extend debuginfo check to cover newer formats
- ignore tasks that TaskManager does not have a handler for
- avoid possible traceback on ^c
- graceful mass builder restart
- no longer issue condrestart in postinstall scriptlet
- fix ssl connections for python 2.7
- more sanity checks on wait-repo arguments (ticket#192)
- maven: only treat files ending in .patch as patch files
- maven: retain ordering so more recent builds will take precedence
- enable passing options to Maven
- maven: use strict checksum checking

* Thu Nov 11 2010 Mike McLean <mikem at redhat.com> - 1.5.0-1
- koji vm daemon for executing certain tasks in virtual machine
- major refactoring of koji daemons
- support for complete history query (not just tag operations)
- allow filtering tasks by channel in webui
- rename-channel and remove-channel commands
- clean up tagBuild checks (rhbz#616839)
- resurrect import-comps command
- utf8 encoding fixes
- allow getfile to handle files > 2G
- update the messagebus plugin to use the new qpid.messaging API
- rpm2maven plugin: use Maven artifacts from rpm builds in Koji's Maven repos
- log mock output

* Thu Jul  8 2010 Mike McLean <mikem at redhat.com> - 1.4.0-1
- Merge mead branch: support for building jars with Maven *
- support for building appliance images *
- soft dependencies for LiveCD/Appliance features
- smarter prioritization of repo regenerations
- package list policy to determine if package list changes are allowed
- channel policy to determine which channel a task is placed in
- edit host data via webui
- description and comment fields for hosts *
- cleaner log entries for kojihub
- track user data in versioned tables *
- allow setting retry parameters for the cli
- track start time for tasks *
- allow packages built from the same srpm to span multiple external repos
- make the command used to fetch sources configuable per repo
- kojira: remove unexpected directories
- let kojid to decide if it can handle a noarch task
- avoid extraneous ssl handshakes
- schema changes to support starred items

* Tue Nov 10 2009 Mike Bonnet <mikeb@redhat.com> - 1.3.2-1
- support for LiveCD creation
- new event-based callback system

* Fri Jun 12 2009 Mike Bonnet <mikeb@redhat.com> - 1.3.1-2
- use <mirrorOf>*</mirrorOf> now that Maven 2.0.8 is available in the buildroots
- retrieve Maven info for a build from the top-level pom.xml in the source tree
- allow specifying one or more Maven profiles to be used during a build

* Fri Feb 20 2009 Mike McLean <mikem at redhat.com> 1.3.1-1
- external repo urls rewritten to end with /
- add schema file for upgrades from 1.2.x to 1.3
- explicitly request sha1 for backward compatibility with older yum
- fix up sparc arch handling

* Wed Feb 18 2009 Mike McLean <mikem at redhat.com> 1.3.0-1
- support for external repos
- support for noarch subpackages
- support rpms with different signatures and file digests
- hub configuration file
- drop huge tables from database
- build srpms in chroots
- hub policies
- limited plugin support
- limited web ui theming
- many miscellaneous enhancements and bugfixes
- license fields changed to reflect code additions

* Mon Aug 25 2008 Mike McLean <mikem@redhat.com> 1.2.6-1
- fix testbuild conditional [downstream]
- fix license tag [downstream]
- bump version
- more robust client sessions
- handle errors gracefully in web ui
- koji-gc added to utils subpackage
- skip sleep in kojid after taking a task
- new dir layout for task workdirs (avoids large directories)
- unified boolean option parsing in kojihub
- new ServerOffline exception
- other miscellaneous fixes

* Fri Jan 25 2008 jkeating <jkeating@redhat.com> 1.2.5-1
- Put createrepo arguments in correct order

* Thu Jan 24 2008 jkeating <jkeating@redhat.com> 1.2.4-1
- Use the --skip-stat flag in createrepo calls.
- canonicalize tag arches before using them (dgilmore)
- fix return value of delete_build
- Revert to getfile urls if the task is not successful in emails
- Pass --target instead of --arch to mock.
- ignore trashcan tag in prune-signed-copies command
- add the "allowed_scms" kojid parameter
- allow filtering builds by the person who built them

* Fri Dec 14 2007 jkeating <jkeating@redhat.com> 1.2.3-1
- New upstream release with lots of updates, bugfixes, and enhancements.

* Tue Jun  5 2007 Mike Bonnet <mikeb@redhat.com> - 1.2.2-1
- only allow admins to perform non-scratch builds from srpm
- bug fixes to the cmd-line and web UIs

* Thu May 31 2007 Mike Bonnet <mikeb@redhat.com> - 1.2.1-1
- don't allow ExclusiveArch to expand the archlist (bz#239359)
- add a summary line stating whether the task succeeded or failed to the end of the "watch-task" output
- add a search box to the header of every page in the web UI
- new koji download-build command (patch provided by Dan Berrange)

* Tue May 15 2007 Mike Bonnet <mikeb@redhat.com> - 1.2.0-1
- change version numbering to a 3-token scheme
- install the koji favicon

* Mon May 14 2007 Mike Bonnet <mikeb@redhat.com> - 1.1-5
- cleanup koji-utils Requires
- fix encoding and formatting in email notifications
- expand archlist based on ExclusiveArch/BuildArchs
- allow import of rpms without srpms
- commit before linking in prepRepo to release db locks
- remove exec bit from kojid logs and uploaded files (patch by Enrico Scholz)

* Tue May  1 2007 Mike Bonnet <mikeb@redhat.com> - 1.1-4
- remove spurious Requires: from the koji-utils package

* Tue May  1 2007 Mike Bonnet <mikeb@redhat.com> - 1.1-3
- fix typo in BuildNotificationTask (patch provided by Michael Schwendt)
- add the --changelog param to the buildinfo command
- always send email notifications to the package builder and package owner
- improvements to the web UI

* Tue Apr 17 2007 Mike Bonnet <mikeb@redhat.com> - 1.1-2
- re-enable use of the --update flag to createrepo

* Mon Apr 09 2007 Jesse Keating <jkeating@redhat.com> 1.1-1
- make the output listPackages() consistent regardless of with_dups
- prevent large batches of repo deletes from holding up regens
- allow sorting the host list by arches

* Mon Apr 02 2007 Jesse Keating <jkeating@redhat.com> 1.0-1
- Release 1.0!

* Wed Mar 28 2007 Mike Bonnet <mikeb@redhat.com> - 0.9.7-4
- set SSL connection timeout to 12 hours

* Wed Mar 28 2007 Mike Bonnet <mikeb@redhat.com> - 0.9.7-3
- avoid SSL renegotiation
- improve log file handling in kojid
- bug fixes in command-line and web UI

* Sun Mar 25 2007 Mike Bonnet <mikeb@redhat.com> - 0.9.7-2
- enable http access to packages in kojid
- add Requires: pyOpenSSL
- building srpms from CVS now works with the Extras CVS structure
- fixes to the chain-build command
- bug fixes in the XML-RPC and web interfaces

* Tue Mar 20 2007 Jesse Keating <jkeating@redhat.com> - 0.9.7-1
- Package up the needed ssl files

* Tue Mar 20 2007 Jesse Keating <jkeating@redhat.com> - 0.9.6-1
- 0.9.6 release, mostly ssl auth stuff
- use named directories for config stuff
- remove -3 requires on creatrepo, don't need that specific anymore

* Tue Feb 20 2007 Jesse Keating <jkeating@redhat.com> - 0.9.5-8
- Add Authors COPYING LGPL to the docs of the main package

* Tue Feb 20 2007 Jesse Keating <jkeating@redhat.com> - 0.9.5-7
- Move web files from /var/www to /usr/share
- Use -p in install calls
- Add rpm-python to requires for koji

* Mon Feb 19 2007 Jesse Keating <jkeating@redhat.com> - 0.9.5-6
- Clean up spec for package review

* Sun Feb 04 2007 Mike McLean <mikem@redhat.com> - 0.9.5-1
- project renamed to koji
