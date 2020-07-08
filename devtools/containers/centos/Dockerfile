FROM centos:6
RUN \
  yum install -y \
    gcc \
    git \
    make \
    krb5-devel \
    libffi-devel \
    openssl-devel \
    pyOpenSSL \
    python-devel \
    redhat-rpm-config \
    rpm-build \
    rpm-python \
    yum-utils && \
  yum install -y epel-release && \
  yum install -y \
    python-flake8 \
    python-pip \
    python-psycopg2 \
    python-qpid-proton \
    python-requests-kerberos && \
  pip install -U 'pip==9.0.1' && \
  pip install -U tox
