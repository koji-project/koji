from unittest import mock
import configparser
import os
import shutil
import tempfile
import unittest

import koji
import kojihub
from kojihub import kojixmlrpc


class TestHubConfig(unittest.TestCase):

    def setUp(self):
        self.context = mock.patch('kojihub.kojihub.context').start()
        self.tempdir = tempfile.mkdtemp()
        self.environ = {
            'koji.hub.ConfigFile': self.tempdir + '/hub.conf',
            'koji.hub.ConfigDir': self.tempdir + '/hub.conf.d',
        }
        # make an empty .d dir
        os.mkdir(self.tempdir + '/hub.conf.d')
        self.write_config({})

    def tearDown(self):
        shutil.rmtree(self.tempdir)
        mock.patch.stopall()

    def write_config(self, data):
        """Write given values to test config file"""
        cfg = configparser.RawConfigParser()
        cfg.add_section('hub')
        for key in data:
            cfg.set('hub', key, data[key])
        with open(self.tempdir + '/hub.conf', 'wt') as fp:
            cfg.write(fp)

    def write_config_string(self, config):
        with open(self.tempdir + '/hub.conf', 'wt') as fp:
            fp.write(config)

    def test_defaults(self):
        # blank config should get us all default opts
        opts = kojixmlrpc.load_config(self.environ)

        for name, dtype, default in kojixmlrpc.config_map:
            self.assertIn(name, opts)
            value = opts[name]
            self.assertEqual(value, default)

    def test_values(self):
        config_data = {
            'CheckClientIP': False,
            'DBHost': 'localhost',
            'DBPort': 1234,
        }
        self.write_config(config_data)

        opts = kojixmlrpc.load_config(self.environ)

        for key in config_data:
            self.assertEqual(config_data[key], opts[key])

    def test_kojidir(self):
        config_data = {
            'KojiDir': self.tempdir,
        }
        self.write_config(config_data)

        opts = kojixmlrpc.load_config(self.environ)

        self.assertEqual(config_data['KojiDir'], opts['KojiDir'])
        self.assertEqual(config_data['KojiDir'], koji.BASEDIR)
        self.assertEqual(config_data['KojiDir'], koji.pathinfo.topdir)

    def test_invalid_dtype(self):
        bad_row = ['BadOpt', 'badtype', None]
        self.write_config({'BadOpt': '1234'})

        with mock.patch('kojihub.kojixmlrpc.config_map', new=kojixmlrpc.config_map + [bad_row]):
            with self.assertRaises(ValueError) as ex:
                kojixmlrpc.load_config(self.environ)

        expected = 'Invalid data type badtype for BadOpt option'
        self.assertEqual(str(ex.exception), expected)


    def test_policy(self):
        config = '''
[policy]
channel =
    has req_channel :: req
    is_child_task :: parent
    method newRepo :: use createrepo
    all :: use default
'''
        self.write_config_string(config)

        kojixmlrpc.load_config(self.environ)


# the end
