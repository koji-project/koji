# coding=utf-8
from __future__ import absolute_import
import os.path
import shutil
import tempfile
try:
    import unittest2 as unittest
except ImportError:
    import unittest

from koji.util import check_sigmd5


class TestCheckSigMD5(unittest.TestCase):

    def setUp(self):
        self.tempdir = tempfile.mkdtemp()
        orig_path = os.path.join(os.path.dirname(__file__), 'data/rpms/test-deps-1-1.fc24.x86_64.rpm')
        self.path = '%s/test.rpm' % self.tempdir
        shutil.copyfile(orig_path, self.path)

    def tearDown(self):
        shutil.rmtree(self.tempdir)

    def test_check_sigmd5_good(self):
        value = check_sigmd5(self.path)
        self.assertEqual(value, True)

    def test_check_sigmd5_bad(self):
        # corrupt the file by truncating it
        with open(self.path, 'a+b') as f:
            f.seek(5, 2)
            f.truncate()
        value = check_sigmd5(self.path)
        self.assertEqual(value, False)
