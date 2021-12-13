Dockerfiles for development
===========================

To facilitate in development - specifically, running tests, some Dockerfiles are
provided:

* [`./Dockerfile.centos7`](./Dockerfile.centos7) CentOS 7, for testing with python2.7
* [`./Dockerfile.centos8`](./Dockerfile.centos8) CentOS 8, for testing with python3.6
* [`./Dockerfile.f32`](./Dockerfile.f32) Fedora 32, for testing with python3.8
* [`./Dockerfile.f33`](./Dockerfile.f33) Fedora 33, for testing with python3.9
* [`./Dockerfile.rawhide`](./Dockerfile.rawhie) Fedora Rawhide, for testing with python3.?

To use them, taking fedora as an example:

    docker build -t koji_test_fedora:32 --no-cache -f Dockerfile.f32
    docker run --rm -v $PWD:/koji --name koji_test koji_test_fedora:32 bash -c "cd /koji && tox -e flake8,py3"

Or CentOS as an example:

    docker build -t koji_test_centos:8 --no-cache -f Dockerfile.centos8
    docker run --rm -v $PWD:/koji --name koji_test koji_test_centos:8 bash -c "cd /koji && tox -e py2"

When running with Podman and SELinux enabled, use the "--security-opt
label=disable" option:

    podman run --rm -v $PWD:/koji --security-opt label=disable --name koji_test koji_test_fedora:32 bash -c "cd /koji && ls -l /koji && tox -e flake8,py3"
