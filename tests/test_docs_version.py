from __future__ import absolute_import
import os
import six
import subprocess
import unittest
import sys

try:
    import importlib.util
except ImportError:  # pragma: no cover
    import imp as imp
    importlib = None

# docs version lives in docs/source/conf.py
TOPDIR = os.path.dirname(__file__) + '/..'
SPHINX_CONF = TOPDIR + '/docs/source/conf.py'

if importlib:
    spec = importlib.util.spec_from_file_location("sphinx_conf", SPHINX_CONF)
    sphinx_conf = importlib.util.module_from_spec(spec)
    sys.modules["sphinx_conf"] = sphinx_conf
    spec.loader.exec_module(sphinx_conf)
else:
    sphinx_conf = imp.load_source('sphinx_conf', SPHINX_CONF)


class TestDocsVersion(unittest.TestCase):

    def get_spec(self):
        return TOPDIR + '/koji.spec'

    def get_koji_version(self):
        spec = self.get_spec()
        cmd = ['rpm', '-q', '--specfile', spec, '--qf', '%{version}\\n']
        popen = subprocess.Popen(cmd, stdout=subprocess.PIPE)
        output = popen.stdout.read()
        # rpm outputs a line for each subpackage
        version = output.splitlines()[0]
        if six.PY3:
            version = version.decode()
        return version

    def test_docs_version(self):
        koji_version = self.get_koji_version()
        self.assertEqual(koji_version, sphinx_conf.release)
        # docs 'version' is x.y instead of x.y.z
        dver = '.'.join(koji_version.split('.')[:-1])
        self.assertEqual(dver, sphinx_conf.version)
