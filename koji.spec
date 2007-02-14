%{!?python_sitelib: %define python_sitelib %(%{__python} -c "from distutils.sysconfig import get_python_lib; print get_python_lib()")}

%define testbuild 1
%define debug_package %{nil}

%define baserelease 5
%if %{testbuild}
%define release %{baserelease}.%(date +%%Y%%m%%d.%%H%%M.%%S)
%else
%define release %{baserelease}
%endif
Name: koji
Version: 0.9.5
Release: %{release}%{?dist}
License: LGPL
Summary: Build system tools
Group: Applications/System
Source: koji-%{PACKAGE_VERSION}.tar.bz2
BuildRoot: %(mktemp -d %{_tmppath}/%{name}-%{version}-%{release}-XXXXXX)
BuildArch: noarch
Requires: python-krbV >= 1.0.13
BuildRequires: python

%description
Koji is a system for building and tracking RPMS.  The base package
contains shared libraries and the command-line interface.

%package hub
Summary: Koji XMLRPC interface
Group: Applications/Internet
Requires: httpd
Requires: mod_python
Requires: postgresql-python
Requires: koji = %{version}-%{release}

%description hub
koji-hub is the XMLRPC interface to the koji database

%package builder
Summary: Koji RPM builder daemon
Group: Applications/System
Requires: koji = %{version}-%{release}
Requires: mock >= 0.5-3
Requires(post): /sbin/chkconfig
Requires(post): /sbin/service
Requires(preun): /sbin/chkconfig
Requires(preun): /sbin/service
Requires(pre): /usr/sbin/useradd
Requires: cvs
Requires: rpm-build
Requires: redhat-rpm-config
Requires: createrepo >= 0.4.4-3

%description builder
koji-builder is the daemon that runs on build machines and executes
tasks that come through the Koji system.

%package utils
Summary: Koji Utilities
Group: Applications/Internet
Requires: postgresql-python
Requires: koji = %{version}-%{release}
Requires: rpm-build
Requires: createrepo >= 0.4.4-3

%description utils
Utilities for the Koji system

%package web
Summary: Koji Web UI
Group: Applications/Internet
Requires: httpd
Requires: mod_python
Requires: mod_auth_kerb
Requires: postgresql-python
Requires: python-cheetah
Requires: koji = %{version}-%{release}
Requires: python-krbV >= 1.0.13

%description web
koji-web is a web UI to the Koji system.

%prep
%setup -q

%build

%install
rm -rf $RPM_BUILD_ROOT
make DESTDIR=$RPM_BUILD_ROOT install

%clean
rm -rf $RPM_BUILD_ROOT

%files
%defattr(-,root,root)
%{_bindir}/*
%{python_sitelib}/koji
%config(noreplace) %{_sysconfdir}/koji.conf
%doc docs

%files hub
%defattr(-,root,root)
%{_var}/www/koji-hub
%config(noreplace) /etc/httpd/conf.d/kojihub.conf

%files utils
%defattr(-,root,root)
%{_sbindir}/kojira
%config %{_initrddir}/kojira
%config %{_sysconfdir}/sysconfig/kojira
%config(noreplace) %{_sysconfdir}/kojira.conf

%files web
%defattr(-,root,root)
%{_var}/www/koji-web
%config(noreplace) /etc/httpd/conf.d/kojiweb.conf

%files builder
%defattr(-,root,root)
%{_sbindir}/kojid
%config %{_initrddir}/kojid
%config %{_sysconfdir}/sysconfig/kojid
%config(noreplace) %{_sysconfdir}/kojid.conf
%attr(-,kojibuilder,kojibuilder) /etc/mock/koji

%pre builder
/usr/sbin/useradd -r -s /bin/bash -G mock -d /builddir -M kojibuilder 2>/dev/null ||:

%post builder
/sbin/chkconfig --add kojid
/sbin/service kojid condrestart &> /dev/null || :

%preun builder
if [ $1 = 0 ]; then
  /sbin/service kojid stop &> /dev/null
  /sbin/chkconfig --del kojid
fi

%post utils
/sbin/chkconfig --add kojira
/sbin/service kojira condrestart &> /dev/null || :
%preun utils
if [ $1 = 0 ]; then
  /sbin/service kojira stop &> /dev/null || :
  /sbin/chkconfig --del kojira
fi

%changelog
* Sun Feb 04 2007 Mike McLean <mikem@redhat.com> - 0.9.5-1
- project renamed to koji
