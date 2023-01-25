# coding=utf-8
from __future__ import absolute_import
import os.path
import shutil
import tempfile
import unittest

import koji



class TestCheckSigMD5(unittest.TestCase):

    def setUp(self):
        self.tempdir = tempfile.mkdtemp()
        orig_path = os.path.join(os.path.dirname(__file__), 'data/rpms/test-deps-1-1.fc24.x86_64.rpm')
        orig_signed = os.path.join(os.path.dirname(__file__), 'data/rpms/test-deps-1-1.fc24.x86_64.rpm.signed')
        self.path = '%s/test.rpm' % self.tempdir
        self.signed = '%s/test.rpm.signed' % self.tempdir
        shutil.copyfile(orig_path, self.path)
        shutil.copyfile(orig_signed, self.signed)

    def tearDown(self):
        shutil.rmtree(self.tempdir)

    def test_spliced_sig_reader(self):
        contents_orig = open(self.path, 'rb').read()
        contents_signed = open(self.signed, 'rb').read()
        sighdr = koji.rip_rpm_sighdr(self.signed)
        contents_spliced = koji.spliced_sig_reader(self.path, sighdr).read()
        self.assertEqual(contents_signed, contents_spliced)
        self.assertNotEqual(contents_signed, contents_orig)

    def test_splice_rpm_sighdr(self):
        contents_signed = open(self.signed, 'rb').read()
        sighdr = koji.rip_rpm_sighdr(self.signed)
        dst = '%s/signed-copy.rpm' % self.tempdir
        koji.splice_rpm_sighdr(sighdr, self.path, dst=dst)
        contents_spliced = open(dst, 'rb').read()
        self.assertEqual(contents_signed, contents_spliced)
