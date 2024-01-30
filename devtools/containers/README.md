Dockerfiles for development
===========================

To facilitate in development - specifically, running tests, some Dockerfiles are
provided:

* [`./Dockerfile.centos7`](./Dockerfile.centos7) CentOS 7, for testing with python2.7
* [`./Dockerfile.centos8`](./Dockerfile.centos8) CentOS 8, for testing with python3.6
* [`./Dockerfile.centos9`](./Dockerfile.centos8) CentOS 9, for testing with python3.9
* [`./Dockerfile.f34`](...) Fedora 34, for testing with python3.9
* [`./Dockerfile.f35`](./Dockerfile.f32) Fedora 35, for testing with python3.10
* [`./Dockerfile.f36`](./Dockerfile.f32) Fedora 36, for testing with python3.10
* [`./Dockerfile.f37`](./Dockerfile.f32) Fedora 37, for testing with python3.11
* [`./Dockerfile.f38`](./Dockerfile.f32) Fedora 38, for testing with python3.11
* [`./Dockerfile.f39`](./Dockerfile.f32) Fedora 39, for testing with python3.12
* [`./Dockerfile.rawhide`](./Dockerfile.rawhie) Fedora Rawhide, for testing with python3.?

To use them, taking fedora as an example:

    docker build -t koji_test_fedora:39 --no-cache -f Dockerfile.f39
    docker run --rm -v $PWD:/koji --name koji_test koji_test_fedora:39 bash -c "cd /koji && tox -e flake8,py3,bandit"

Or CentOS with py3 as an example:

    docker build -t koji_test_centos:8 --no-cache -f Dockerfile.centos8
    docker run --rm -v $PWD:/koji --name koji_test koji_test_centos:8 bash -c "cd /koji && tox -e flake8,py3,bandit"

Or CentOS with py2 as an example:

    docker build -t koji_test_centos:7 --no-cache -f Dockerfile.centos8
    docker run --rm -v $PWD:/koji --name koji_test koji_test_centos:7 bash -c "cd /koji && tox -e py2"

When running with Podman and SELinux enabled, use the "--security-opt
label=disable" option:

    podman run --rm -v $PWD:/koji --security-opt label=disable --name koji_test koji_test_fedora:39 bash -c "cd /koji && ls -l /koji && tox -e flake8,py3,bandit"
