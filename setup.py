from __future__ import absolute_import

import sys

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
    # since pyOpenSSL-18.0.0, py26 support is dropped
    # see https://pagure.io/koji/issue/1060
    if sys.version_info[0] == 2 and sys.version_info[1] < 7:
        requires.append('pyOpenSSL<18.0.0')
    else:
        requires.append('pyOpenSSL')

    return requires


setup(
    name="koji",
    version="1.22.1",
    description=("Koji is a system for building and tracking RPMS. The base"
                 " package contains shared libraries and the command-line"
                 " interface."),
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
        "Programming Language :: Python :: 2.6",
        "Programming Language :: Python :: 2.7",
        "Programming Language :: Python :: 3",
        "Operating System :: POSIX :: Linux",
        "Topic :: Utilities"
    ],
    packages=['koji', 'koji_cli', 'koji_cli_plugins'],
    package_dir={
        'koji': 'koji',
        'koji_cli': 'cli/koji_cli',
        'koji_cli_plugins': 'plugins/cli',
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
    python_requires='>=2.6',
    install_requires=get_install_requires(),
)
