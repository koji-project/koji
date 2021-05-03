FROM registry.fedoraproject.org/fedora:34
RUN \
  dnf -y update --nodocs --setopt=install_weak_deps=False && \
  dnf install -y --nodocs --setopt=install_weak_deps=False \
  'dnf-command(download)' \
  gcc \
  git \
  glib2-devel \
  glibc-langpack-en \
  krb5-devel \
  libffi-devel \
  python3-librepo \
  libxml2-devel \
  make \
  openssl-devel \
  python3-devel \
  python3-pip \
  python3-rpm \
  python3-tox \
  redhat-rpm-config \
  rpm-build \
  rpm-devel \
  sqlite-devel \
  yum-utils && \
  dnf clean all\
