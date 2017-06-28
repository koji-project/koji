import sys
from setuptools import setup

def get_install_requires():
    # To install all build requires:
    # $ dnf install python-pip git krb5-devel gcc redhat-rpm-config \
    #               glib2-devel sqlite-devel libxml2-devel python-devel \
    #               openssl-devel libffi-devel

    # In a perfect world this would suffice:
    # 'rpm',
    # But rpm isn't available on PyPI so it needs to be installed other way.

    # To install it from upstream one would need to run ./autogen.sh and
    # ./configure just to create setup.py with correct paths to header
    # files. I wasn't able run it successfully anyway so it is easier to
    # grab system package instead.

    # Install rpm python package system-wide:
    # $ dnf install rpm-python

    # If you are running in virtualenv use following command to make
    # system-wide rpm python package inside virtualenv:
    # $ ln -vs $(/usr/bin/python -c 'import rpm, os.path; print(os.path.dirname(rpm.__file__))') \
    #          $(/usr/bin/env python -c 'import distutils.sysconfig; print(distutils.sysconfig.get_python_lib())')
    # resp. for python3
    # $ ln -vs $(/usr/bin/python3 -c 'import rpm, os.path; print(os.path.dirname(rpm.__file__))') \
    #          $(/usr/bin/env python -c 'import distutils.sysconfig; print(distutils.sysconfig.get_python_lib())')
    # Other options is to create virtualenv with --system-site-packages if
    # it doesn't harm you.

    # pycurl can come without ssl backend (or bad one). In such case use
    # $ pip uninstall pycurl; pip install pycurl --global-option="--with-nss"
    # or different backend mentioned in error message (openssl, ...)

    requires = [
        'pyOpenSSL',
        'pycurl',
        'python-dateutil',
        'requests',
        'requests-kerberos',
        'six',
        #'libcomps',
        #'rpm',
    ]
    if sys.version_info[0] < 3:
        # optional auth library for older hubs
        # hubs >= 1.12 are using requests' default GSSAPI
        requires.append('python-krbV')
    return requires

setup(
    name="koji",
    version="1.14.0",
    description=("Koji is a system for building and tracking RPMS. The base"
                 " package contains shared libraries and the command-line"
                 " interface."),
    license="LGPLv2 and GPLv2+",
    url="http://pagure.io/koji/",
    author = 'Koji developers',
    author_email = 'koji-devel@lists.fedorahosted.org',
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
    packages=['koji', 'koji.ssl', 'koji_cli'],
    package_dir={
        'koji': 'koji',
        'koji_cli': 'cli/koji_cli',
    },
    # doesn't make sense, as we have only example config
    #data_files=[
    #    ('/etc', ['cli/koji.conf']),
    #],
    scripts=['cli/koji'],
    python_requires='>=2.6',
    install_requires=get_install_requires(),
)
