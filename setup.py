from setuptools import setup

setup(
    name="koji",
    version="1.11.1",
    description=("Koji is a system for building and tracking RPMS. The base"
                 " package contains shared libraries and the command-line"
                 " interface."),
    license="LGPLv2 and GPLv2+",
    url="http://pagure.io/koji/",
    classifiers=[
        "Development Status :: 5 - Production/Stable",
        "Environment :: Console",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: GNU Lesser General Public License v2 or later (LGPLv2+)",
        "Programming Language :: Python :: 2 :: Only",
        "Topic :: Utilities"
    ],
    package_dir={'koji': 'koji'},
    packages=['koji', 'koji.ssl'],
    scripts=['cli/koji'],
    install_requires=[
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
        # $ ln -vs $(/usr/bin/python -c 'import rpm, os.path; print os.path.dirname(rpm.__file__)') \
        #          $(/usr/bin/env python -c 'import distutils.sysconfig; print(distutils.sysconfig.get_python_lib())')

        'pyOpenSSL',
        'python-dateutil',
        'python-krbV',
        'yum-metadata-parser',
        # Note: urlgrabber package on PyPI has still bug
        # https://bugzilla.redhat.com/show_bug.cgi?id=1200091 fixed yet.
        'urlgrabber',
    ],
    dependency_links=[
        'git+git://yum.baseurl.org/yum-metadata-parser.git#egg=yum-metadata-parser-1.1.4',
        'git+git://yum.baseurl.org/urlgrabber.git#egg=urlgrabber-3.10.1',
    ]
)
