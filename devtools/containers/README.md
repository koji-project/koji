Dockerfiles for development
===========================

To facilitate in development - specifically, running tests, two Dockerfiles are
provided:

* [`./centos/Dockerfile`](./centos/Dockerfile) CentOS 6, for testing with python2.6
* [`./fedora/Dockerfile`](./fedora/Dockerfile) Fedora 32, for testing with python3.8

To use them, taking fedora as an example:

    docker build -t koji_test_fedora:latest --no-cache ./devtools/containers/fedora
    docker run --rm -v $PWD:/koji --name koji_test koji_test_fedora:latest bash -c "cd /koji && tox -e flake8,py3"

Or CentOS as an example:

    docker build -t koji_test_centos:latest --no-cache ./devtools/containers/centos
    docker run --rm -v $PWD:/koji --name koji_test koji_test_centos:latest bash -c "cd /koji && tox -e py2"

When running with Podman and SELinux enabled, use the "--security-opt
label=disable" option:

    podman run --rm -v $PWD:/koji --security-opt label=disable --name koji_test koji_test_fedora:latest bash -c "cd /koji && ls -l /koji && tox -e flake8,py3"
