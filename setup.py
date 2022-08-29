#!/usr/bin/env python
from __future__ import absolute_import

import os.path
from setuptools import setup


def get_install_requires():
    # To install all build requires:
    # $ dnf install python-pip git krb5-devel gcc redhat-rpm-config \
    #               glib2-devel sqlite-devel libxml2-devel python-devel \
    #               openssl-devel libffi-devel

    requires = [
        'python-dateutil',
        'requests',
        'requests-gssapi',
        'six',
        # 'libcomps',
        # 'rpm-py-installer', # it is optional feature
        # 'rpm',
    ]
    return requires


def get_version():
    cwd = os.path.dirname(__file__)
    exec(open(os.path.join(cwd, 'koji/_version.py'), 'rt').read())
    return locals()['__version__']


def get_long_description():
    cwd = os.path.dirname(__file__)
    return open(os.path.join(cwd, "README.md"), "rt").read()


setup(
    name="koji",
    version=get_version(),
    description=("Koji is a system for building and tracking RPMS. The base"
                 " package contains shared libraries and the command-line"
                 " interface."),
    long_description=get_long_description(),
    long_description_content_type='text/markdown',
    include_package_data=True,
    license="LGPLv2 and GPLv2+",
    url="http://pagure.io/koji/",
    author='Koji developers',
    author_email='koji-devel@lists.fedorahosted.org',
    classifiers=[
        "Development Status :: 5 - Production/Stable",
        "Environment :: Console",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: GNU Lesser General Public License v2 or later (LGPLv2+)",
        "Natural Language :: English",
        "Programming Language :: Python :: 2.7",
        "Programming Language :: Python :: 3",
        "Operating System :: POSIX :: Linux",
        "Topic :: Utilities"
    ],
    packages=[
        'koji',
        'koji_cli',
        'koji_cli_plugins',
    ],
    package_dir={
        'koji': 'koji',
        'koji_cli': 'cli/koji_cli',
        'koji_cli_plugins': 'plugins/cli',
    },
    package_data={
        '': ['README.md'],
    },
    # doesn't make sense, as we have only example config
    # data_files=[
    #     ('/etc', ['cli/koji.conf']),
    # ],
    scripts=[
        'cli/koji',
        'util/koji-gc',
        'util/koji-shadow',
        'util/koji-sweep-db',
        'util/kojira',
    ],
    python_requires='>=2.7',
    install_requires=get_install_requires(),
)
