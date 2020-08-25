%bcond_without python3
%bcond_without python2
%global _python_bytecompile_extra 0

# We can build varying amounts of Koji for python2 and python3 based on
# the py[23]_support macro values. Valid values are:
#   undefined or 0 -- do not build
#   1 -- build just the cli and lib
#   2 -- build everything we can
# For executable scripts, py3 wins if we build it
# The following rules tweak these settings based on options and environment

# Default to building both fully
%define py2_support 2
%define py3_support 2

%if 0%{?rhel} >= 8
# and no python2 on rhel8+
%define py2_support 0
%else
%if 0%{?rhel}
# No python3 for older rhel
%define py3_support 0
%endif
%endif

%if 0%{?fedora} >= 33
# no py2 after F33
%define py2_support 0
%define py3_support 2
%else
%if 0%{?fedora} >= 30
%define py2_support 1
%define py3_support 2
%else
%if 0%{?fedora}
# match what the older Fedoras already have
%define py2_support 2
%define py3_support 1
%endif
%endif
%endif

# Lastly enforce the bcond parameters
%if %{without python2}
%define py2_support 0
%endif
%if %{without python3}
%define py3_support 0
%endif

%if ! %{py2_support}
# use python3
%define __python %{__python3}
%endif

# Compatibility with RHEL. These macros have been added to EPEL but
# not yet to RHEL proper.
# https://bugzilla.redhat.com/show_bug.cgi?id=1307190
%{!?__python2: %global __python2 /usr/bin/python2}
%{!?python2_sitelib: %global python2_sitelib %(%{__python2} -c "from distutils.sysconfig import get_python_lib; print(get_python_lib())")}
%{!?python2_sitearch: %global python2_sitearch %(%{__python2} -c "from distutils.sysconfig import get_python_lib; print(get_python_lib(1))")}
%{!?py2_build: %global py2_build %{expand: CFLAGS="%{optflags}" %{__python2} setup.py %{?py_setup_args} build --executable="%{__python2} -s"}}
%{!?py2_install: %global py2_install %{expand: CFLAGS="%{optflags}" %{__python2} setup.py %{?py_setup_args} install -O1 --skip-build --root %{buildroot}}}

# If the definition isn't available for python3_pkgversion, define it
%{?!python3_pkgversion:%global python3_pkgversion 3}

%if 0%{?fedora} || 0%{?rhel} >= 7
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
Version: 1.22.1
Release: %{release}%{?dist}
License: LGPLv2 and GPLv2+
# the included arch lib from yum's rpmUtils is GPLv2+
Summary: Build system tools
Group: Applications/System
URL: https://pagure.io/koji
Source: https://releases.pagure.org/koji/koji-%{version}.tar.bz2
BuildRoot: %{_tmppath}/%{name}-%{version}-%{release}-root-%(%{__id_u} -n)
BuildArch: noarch
%if 0%{py3_support}
Requires: python%{python3_pkgversion}-%{name} = %{version}-%{release}
Requires: python%{python3_pkgversion}-libcomps
%else
Requires: python2-%{name} = %{version}-%{release}
%if 0%{?fedora} || 0%{?rhel} >= 7
Requires: python-libcomps
%endif
%endif
%if %{use_systemd}
BuildRequires: systemd
BuildRequires: pkgconfig
%endif

%description
Koji is a system for building and tracking RPMS.  The base package
contains shared libraries and the command-line interface.

%if 0%{py2_support}
%package -n python2-%{name}
Summary: Build system tools python library
%{?python_provide:%python_provide python2-%{name}}
%if 0%{?fedora} >= 30
BuildRequires: python2-devel
%else
BuildRequires: python-devel
%endif
%if 0%{?fedora} || 0%{?rhel} >= 8
Requires: python2-rpm
%else
Requires: rpm-python
%endif
Requires: pyOpenSSL
Requires: python-requests
Requires: python-requests-kerberos
Requires: python-dateutil
Requires: python-six

%description -n python2-%{name}
desc
%endif

%if 0%{py3_support}
%package -n python%{python3_pkgversion}-%{name}
Summary: Build system tools python library
%{?python_provide:%python_provide python%{python3_pkgversion}-%{name}}
BuildRequires: python%{python3_pkgversion}-devel
%if 0%{?fedora} || 0%{?rhel} >= 8
Requires: python%{python3_pkgversion}-rpm
%else
Requires: rpm-python%{python3_pkgversion}
%endif
Requires: python%{python3_pkgversion}-pyOpenSSL
Requires: python%{python3_pkgversion}-requests
%if 0%{?fedora} >= 32
Requires: python%{python3_pkgversion}-requests-gssapi
%else
Requires: python%{python3_pkgversion}-requests-kerberos
%endif
Requires: python%{python3_pkgversion}-dateutil
Requires: python%{python3_pkgversion}-six

%description -n python%{python3_pkgversion}-%{name}
desc
%endif

%if 0%{py2_support}
%package -n python2-%{name}-cli-plugins
Summary: Koji client plugins
Group: Applications/Internet
License: LGPLv2
Requires: python2-%{name} = %{version}-%{release}
Obsoletes: python2-%{name}-sidetag-plugin-cli < %{version}-%{release}
Provides: python2-%{name}-sidetag-plugin-cli = %{version}-%{release}

%description -n python2-%{name}-cli-plugins
Plugins to the koji command-line interface
%endif

%if 0%{py3_support}
%package -n python%{python3_pkgversion}-%{name}-cli-plugins
Summary: Koji client plugins
Group: Applications/Internet
License: LGPLv2
Requires: python%{python3_pkgversion}-%{name} = %{version}-%{release}
Obsoletes: python%{python3_pkgversion}-%{name}-sidetag-plugin-cli < %{version}-%{release}
Provides: python%{python3_pkgversion}-%{name}-sidetag-plugin-cli = %{version}-%{release}

%description -n python%{python3_pkgversion}-%{name}-cli-plugins
Plugins to the koji command-line interface
%endif

%if 0%{py3_support} > 1
%package hub
Summary: Koji XMLRPC interface
Group: Applications/Internet
License: LGPLv2
Requires: %{name} = %{version}-%{release}
Requires: %{name}-hub-code
%if 0%{?fedora} || 0%{?rhel} > 7
Suggests: python%{python3_pkgversion}-%{name}-hub
Suggests: python%{python3_pkgversion}-%{name}-hub-plugins
%endif

%description hub
koji-hub is the XMLRPC interface to the koji database

%package -n python%{python3_pkgversion}-%{name}-hub
Summary: Koji XMLRPC interface
Group: Applications/Internet
License: LGPLv2 and GPLv2
# rpmdiff lib (from rpmlint) is GPLv2 (only)
Requires: httpd
Requires: python%{python3_pkgversion}-mod_wsgi
%if 0%{?fedora} || 0%{?rhel} >= 7
Requires: mod_auth_gssapi
%endif
Requires: python%{python3_pkgversion}-psycopg2
Requires: python%{python3_pkgversion}-%{name} = %{version}-%{release}
# py2 xor py3
Provides: %{name}-hub-code = %{version}-%{release}

%description -n python%{python3_pkgversion}-%{name}-hub
koji-hub is the XMLRPC interface to the koji database

%package hub-plugins
Summary: Koji hub plugins
Group: Applications/Internet
License: LGPLv2
Requires: %{name}-hub-plugins-code = %{version}-%{release}
%if 0%{?fedora} || 0%{?rhel} > 7
Suggests: python%{python3_pkgversion}-%{name}-hub-plugins
%endif

%description hub-plugins
Plugins to the koji XMLRPC interface

%package -n python%{python3_pkgversion}-%{name}-hub-plugins
Summary: Koji hub plugins
Group: Applications/Internet
License: LGPLv2
Requires: python%{python3_pkgversion}-%{name}-hub = %{version}-%{release}
Requires: python%{python3_pkgversion}-qpid-proton
Requires: cpio
Provides: %{name}-hub-plugins-code = %{version}-%{release}
Obsoletes: python%{python3_pkgversion}-%{name}-sidetag-plugin-hub < %{version}-%{release}
Provides: python%{python3_pkgversion}-%{name}-sidetag-plugin-hub = %{version}-%{release}

%description -n python%{python3_pkgversion}-%{name}-hub-plugins
Plugins to the koji XMLRPC interface
%endif

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
Requires: mock >= 0.9.14
Requires(pre): /usr/sbin/useradd
Requires: squashfs-tools
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
Requires: createrepo >= 0.9.2
%if 0%{py3_support} > 1
Requires: python%{python3_pkgversion}-%{name} = %{version}-%{release}
Requires: python%{python3_pkgversion}-librepo
Requires: python%{python3_pkgversion}-multilib
Requires: python%{python3_pkgversion}-cheetah
%else
Requires: python2-%{name} = %{version}-%{release}
Requires: python2-multilib
Requires: python-cheetah
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
%if 0%{py3_support} > 1
Requires: python%{python3_pkgversion}-libvirt
Requires: python%{python3_pkgversion}-libxml2
%else
Requires: libvirt-python
Requires: libxml2-python
%endif
Requires: /usr/bin/virt-clone
Requires: qemu-img

%description vm
koji-vm contains a supplemental build daemon that executes certain tasks in a
virtual machine. This package is not required for most installations.

%package utils
Summary: Koji Utilities
Group: Applications/Internet
License: LGPLv2
Requires: %{name} = %{version}-%{release}
%if 0%{py3_support} > 1
Requires: python%{python3_pkgversion}-psycopg2
Obsoletes: python%{python3_pkgversion}-koji-sidetag-plugin-tools < %{version}-%{release}
Provides: python%{python3_pkgversion}-koji-sidetag-plugin-tools = %{version}-%{release}
%else
Requires: python-psycopg2
Obsoletes: python2-koji-sidetag-plugin-tools < %{version}-%{release}
Provides: python2-koji-sidetag-plugin-tools = %{version}-%{release}
%endif
%if %{use_systemd}
Requires(post): systemd
Requires(preun): systemd
Requires(postun): systemd
%endif

%description utils
Utilities for the Koji system

%if 0%{py3_support} > 1
%package web
Summary: Koji Web UI
Group: Applications/Internet
License: LGPLv2
Requires: %{name} = %{version}-%{release}
Requires: %{name}-web-code = %{version}-%{release}
%if 0%{?fedora} || 0%{?rhel} > 7
Suggests: python%{python3_pkgversion}-%{name}-web
%endif

%description web
koji-web is a web UI to the Koji system.

%package -n python%{python3_pkgversion}-%{name}-web
Summary: Koji Web UI
Group: Applications/Internet
License: LGPLv2
%{?python_provide:%python_provide python%{python3_pkgversion}-%{name}-web}
Requires: httpd
Requires: python%{python3_pkgversion}-mod_wsgi
Requires: mod_auth_gssapi
Requires: python%{python3_pkgversion}-psycopg2
Requires: python%{python3_pkgversion}-cheetah
Requires: python%{python3_pkgversion}-%{name} = %{version}-%{release}
Provides: %{name}-web-code = %{version}-%{release}

%description -n python%{python3_pkgversion}-%{name}-web
koji-web is a web UI to the Koji system.
%endif

%prep
%autosetup -p1

%build

%install
rm -rf $RPM_BUILD_ROOT

%if 0%{py2_support} < 2  &&  0%{py3_support} < 2
echo "At least one python must be built with full support"
exit 1
%endif

# python2 build
%if 0%{py2_support} > 1
make DESTDIR=$RPM_BUILD_ROOT PYTHON=%{__python2} %{?install_opt} install
%else
%if 0%{py2_support}
for d in koji cli plugins ; do
    pushd $d
    make DESTDIR=$RPM_BUILD_ROOT KOJI_MINIMAL=1 PYTHON=%{__python2} %{?install_opt} install
    popd
done
%endif
%endif


# python3 build
%if 0%{py3_support} > 1
make DESTDIR=$RPM_BUILD_ROOT PYTHON=%{__python3} %{?install_opt} install
# alter python interpreter in koji CLI
scripts='%{_bindir}/koji %{_sbindir}/kojid %{_sbindir}/kojira %{_sbindir}/koji-shadow
         %{_sbindir}/koji-gc %{_sbindir}/kojivmd %{_sbindir}/koji-sweep-db
         %{_sbindir}/koji-sidetag-cleanup'
for fn in $scripts ; do
    sed -i 's|#!/usr/bin/python2|#!/usr/bin/python3|' $RPM_BUILD_ROOT$fn
done
%else
%if 0%{py3_support}
# minimal
for d in koji cli plugins ; do
    pushd $d
    make DESTDIR=$RPM_BUILD_ROOT KOJI_MINIMAL=1 PYTHON=%{__python3} %{?install_opt} install
    popd
done
# alter python interpreter in koji CLI
sed -i 's|#!/usr/bin/python2|#!/usr/bin/python3|' $RPM_BUILD_ROOT/usr/bin/koji
%endif
%endif

%if 0%{?fedora}
# handle extra byte compilation
extra_dirs='
    %{_prefix}/lib/koji-builder-plugins
    %{_prefix}/lib/koji-hub-plugins
    %{_datadir}/koji-hub
    %{_datadir}/koji-web/lib/kojiweb
    %{_datadir}/koji-web/scripts'
%if 0%{py2_support} > 1
for fn in $extra_dirs ; do
    %py_byte_compile %{__python2} %{buildroot}$fn
done
%endif
%if 0%{py3_support} > 1
for fn in $extra_dirs ; do
    %py_byte_compile %{__python3} %{buildroot}$fn
done
%endif
%endif

# in case, we're building only py2, delete all py3 content
%if 0%{py3_support} < 1 && 0%{py2_support} > 0
   rm -rf %{buildroot}%{_datadir}/koji-web
   rm -rf %{buildroot}%{_datadir}/koji-hub
   rm -rf %{buildroot}%{_prefix}/lib/koji-hub-plugins
   rm -f %{buildroot}/etc/httpd/conf.d/kojihub.conf
   rm -f %{buildroot}/etc/httpd/conf.d/kojiweb.conf
   rm -f %{buildroot}/etc/koji-hub/hub.conf
   rm -f %{buildroot}/etc/koji-hub/plugins/protonmsg.conf
   rm -f %{buildroot}/etc/koji-hub/plugins/rpm2maven.conf
   rm -f %{buildroot}/etc/koji-hub/plugins/save_failed_tree.conf
   rm -f %{buildroot}/etc/koji-hub/plugins/sidetag.conf
   rm -f %{buildroot}/etc/kojiweb/web.conf
   rm -f %{buildroot}%{_prefix}/lib/systemd/system/koji-sweep-db.service
   rm -f %{buildroot}%{_prefix}/lib/systemd/system/koji-sweep-db.timer
   rm -f %{buildroot}%{_prefix}/sbin/koji-sweep-db
%endif

%clean
rm -rf $RPM_BUILD_ROOT

%files
%{_bindir}/*
%config(noreplace) /etc/koji.conf
%dir /etc/koji.conf.d
%doc docs Authors COPYING LGPL

%if 0%{py2_support}
%files -n python2-%{name}
%{python2_sitelib}/%{name}
%{python2_sitelib}/koji_cli
%endif

%if 0%{py3_support}
%files -n python%{python3_pkgversion}-koji
%{python3_sitelib}/%{name}
%{python3_sitelib}/koji_cli
%endif

%if 0%{py2_support}
%files -n python2-%{name}-cli-plugins
%{python2_sitelib}/koji_cli_plugins
# we don't have config files for default plugins yet
#%%dir %%{_sysconfdir}/koji/plugins
#%%config(noreplace) %%{_sysconfdir}/koji/plugins/*.conf
%endif

%if 0%{py3_support}
%files -n python%{python3_pkgversion}-%{name}-cli-plugins
%{python3_sitelib}/koji_cli_plugins
# we don't have config files for default plugins yet
#%%dir %%{_sysconfdir}/koji/plugins
#%%config(noreplace) %%{_sysconfdir}/koji/plugins/*.conf
%endif

%if 0%{py3_support} > 1
%files hub
%config(noreplace) %attr(0640, root, apache) /etc/httpd/conf.d/kojihub.conf
%dir /etc/koji-hub
%config(noreplace) %attr(0640, root, apache) /etc/koji-hub/hub.conf
%dir /etc/koji-hub/hub.conf.d
%{_sbindir}/koji-sweep-db
%if %{use_systemd}
%{_unitdir}/koji-sweep-db.service
%{_unitdir}/koji-sweep-db.timer
%endif

%files -n python%{python3_pkgversion}-%{name}-hub
%{_datadir}/koji-hub/*.py
%{_datadir}/koji-hub/__pycache__

%files hub-plugins
%dir /etc/koji-hub/plugins
%config(noreplace) /etc/koji-hub/plugins/*.conf

%files -n python%{python3_pkgversion}-%{name}-hub-plugins
%{_prefix}/lib/koji-hub-plugins/*.py
%{_prefix}/lib/koji-hub-plugins/__pycache__
%endif

%files builder-plugins
%dir /etc/kojid/plugins
%config(noreplace) /etc/kojid/plugins/*.conf
%dir %{_prefix}/lib/koji-builder-plugins
%{_prefix}/lib/koji-builder-plugins/*.py*
%if 0%{py3_support} > 1
%{_prefix}/lib/koji-builder-plugins/__pycache__
%endif

%files utils
%{_sbindir}/kojira
%if %{use_systemd}
%{_unitdir}/koji-gc.service
%{_unitdir}/koji-gc.timer
%{_unitdir}/kojira.service
%endif
%dir /etc/kojira
%config(noreplace) /etc/kojira/kojira.conf
%{_sbindir}/koji-gc
%dir /etc/koji-gc
%config(noreplace) /etc/koji-gc/koji-gc.conf
%config(noreplace) /etc/koji-gc/email.tpl
%{_sbindir}/koji-shadow
%dir /etc/koji-shadow
%config(noreplace) /etc/koji-shadow/koji-shadow.conf
%{_sbindir}/koji-sidetag-cleanup

%if 0%{py3_support} > 1
%files web
%dir /etc/kojiweb
%config(noreplace) /etc/kojiweb/web.conf
%config(noreplace) /etc/httpd/conf.d/kojiweb.conf
%dir /etc/kojiweb/web.conf.d

%files -n python%{python3_pkgversion}-%{name}-web
%{_datadir}/koji-web
%endif

%files builder
%{_sbindir}/kojid
%if 0%{py2_support} > 1
%dir %{_libexecdir}/kojid
%{_libexecdir}/kojid/mergerepos
%endif
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
%{_sbindir}/kojivmd
#dir %%{_datadir}/kojivmd
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
%endif

%changelog
* Tue Jul 28 2020 Mike McLean <mikem at redhat.com> - 1.22.0-1
- PR#2404: release bump and changelog
- PR#2393: release notes - 1.22
- PR#2397: kojira: remove unused delete_batch_size
- PR#2401: kojira: drop reference to krb_login
- PR#2280: Use requests_gssapi instead of requests_kerberos
- PR#2244: remove deprecated krbV support
- PR#2340: kojira: threaded repo deletion
- PR#2337: align option naming with mock
- PR#2363: sphinx formatting fixes for hub policy doc
- PR#2377: hub: document listBType return value when query matches no entries
- PR#2123: Pass buildroot to preSCMCheckout and postSCMCheckout where applicable.
- PR#2257:  BuildSRPMFromSCMTask: Support auto-selecting a matching specfile name
- PR#2387: cli: list-tags: fall back to old behavior on ParameterError
- PR#2353: turn off dnf_warning in mock.cfg
- PR#2385: doc: exporting repositories
- PR#2372: TaskManager: clean both result and results dirs
- PR#2376: kojid: use mergerepo_c for all merge modes
- PR#2359: hub: importImage doesn't honor volume
- PR#2364: cli clone-tag - get srctag info with event
- PR#2347: cli: fix image-build-indirection --wait
- PR#2366: upgrade-sql: fix backward compatibility
- PR#2369: hub: make sure checksum_type is int for DB
- PR#2306: Provide task-based data to volume policy
- PR#2346: cli: --wait for download-task
- PR#2342: fix simple_error_message encoding
- PR#2358: web: remove "GssapiLocalName off" setting
- PR#2354: fix error message
- PR#2351: hub: remove "GssapiLocalName off" setting
- PR#2350: doc: improve hub selinux instructions
- PR#2352: doc: update test suite dependency list for py3
- PR#2348: fix option order
- PR#2339: kojira: drop kojira.sysconfig
- PR#2320: hub: allow glob matching for listTags
- PR#2344: runroot: basic docs
- PR#2345: builder: document plugin callbacks
- PR#2327: koji-gc: fix py3 compare behaviour for dicts
- PR#2338: hub: fix typo
- PR#2334: hub: fix index so it gets used by planner
- PR#2137: more debug info for un/tracked tasks in kojira
- PR#2161: doc: update documentation for SSLCACertificateFile
- PR#2162: hub: remove "GssapiSSLonly Off" option
- PR#2287: doc: rewrite PostgreSQL authorization instructions
- PR#2290: vm: clone mac address via xml
- PR#2317: md5: try the best to use sha256 instead of md5 and ignore FIPS in other parts
- PR#2263: improve race condition for getNextRelease / images
- PR#2085: hide local --debug options
- PR#2301: avoid redundant clauses and joins in query_buildroots()
- PR#2237: db: use timestamps with timezone
- PR#2329: docs: align "Hub" text in diagram
- PR#2330: clean_old option was duplicated on clean_empty
- PR#2331: hub: document listChannels arguments
- PR#2318: make mock depsolver policy configurable
- PR#1932: per-tag settings for mock's sign plugin
- PR#2328: koji-gc: fix flake8
- PR#2218: Drop py2 support for hub/web
- PR#2316: kojira: replace deprecated Thread.isAlive()
- PR#2309: hub: simplify recipients condition in build_notification()
- PR#2326: sidetag: parenthesis typo
- PR#2322: Side tags: allow admin ops and misc fixes
- PR#2323: kojira: Fix logic detecting directories
- PR#2276: document merge modes
- PR#2310: hub: fix "opt-outs" comment in get_notification_recipients()
- PR#2256: Don't break on deleted tag
- PR#2154: kojira: swap first_seen with latest mtime for repo
- PR#2275: hub: default policy allow packagelist changes with 'tag' permission
- PR#2255: cli: output extra['rpm.macro.*'] to mock-config
- PR#2253: koji-gc: set smtp_host to localhost by default
- PR#2308: hub: return empty list in get_notification_recipients()
- PR#2293: disable notifications by default in [un]tagBuildBypass calls
- PR#2303: hub: query_buildroots fix query behaviour
- PR#2299: hub: query_buildroots have to return ASAP
- PR#2166: mock's boostrap + image support
- PR#2295: Koji 1.21.1 release notes
- PR#2278: koji-gc: fix cc/bcc e-mail handling
- PR#2212: kojid: remove bootstrap dir
- PR#2254:  openRemoteFile retries and checks downloaded content
- PR#2225: hub: log tracebacks for multicalls
- PR#2279: koji-gc: fix query order
- PR#2064: Support tag specific environment variables
- PR#2153: koji-gc: various typos in maven path
- PR#2193: www: repoinfo page
- PR#2268: don't decode signature headers
- PR#2214: cli: drop unneeded activate_session
- PR#2266: Correctly identify "hostname doesn't match" errors
- PR#2228: cli: flush stdout during watch-logs
- PR#2264: replace deprecated function with logging
- PR#2262: Pass bootloader append option to livemedia builds
- PR#2195: koji-gc: allow specifying CC and BCC address for email notifications
- PR#2141: kojiweb: update for mod_auth_gssapi configuration
- PR#2238: hub: deprecate host.getTask call
- PR#2224: cli: fix variable name
- PR#2245: cli: extend docs for --before/--after options
- PR#2246: deprecated warning for cli option --ca as well
- PR#2248: doc: links to copr builds
- PR#2223: cli: fix un/lock-tag permission handling
- PR#2241: hub: API docs
- PR#2242: hub: additional API docs
- PR#2199: koji-gc: add systemd unit files
- PR#2157: kojira: use cached getTag for external repos
- PR#2226: cli: deprecate --ca
- PR#2197: Use %autosetup (fixes #2196)
- PR#2235: doc: update postgresql-setup command for el8 and Fedora
- PR#2236: fix additional flake8 problems
- PR#2233: fix flake8 errors
- PR#2151: koji-gc: support request_kerberos
- PR#2211: koji-gc: test existence of trashcan tag
- PR#2132: listSideTags returns also user info
- PR#2187: koji-sweep-db: use "Type=oneshot" for systemd
- PR#2213: Correct docstring about deleting inheritance rules
- PR#2209: koji-utils: only requires /usr/bin/python2 on rhel<=7
- PR#2205: doc: fix koji-sweep-db filename typo
- PR#2206: doc: indent SQL query for user ID discovery
- PR#2207: cli: improve grant-permission --new --help message
- PR#2203: hub: admin can't force tag now
- PR#2194: remove obsoleted note
- PR#2158: hub: document addExternalRepoToTag arguments
- PR#2172: hub: document createUser arguments
- PR#2180: cli: fix "list-history --help" text for "--cg"
- PR#2044: Unify error messages in CLI
- fix flake8
- PR#2024: queue log file for kojira
- PR#2136: replace logging.warn with warning
- PR#2038: Don't use listTagged(tag, *) for untag-build
- PR#2103: fix list-signed --tag memory issues
- PR#2150: translate exceptions to GenericError
- PR#2176: hub: document editUser method
- PR#2175: kojira: remove duplicate Kerberos configuration boilerplate
- Merge #2173 `hub: document getTagExternalRepos`
- PR#2177: doc: "koji build" requires a target
- PR#2178: docs: Fix sidetag enablement typo
- PR#2174: hub: document removeExternalRepoFromTag arguments
- hub: document getTagExternalRepos
- fix docs
- missing file from 1.21 docs

* Wed Jun 03 2020 Tomas Kopecek <tkopecek at redhat.com> - 1.21.1-1
 - PR#2279: koji-gc: fix query order
 - PR#2038: Don't use listTagged(tag, *) for untag-build
 - PR#2245: cli: extend docs for --before/--after options
 - PR#2103: fix list-signed --tag memory issues
 - PR#2241: hub: API docs
 - PR#2242: hub: additional API docs
 - PR#2136: replace logging.warn with warning
 - PR#2141: kojiweb: update for mod_auth_gssapi configuration
 - PR#2153: koji-gc: various typos in maven path
 - PR#2157: kojira: use cached getTag for external repos
 - PR#2158: hub: document addExternalRepoToTag arguments
 - PR#2194: remove obsoleted note
 - PR#2211: koji-gc: test existence of trashcan tag
 - PR#2203: hub: admin can't force tag now
 - PR#2224: cli: fix variable name
 - PR#2223: cli: fix un/lock-tag permission handling
 - PR#2268: don't decode signature headers
 - PR#2248: doc: links to copr builds
 - PR#2178: docs: Fix sidetag enablement typo
 - PR#2174: hub: document removeExternalRepoFromTag arguments
 - fix docs
 - missing file from 1.21 docs

* Tue Apr 14 2020 Tomas Kopecek <tkopecek at redhat.com> - 1.21-1
- PR#2057: update docs on httpd configuration
- PR#1385: Add --no-delete option to clone-tag
- PR#2054: editSideTag API call
- PR#2081: new policy for dist-repo
- PR#2129: hub: document deleteExternalRepo arguments
- PR#2128: hub: document getExternalRepo arguments
- PR#2127: fix sanity check in merge_scratch
- PR#2125: Set default keytab for kojira
- PR#2071: Better help for build/latest-build
- PR#516:  kojira monitors external repos changes
- PR#2121: kojira: be tolerant of old with_src configuration option
- PR#2105: always set utf8 pg client encoding
- PR#2106: kojira: Allow using Kerberos without krbV
- PR#2088: fix missing /lib/ in hub-plugins path
- PR#2097: display merge mode for external repos
- PR#2098: move admin force usage to assert_policy
- PR#1990: allow debuginfo for sidetag repos
- PR#2082: delete oldest failed buildroot, when there is no space
- PR#2115: Correct json.dumps usage
- PR#2113: don't break on invalid task
- PR#2058: merge_scratch: Compare SCM URLs only if built from an SCM
- PR#2074: Limit final query by prechecking buildroot ids
- PR#2022: reverse score ordering for tags
- PR#2056: fix table name
- PR#2002: try to better guess mock's error log
- PR#2080: koji download-build - consider resume downloads by default
- PR#2042: add-host work even if host already tried to log in
- PR#2051: hub: editTagExternalRepo is able to set merge_mode
- PR#2040: koji.ClientSession: fix erroneous conversion to latin-1
- PR#2089: propagate event to get_tag_extra
- PR#2047: limit size of extra field in proton msgs
- PR#2019: log --force usage by admins
- PR#2083: allow to skip SRPM rebuild for scratch builds
- PR#2068: use real time for events
- PR#2078: Adapt older win-build docs
- PR#2075: Don't use datetime timestamp() as it's not in Python 2
- PR#2028: make xz options configurable
- PR#2079: prune old docs about interaction with Fedora's koji
- PR#2030: raise error on non-existing tag
- PR#1749: rpm: remove references to EOL fedora versions
- PR#1194: client: use default CA store during SSL auth if serverca is unset
- PR#2073: trivial flake8 warning fix
- PR#2048: use only gssapi_login in CLI
- PR#2016: Add detail about known koji signatures to buildinfo
- PR#2027: raise GenericError instead of TypeError in filterResults
- PR#2009: CG: add and update buildinfo.extra.typeinfo if it doesn't exist
- PR#2049: extending flake8 rules
- PR#1891: Disable notifications from clone-tag by default
- PR#2006: add missing koji-sidetag-cleanup script
- PR#2025: Include livemedia builds in accepted wrapperRPM methods
- PR#2045: insert path before import kojihub
- PR#2034: update docs to current jenkins setup
- PR#1987: Add doc string for virtual methods
- PR#1916: replace xmlrpc_client exception with requests
- PR#751:  xmlrpcplus: use parent Marshaller's implementations where possible
- PR#2004: obsolete external sidetag plugin
- PR#1992: deprecation of krb_login
- PR#2001: remove usage of deprecated cgi.escape function
- PR#1333: file locking for koji-gc
- PR#692: Add smtp authentication support
- PR#1956: Merge sidetag plugin
- PR#478: Add _taskLabel entry for indirectionimage
- PR#2000: hub: improve listBTypes() API documentation
- PR#1058: Add 'target' policy
- PR#938: Deprecating list-tag-history and tagHistory
- PR#1971: remove outdated comment in schema file
- PR#1986: fix test
- PR#1984: Remove deprecated md5/sha1 constructors
- PR#1059: Emit user in PackageListChange messages
- PR#1945: check permission id in edit_tag
- PR#1948: check package list existence before blocking
- PR#1949: don't allow setTaskPriority on closed task
- PR#1950: print warn to stderr instead of stdout
- PR#1951: add strict to getChangelogEntries
- PR#1975: update runs_here.rst: correcting usage of koji at CERN
- PR#1934: remove unused option --with-src in kojira
- PR#1911: hub: [newRepo] raise error when tag doesn't exist
- PR#1886: cli: make list-signed accepting integer params
- PR#1863: hub: remove debugFunction API

* Thu Mar  5 2020 Tomas Kopecek <tkopecek at redhat.com> - 1.20.1-1
- PR#1995: hub: improve search() API documentation
- PR#1993: Always use stream=True when iterating over a request
- PR#1982: ensure that all keys in distrepo are lowered
- PR#1962: improve sql speed in build_references
- PR#1960: user proper type for buildroot state comparison
- PR#1958: fix potentially undeclared variable error
- PR#1967: don't use full listTags in list-groups call
- PR#1944: analyze/vacuum all affected tables
- PR#1929: fix flags display for list-tag-inheritance
- PR#1935: docs for kojira and koji-gc
- PR#1923: web: fix typo - the param[0] is tag, not target
- PR#1919: expect, that hub is returning GM time
- PR#1465: unittest fix: tests/test_cli/test_list_tagged.py
- PR#1920: display some taskinfo for deleted buildtags
- PR#1488: Display params also for malformed tasks in webui
- PR#2020: move needed functions
- PR#1946: fix usage message for add-pkg
- PR#1947: fix help message for list-groups
- PR#2060: build_references: fix the type of event_id used by max

* Mon Jan 20 2020 Tomas Kopecek <tkopecek at redhat.com> - 1.20.0-1
- PR#1908: koji 1.20 release
- PR#1909: a follow-up fix for koji-gc
- PR#1921: fix test for PR1918
- PR#1893: raise GenericError on existing build reservation
- PR#1917: Update typeinfo metadata documentation
- PR#1918: cli: add "--new" option in "grant-permission" help summary
- PR#1912: hub: [distRepo] fix input tag arg for getBuildConfig call
- PR#1832: docstrings for API
- PR#1889: fix nvr/dict params
- PR#1743: basic zchunk support for dist-repo
- PR#1869: limit distRepo tasks per tag
- PR#1873:  koji-gc: untagging/moving to trashcan is very slow
- PR#1829: Add a sanity check on remotely opened RPMs
- PR#1892: kojid: use binary msg for python3 in *Notification tasks
- PR#1854: do not use with statement with requests.get
- PR#1875: document noarch rpmdiff behaviour
- PR#1872: hub: getUser: default krb_princs value is changed to True
- PR#1824: additional options to clean database
- PR#1246: split admin_emails option for kojid
- PR#1794: merge duplicate docs
- PR#763: clean all unused `import` and reorder imports
- PR#1626: build can wait for actual repo
- PR#1640: Provide for passing credentials to SRPMfromSCM
- PR#1820: [web] human-friendly file sizes in taskinfo page
- PR#1821: browsable api
- PR#1839: fix closing table tag
- PR#1785: unify return values for permission denied
- PR#1428: Add koji-gc/kojira/koji-shadow to setup.py
- PR#1868: extend docstrings for CGInit/RefundBuild
- PR#1853: fix CGRefundBuild to release build properly
- PR#1862: gitignore: exclude .vscode folder
- PR#1845: QueryProcessor: fix countOnly for group sql
- PR#1850: fix conflict -r option for kernel version
- PR#1848: list-pkgs: fix opts check
- PR#1847: hub: fix BulkInsertProcessor call in CGImport
- PR#1841: continue instead of exiting
- PR#1837: A few fixes for kojikamid
- PR#1823: docs for partitioning buildroot_listings
- PR#1771: koji-sweep-db: Turn on autocommit to eliminate VACUUMing errors
- PR#723: improve test and clean targets in Makefiles
- PR#1037: use --update for dist-repos if possible
- PR#1817: document tag inheritance
- PR#1691: human-readable timestamp in koji-gc log
- PR#1755: drop buildMap API call
- PR#1814: some list-pkgs options work only in combinations
- PR#821: Log kernel version used for buildroot
- PR#983: fix downloads w/o content-length
- PR#284: Show build link(s) on buildContainer task page
- PR#1826: fix time type for restartHosts
- PR#1790: remove old db constraint
- PR#1775: clarify --ts usage
- PR#1542: Replace urllib.request with requests library
- PR#1380: no notifications in case of deleted tag
- PR#1787: raise error when config search paths is empty
- PR#1828: cli: refine output of list-signed
- PR#1781: Remove title option for livemedia-creator
- PR#1714: use BulkInsertProcessor for hub mass inserts
- PR#1797: hub: build for policy check should be build_id in host.tagBuild
- PR#1807: util: rename "dict" arg
- PR#1149: hub: new addArchiveType RPC
- PR#1798: rm old test code
- PR#1795: fix typos for GenericError
- PR#1799: hub: document cg_import parameters
- PR#1804: docs: MaxRequestsPerChild -> MaxConnectionsPerChild
- PR#1806: docs: explain "compile/builder1" user principal
- PR#1800: rpm: remove %defattr
- PR#1805: docs: recommend 2048 bit keys
- PR#1801: docs: fix indent for reloading postgres settings
- PR#1802: docs: simplify admin bootstrapping intro
- PR#1803: docs: fix rST syntax for DB listening section
- PR#1551: cluster health info page
- PR#1525: include profile name in parsed config options
- PR#1773: make rpm import optional in koji/__init__.py
- PR#1767: check ConfigParser object rather than config path list

* Fri Nov  8 2019 Brendan Reilly <breilly at redhat.com> - 1.19.1-1
- PR#1751: hub: Fix issue with listing users and old versions of Postgres
- PR#1753: Fix hub reporting of bogus ownership data
- PR#1733: allow tag or target permissions as appropriate (on master)

* Wed Oct  30 2019 Brendan Reilly <breilly at redhat.com> - 1.19.0-1
- PR#1720: backward-compatible db conversion
- PR#1713: cli: fix typo in edit-user cmd
- PR#1662: CGUninitBuild for cancelling CG reservations
- PR#1681: add all used permissions to db
- PR#1702: fix log message to show package name
- PR#1682: mostly only mock exit code 10 ends in build.log
- PR#1694: doc: change user creating sql for kerberos auth
- PR#1706: fix test for RHEL6
- PR#1701: fix user operations typos
- PR#1296: extract read_config_files util for config parsing
- PR#1670: verifyChecksum fails for non-output files
- PR#1492: bundle db maintenance script to hub
- PR#1160: hub: new listCGs RPC
- PR#1120: Show inheritance flags in list-tag-inheritance output
- PR#1683: in f30+ python-devel defaults to python3
- PR#1685: Tag permission can be used for un/tagBuildBypass
- PR#902: Added editUser api call
- PR#1684: use preferred arch if there is more options
- PR#1700: README: fix bullet indentation
- PR#1159: enforce unique content generator names in database
- PR#1699: remove references to PythonOption
- PR#923: Remove Groups CLI Call
- PR#1696: fix typo in createUser
- PR#1419: checking kerberos prinicipal instead of username in GSSAPI authentication
- PR#1648: support multiple realms by kerberos auth
- PR#1657: Use bytes for debug string
- PR#1068: hub: [getRPMFile] add strict behavior
- PR#1631: check options for list-signed
- PR#1688: clarify fixed/affected versions in cve announcement
- PR#1687: Docs updates for CVE-2019-17109
- PR#1686: Fix for CVE-2019-17109
- PR#1680: drop unused host.repoAddRPM call
- PR#1666: Fix typo preventing vm builds
- PR#1677: docs for build.extra.source
- PR#1675: Subselect gives better performance
- PR#1642: Handle sys.exc_clear in Python 3
- PR#1157: cli: [make-task] raise readable error when no args
- PR#1678: swapped values in message
- PR#1676: Made difference between Builds and Tags sections more clear
- PR#1173: hub: [groupListRemove] raise Error when no group for tag
- PR#1197: [lib] ensuredir: normalize directory and don't throw error when dir exists
- PR#1244: hub: add missing package list check
- PR#1523: builder: log insufficent disk space location
- PR#1616: docs/schema-upgrade-1.18-1.19.sql/schema.sql: additional CoreOS artifact types.
- PR#1643: fix schema.sql introduced by moving owner from tag_packages to another table
- PR#1589: query builds per chunks in prune-signed-builds
- PR#1653: Allow ClientSession objects to get cleaned up by the garbage collector
- PR#1473: move tag/package owners to separate table
- PR#1430: koji-gc: Added basic email template
- PR#1633: Fix lookup_name usage + tests
- PR#1627: Don't allow archive imports that don't match build type
- PR#1618: write binary data to ks file
- PR#1623: Extend help message to clarify clone-tag usage
- PR#1621: rework update of reserved builds
- PR#1508: fix btype lookup in list_archive_files()
- PR#1223: Unit test download_file
- PR#1613: Allow builder to attempt krb if gssapi is available
- PR#1612: use right top limit
- PR#1595: enable dnf_warning in mock config
- PR#1458: remove deprecated koji.util.relpath
- PR#1511: remove deprecated BuildRoot.uploadDir()
- PR#1512: remove deprecated koji_cli.lib_unique_path
- PR#1490: deprecate sha1/md5_constructor from koji.util

* Fri Aug  9 2019 Mike McLean <mikem at redhat.com> - 1.18.0-1
- PR#1606: pull owner from correct place
- PR#1602: copy updated policy for reserved cg builds
- PR#1601: fix recycling build due to cg
- PR#1597: Backward-compatible fix for CG import
- PR#1591: secrets import is missing 'else' variant
- PR#1555: use _writeInheritanceData in _create_tag
- PR#1580: cli: verify user in block-notification command
- PR#1578: cli:fix typo in mock-config
- PR#1464: API for reserving NVRs for content generators
- PR#898: Add support for tag/target macros for Mageia
- PR#1544: use RawConfigParser for kojid
- PR#863: cli: change --force to real bool arg for add-tag-inheritance
- PR#1253: cli: add option for custom cert location
- PR#1353: Create db index for listTagged
- PR#1375: docs: add architecture diagram
- PR#892: cli: also load plugins from ~/.koji/plugins
- PR#1516: kojibuilder: Pass mergerepo_c --all for bare mode as well.
- PR#1524: set module_hotfixes=1 in yum.conf via tag config
- PR#1417: notification's optouts
- PR#1515: add debug message to new multicall to match original
- PR#1480: Add raw-gz and compressed QCOW2 archive types.
- PR#1260: use LANG=C for running all tests
- PR#1447: handle deleted tags in kojira
- PR#1513: Allow hub policy to match version and release
- PR#1462: rebuildSRPM task
- PR#1498: Pass bytes to md5_constructor
- PR#1502: Don't pass block list in bare merge mode
- PR#1489: pass bytes to sha1 constructor
- PR#1499: remove merge option from edit-external-repo
- PR#1427: Fix typo in getArchiveTypes docstring
- PR#957: New multicall interface
- PR#1280: put fix_pyver before printing command help
- PR#1415: New 'buildtype' test for policies
- PR#1258: retain old search pattern in web ui
- PR#1479: use better index for sessions
- PR#1279: let hub decide, what headers are supported
- PR#1454: introduce host-admin permission + docs
- PR#1303: fix history display for parallel host_channels updates
- PR#1278: createrepo_c is used by default now
- PR#1449: show load/capacity in list-channels
- PR#1476: Allow taginfo cli to use tag IDs; fixed Inheritance printing bug
- PR#1445: turn back on test skipped due to coverage bug
- PR#1452: fix parentheses for tuple in _writeInheritanceData
- PR#1456: deprecate BuildRoot.uploadDir method
- PR#1461: check existence of tag_id in getInheritanceData
- PR#1471: list-hosts shouldn't error on empty list
- PR#1273: Allow generating separate src repo for build repos
- PR#1255: always check existence of tag in setInheritanceData
- PR#1256: add strict option to getTaskChildren
- PR#1257: fail runroot task on non-existing tag
- PR#1272: check architecture names for mistakes
- PR#1322: Reduce duplicate "fixEncoding" code
- PR#1327: volume option for dist-repo
- PR#1442: delete_build: handle results of lazy build_references call
- PR#1425: add --show-channels listing to list-hosts
- PR#1432: py2.6 compatibility fix
- PR#1434: hub: fix check_fields and duplicated parent_id in _writeInheritanceData
- PR#1439: user correct column in sql (getTask)
- PR#1437: fix table name in build_references query
- PR#1414: Fix jenkins config for new python mock
- PR#1411: handle bare merge mode
- PR#1410: build_srpm: Wait until after running the sources command to check for alt_sources_dir
- PR#1383: display task durations in webui
- PR#1358: rollback errors in multiCall
- PR#1413: Makefile: print correct urls for test coverage
- PR#1409: Fix SQL after introduction of host_config
- PR#1324: createEmptyBuild errors for non-existent user
- PR#1406: fix mapping iteration in getFullInheritance
- PR#1398: kojid: Download only 'origin'
- PR#1365: Check CLI arguments for enable/disable host
- PR#1390: CLI list-channels sorted output
- PR#1389: block_pkglist compatibility fix
- PR#1376: use context manager for open in CLI
- PR#1392: Replace references to latest-pkg with latest-build
- PR#1386: scale task_avail_delay based on bin rank
- PR#1363: Use createrepo_update even for first repo run
- PR#1368: update test requirements in jenkins
- PR#1374: honor mock.package_manager tag setting in mock-config cli
- PR#1387: remove unused variable
- PR#1143: hub: document CG access method arguments
- PR#1169: docs: use systemctl enable --now for postgres and kojid
- PR#1155: hub: document addHost and editHost arguments
- PR#1242: kojid.conf documentation
- PR#1340: Update server doc for newer TLS and event worker
- PR#1359: docs: remove "TBD" sections
- PR#1360: docs: remove mod_python references
- PR#1361: docs: kojirepod -> kojira
- PR#1370: add vhdx archivetype
- PR#1331: provide lower level versions of build_target functions
- PR#1348: rm old references to Mozilla
- PR#1297: Support tilde in search
- PR#1356: kojira: fix iteration over repos in py3
- PR#1342: Remove python2.4 OptionParse fix
- PR#1347: Fix hub startup handling
- PR#1346: Rely on ozif_enabled switch in BaseImageTask
- PR#1344: add .tgz to list of tar's possible extensions
- PR#1086: hub: unittest for get_external_repos
- PR#1170: docs: koji package provides schema.sql file
- PR#1281: remove urlescape from package name
- PR#1304: hub: document setInheritanceData arguments
- PR#1277: Remove 'keepalive' option
- PR#1330: fix docs typos
- PR#1339: fix typo in usage of six's import of MIMEText
- PR#1337: minor gc optimizations
- PR#1254: doc: Include AnyStor mention to 'koji runs here' doc
- PR#1325: run py3 tests in CI by default
- PR#1326: README: link to Pungi project instead of mash
- PR#1329: Update plugin doc (confusing sentence)

* Wed Mar  6 2019 Mike McLean <mikem at redhat.com> - 1.17.0-1
- PR#1320: also remove nonprintable changelog chars in py3
- PR#1293: fix dict encoding in py3
- PR#1309: Fix binary output in cli in py3
- PR#1317: fix deps for utils/vm subpackages on py3
- PR#1315: fix checksum validation in CG_Importer
- PR#1313: Fix encoding issues with base64 data
- PR#1307: python3-koji-hub requires python3-psycopg2
- PR#1290: downloadTaskOutput fix for py3
- PR#1300: require correct mod_wsgi
- PR#1301: use greetings list from lib
- PR#1284: replace urrlib.quote with six.moves
- PR#1286: correctly escape license in web ui
- PR#1292: define _sortByKeyFuncNoneGreatest as staticmethod
- PR#1227: Added volume id as argument to livemedia and livecd tasks
- PR#1070: consolidate access to rpm headers
- PR#1274: cve-2018-1002161
- PR#1271: decode Popen.communicate result under py3
- PR#1269: require librepo on python3
- PR#1222: Include CLI plugins in setup.py
- PR#1265: py3 tests + related fixes
- PR#1220: Fix non-ascii strings in xmlrpc
- PR#1229: document reason strings in policies
- PR#1263: python 3 can't index dict.keys()
- PR#1235: fix weak deps handling in rpminfo web page
- PR#1251: fix race-condition with librepo temp directories
- PR#1245: organize python 2/3 cases in spec file
- PR#1231: remove unused directory
- PR#1248: use six move for email.MIMEText
- PR#1150: using ConfigParser.read_file for PY3
- PR#1249: more detailed help for block-group-pkg
- PR#1117: python3 kojid
- PR#891: Web UI python3 changes
- PR#921: Py3 hub
- PR#1182: hub: document get_channel arguments
- PR#1014: cli: preserve build order in clone-tag
- PR#1218: docs: drop HTML tags from howto doc
- PR#1211: Fix wrong error message
- PR#1184: rest of python3 support for koji lib
- PR#1062: fix pyOpenSSL dependency for py26 in setup.py
- PR#1019: Use python2/3 instead of python in Makefile/spec
- PR#1190: hub: document all edit_tag arguments
- PR#1201: re-add urlparse import in kojikamid
- PR#1203: Fix `is_conn_error()` for Python 3.3+ change to `socket.error`
- PR#967: use correct fileinfo checksum field
- PR#1187: Add ctx option to ClientSession.krb_login()
- PR#1175: kojira: avoid race condition that causes "unknown task" errors
- PR#964: few sort speedups
- PR#852: drop encode_int helper
- PR#1043: remove old messagebus plugin
- PR#1176: kojid: implement task_avail_delay check
- PR#1180: Update source when recycling build
- PR#1178: cli: document parse_arches method parameters
- PR#920: use relative symlinks for hub imports
- PR#981: cli: add a param in watch_tasks to override KeyboardInterrupt output
- PR#1042: don't fail on missing field in base policy tests
- PR#1172: make timeout of authentication configurable
- PR#1168: remove shebang in context module
- PR#1045: cli: [free-task] raise error when no task-id specified
- PR#1056: Print warning to stderr
- PR#1057: raise error for non-existing task in list_task_output
- PR#1061: hub: [getRPMDeps] add strict behavior
- PR#1065: fix wrong message
- PR#1081: hub: [getPackageID] add strict behavior
- PR#1099: hub: [hasPerm] add strict behavior
- PR#732: koji.next.md: drop RHEL 5 requirements
- PR#1156: hub: unlimited NameWidth for kojifiles Apache location
- PR#1154: docs: update cheetah template user guide link
- PR#1148: docs: use "postgresql-setup initdb" to initialize database
- PR#1141: hub: document edit_tag argument types
- PR#1138: cli: fix "at least" typo in help text
- PR#1137: docs: unify "dnf" and "yum" instructions in server howto
- PR#1125: Ignore non-existing option when activate a session
- PR#1111: Don't retry if certificate is not readable
- PR#928: check tag existence in list-tagged cmd and listTagged* APIs
- PR#1127: only pass new incl_blocked call opt if it is explicitly needed
- PR#1124: tooltip for search field
- PR#1115: Do not require split_debuginfo
- PR#1123: fix wrong old value in postBuildStateChange callback
- PR#1097: hub: [getTaskInfo] add strict behavior
- PR#1098: cli: [download-task] readable error when no task found
- PR#1096: cli: fix typos in *-notification error msg
- PR#1072: Include WadersOS mention to 'koji runs here' doc
- PR#1094: hub: [postBuildStateChange] passing the newest build info
- PR#1066: Simple mode for mergerepos
- PR#1091: more informative error for invalid scm schemes
- PR#1003: update jenkins configuration
- PR#947: exclude py compiled files under util/
- PR#965: check rpm headers support directly
- PR#978: get_next_release should check also running builds
- PR#1041: fix utf-8 output in CLI
- PR#1036: Add more test patterns for rpmdiff unit test.
- PR#1023: Expand user directory from config
- PR#1002: prioritize unittest2
- PR#1000: Fix target handling in make_task
- PR#997: Fix rpmdiff's ignoring of size
- PR#1012: Fix isinstance with lists
- PR#1030: Create symlinks for builds imported onto non-default volumes
- PR#1021: Raise error for non-200 codes in download_file
- PR#1005: Add unit tests for check volume id substitution list
- PR#1027: [kojihub] add strict parameter in getBuildNotification
- PR#1016: raise Error when user not found in getBuildNotifications
- PR#1008: decode_args(): make a copy of the opts dict, rather than modifying it in-place
- PR#989: additional info on builders in channelinfo page
- PR#685: Rest of automated conversion from py3 changes
- PR#962: put source target scratch into policy_data in make_task
- PR#980: cli: rename _unique_path to unique_path, and deprecate the old one
- PR#900: enable batch multiCall in clone-tag
- PR#973: Check empty arches before spawning dist-repo
- PR#959: fix wrong tagNotification in tagBuildBypass API
- PR#969: Enable python3 on RHEL8 build
- PR#970: Add RISC-V (riscv64) to distrepo task
- PR#897: Fix use_host_resolv with new mock version (2017 Nov 22+)
- PR#868: allow force for pkglist_add
- PR#845: propagate exception correctly
- PR#831: Use unittest2 for rhel6 compatibility
- PR#873: Allow listing of blocked data in readTagGroups
- PR#940: Add --enabled --ready filters for list-channels
- PR#952: cli: [clone-tag] preserve build order
- PR#919: remove deprecated BuildRoot.scrub()
- PR#948: cli: don't show license for external RPM in rpminfo
- PR#879: cli: change bad reference in clone-tag
- PR#946: force using python2 to run script
- PR#925: Allow longer Build Target names

* Tue May 15 2018 Mike McLean <mikem at redhat.com> - 1.16.0-1
- Fix CVE-2018-1002150 - distRepoMove missing access check
- PR#884: Add option to configure DB port
- PR#914: dist repo updates
- PR#843: make py2 files parseable with py3
- PR#841: kojid: make install timeout of imagefactory conf configurable
- PR#777: add debug timestamp log for logs
- PR#904: replace long with int
- PR#911: readTaggedRPMS: passing table 'tag_listing' in eventCondition
- PR#691: option for notifications in untagBuildBypass
- PR#869: also forget requests session in _forget()
- PR#874: Update URL for Open Science Grid Koji instance
- PR#883: Doc: add repos-dist to koji filesystem skeleton
- PR#894: tests for download_logs
- PR#909: Docs for CVE-2018-1002150
- PR#778: add history to edit_host
- PR#774: Cache rpmdiff results and don't spawn special process
- PR#908: Fix typo in deleted mount check
- PR#770: print debug and error messages to stderr
- PR#688: CLI commands for notifications
- PR#901: Add more path info to volume documentation
- PR#678: fix grplist_block
- PR#734: hub: add strict behavior in `get_archive_file()` and `list_archive_files()`
- PR#726: pass full buildinfo obtained by get_build to postBuildStateChange callbacks
- PR#823: Add --old-chroot option to runroot command
- PR#881: add txkoji to related projects
- PR#822: Don't show license for external rpms
- PR#779: drop cascade in schema-clear
- PR#860: mavenBuild uses wrong session
- PR#858: restart-hosts fails if provided arguments
- PR#853: Show the krb principal name in debug log
- PR#711: Drop explicit python-krbV dependency for modern platforms
- PR#768: json serialize additional types in protonmsg
- PR#849: kojira: sanity check in pruneLocalRepos
- PR#848: use subprocess.Popen instead of subprocess.check_output
- PR#819: Drop pre-2.6 compat function koji.util._relpath
- PR#828: fix runroot output on py3
- PR#765: search build by source
- PR#817: Update the volume ID substitutions list and application
- PR#744: Replace cmp= with key= for python3 support
- PR#748: hub: make list_archives to accept strict argument
- PR#769: handle None in place of string in buildNotification
- PR#824: Add internal_dev_setup option to runroot config
- PR#804: hub: fix KeyError in `get_notification_recipients`
- PR#802: omit the last dot of cname when krb_canon_host=True
- PR#820: compressed xml archive type
- PR#743: Fix key access mechanism in _build_image
- PR#800: Don't allow combination of --mine and task-ids
- PR#812: Fix AttributeError during archive import
- PR#796: Fix comparison with Enum value
- PR#695: blacklist tags for kojira
- PR#773: create/edit notification checks for duplicity
- PR#799: Fix values for non-existent options
- PR#805: fix duplicated args "parent" in waittest task
- PR#806: honour runroot --quiet for old-style call
- PR#767: update docs for listRPMFile
- PR#797: Move kojira's regen loop into dedicated thread
- PR#794: Work around race in add_external_rpm
- PR#753: check python-requests-kerberos version before gssapi login
- PR#783: don't join users table if countOnly
- PR#775: drop pycurl dependency
- PR#733: ut: [cli] fix unexcepted order problem in test_taskinfo
- PR#730: add unit test for cli commands, coverage(40%)
- PR#787: builder: make temp dir to be configured
- PR#498: remove old ssl library
- PR#755: remove simplejson imports
- PR#731: koji.next.md: Content Generators are available
- PR#754: drop rhel5 cases from spec
- PR#761: proper comments of unused spec macros
- PR#762: remove unused import in koji-shadow
- PR#764: incorrect py3 syntax
- PR#757: Force coverage3 read correct rc file.
- PR#632: drop migrateImage call
- PR#759: cli: fix issues in dist-repo command

* Mon Dec 18 2017 Mike McLean <mikem at redhat.com> - 1.15.0-1
- PR#602: don't use /tmp in chroot
- PR#674: store git commit hash to build.source
- PR#492: Setuptools support
- PR#740: Check for login earlier
- PR#708: Implement support for keytab in gssapi codepaths
- PR#446: run checks earlier for cg_import
- PR#610: show components for all archives
- PR#578: cli: fix changelog encode for PY3
- PR#533: Treat canceled tasks as failed for optional_archs
- PR#686: Display license info in CLI's rpminfo and Web UI
- PR#718: convenience script to run py2 and py3 tests in parallel
- PR#722: docs: check external repos with taginfo
- PR#675: refactory cli unittests, move share code pieces to utilities library
- PR#714: Use task id as key to sort
- PR#707: add argument detection to prevent array out of index error.
- PR#717: Fix watch-tasks unit tests
- PR#615: don't send notifications to disabled users or hosts
- PR#698: set optional_arches to list
- PR#703: cli: make return code of watch_task to always ignore sub-task failure
- PR#704: cli: use strict with getTag call when appropriate
- PR#710: use `hasPerm` to check permission in save_failed_tree
- PR#699: Add documentation for storage volumes
- PR#693: Import koji.plugin explicitly
- PR#647: Don't check non-existing file
- PR#664: make grab_session_options to accept dict directly
- PR#673: functions for parsing task parameters
- PR#681: use six.StringIO everywhere
- PR#684: correct format and fix issue #682
- PR#646: Improve test coverage in koji/util
- PR#677: handle DateTime objects in encode_datetime
- PR#670: Create repo without --deltas if no old package dir is set
- PR#666: Few cheap python3 compatibilities
- PR#662: mock koji.commands._running_in_bg function to run unittest in background
- PR#645: don't fail on CLI plugins without docstrings
- PR#655: fix unreachable code
- PR#656: remove unused calls
- PR#652: add unittests for koji commands
- PR#658: consolidate safe_rmtree, rmtree and shutil.rmtree
- PR#660: more runroot tests
- PR#633: unify runroot CLI interface
- PR#649: delete build directory if cg_import fails
- PR#653: Add krb_canon_host option
- PR#657: protonmsg: include the arch in the headers of rpm sign messages
- PR#651: protonmsg: don't send rpm.sign messages when the sigkey is empty
- PR#654: Update links in docs to point to correct pages
- PR#631: cg_import fails immediately if build directory already exists
- PR#601: replace pycurl with requests
- PR#608: tests for handling user groups
- PR#637: set timezone to US/Eastern when test_build_notification executing
- PR#636: use urlparse.parse_qs instead of deprecated cgi.parse_qs
- PR#628: add a unit test for buildNotification task
- PR#620: some tests for koji.auth
- PR#625: watch-logs --mine --follow
- PR#629: fix wrong mock.patch target
- PR#598: kojira: speed up repo dist check
- PR#622: basic volume policy support
- PR#624: fix formatTime for DateTime
- PR#537: messagebus plugin: deferred sending and test mode
- PR#605: update docstring
- PR#611: the split_cli.py script is no longer needed
- PR#617: display suid bit in web ui
- PR#619: cleanup unnecessary subdir phony
- PR#606: drop importBuildInPlace call
- PR#609: move spin-livemedia to build section

* Mon Sep 25 2017 Mike McLean <mikem at redhat.com> - 1.14.0-1
- PR#597: use_old_ssl is deprecated
- PR#591: Normalize paths for scms
- PR#432: override build_arch_can_fail settings
- PR#566: allow profiles to request a specific python version
- PR#554: deprecate importBuildInPlace hub call
- PR#590: support repo_include_all tag extra option
- PR#582: Content generator metadata documentation update
- PR#579: ignore inodes when running rpmdiff.
- PR#493: modify activate_session to be easily used without CLI
- PR#589: fix scratch ref for scm callback
- PR#587: add `build_tag` argument in `postSCMCheckout` callback
- PR#583: support rpm LONG*SIZE header fields
- PR#526: Added list builds command to koji CLI
- PR#581: Add a note to get_build docstring
- PR#575: add xjb and yaml type in archivetypes table
- PR#571: Support large ints over xmlrpc using i8 tag
- PR#538: protonmsg plugin: test mode
- PR#547: update version in sphinx config
- PR#548: set task arch for indirection image builds
- PR#568: spec: use correct macro - rhel instead redhat for RHEL version
- PR#558: cli: Fix exit code for building images
- PR#559: return result status in save-failed-tree
- PR#561: rename rpm-python to python*-rpm for EOL of F24
- PR#562: fix serverca default in kojivmd
- PR#565: expose graceful reload in kojid service config and init script
- PR#544: incorrect parameter for error message
- PR#510: cli: change download-task to regular curl download
- PR#536: fix docs links, plus minor docs cleanup
- PR#539: runroot: friendlier parsing of path_subs config
- PR#542: check RPMTAG_LONGSIZE is RPMTAG_SIZE is null
- PR#419: Koji support for custom Lorax templates in LiveMedia tasks
- PR#546: fix test_krbv_disabled unit test
- PR#518: Error out if krbV is unavailable and gssapi did not work
- PR#535: datetime compatibility for plugins
- PR#524: Add support for debugsource
- PR#528: allow some missing path sections in runroot config
- PR#530: Spelling fixes
- PR#506: Track artifacts coming from koji itself
- PR#499: runroot: use /builddir/runroot.log instead of /tmp/runroot.log
- PR#509: CLI block-group command
- PR#514: Fix resubmit
- PR#521: update links in README.md
- PR#502: download-build: suppress output on quiet and add --noprogress
- PR#511: unit tests for delete_tag() [Open]
- PR#484: fix NoneType TypeError in deleteTag
- PR#490: getUserPerms should throw GenericError when no user found
- PR#497: remove deprecated buildFromCVS call
- PR#503: Remove deprecated compat_mode from runroot plugin
- PR#507: drop unused add_db_logger call and db table
- PR#508: drop mod_python support

* Fri Jun 30 2017 Mike McLean <mikem at redhat.com> - 1.13.0-1
- PR#496 Makefile/spec fixes for building on el6
- PR#491 epel-compatible macro in spec
- PR#487 alter specfile for rhel6/7
- PR#488 python2.5 doesn't know named components
- PR#400 per-tag configuration of chroot mock behaviour
- PR#480 koji_cli name interferes with new library
- PR#475 fix StringType and itervalues in plugin and cli
- PR#476 provide a temporary workdir for restart task unit tests
- PR#477 update .gitignore
- PR#465 Don't allow not-null empty arch/userID in listHosts
- PR#471 Rework build log display in web ui
- PR#472 New features for restart-hosts command
- PR#474 propagate task.assign return value
- PR#353 add pre/postSCMCheckout plugin_callbacks
- PR#199 CLI plugins
- PR#449 Make sure to fix encoding all RPM Headers
- PR#442 list-channels CLI command
- PR#445 log failed plugin
- PR#441 document easier bootstrap for groups
- PR#438 Fix traceback for missing update
- PR#453 honor --quiet in list-tagged
- PR#448 Fix python3 deps
- PR#450 epel-compatible python3 macros
- PR#444 require mod_auth_gssapi instead of mod_auth_kerb where applicable
- PR#434 devtools: fakehub and fakeweb
- PR#447 python3 docs update
- PR#417 Python3 support for CLI + XMLRPC client
- PR#421 Extend allowed_scms format to allow explicit blocks
- PR#424 handle task fault results in download-logs
- PR#431 don't inspect results for failed createImage tasks
- PR#430 note about where API docs are found
- PR#403 fixEncoding for changelogs
- PR#402 parse deleted mountpoints
- PR#418 use old tarfile arguments
- PR#422 doc: use `tag-build` instead of alias cmd `tag-pkg`
- PR#404 XZ threads are very bad about memory, so use only two threads.
- PR#408 Support proxyuser=username in krbLogin
- PR#411 Replace references to cvs with modern git examples
- PR#381 use /etc/ in the spec file
- PR#380 Make raw-xz faster by using xz threads
- PR#397 missing argument
- PR#399 Added hostinfo command to cli
- PR#401 add default_md to docs (ssl.cnf)
- PR#394 link to kojiji (Koji Java Interface)
- PR#388 Increase 50 character limit of tag names
- PR#352 Optional JSON output for 'koji call'
- PR#393 remove minor version from User-Agent header
- PR#372 update jenkins config
- PR#375 raise error on non-existing profile
- PR#382 update the 1.11 to 1.12 upgrade schema for BDR
- PR#384 Pull in some get_header_fields enhancements from Kobo
- PR#378 Couple of small fixes to the koji documentation
- PR#385 allow kojid to start when not using ssl cert auth

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
