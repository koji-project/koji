from __future__ import absolute_import

import mock
import optparse

import koji
import unittest

from . import loadcli

cli = loadcli.cli


class TestGetOptions(unittest.TestCase):

    def setUp(self):
        self.expanduser = mock.patch('os.path.expanduser').start()
        self.read_config = mock.patch('koji.read_config').start()
        self.config_dict = {'server': 'http://localhost/kojihub',
                            'weburl': 'http://localhost/koji',
                            'topurl': None, 'pkgurl': None, 'topdir': '/mnt/koji',
                            'max_retries': 30, 'retry_interval': 20, 'anon_retry': False,
                            'offline_retry': False, 'offline_retry_interval': 20,
                            'timeout': 50000, 'auth_timeout': 60, 'use_fast_upload': True,
                            'upload_blocksize': 1048576, 'poll_interval': 6, 'principal': None,
                            'keytab': None, 'cert': None, 'serverca': None, 'no_ssl_verify': False,
                            'authtype': None, 'debug': False, 'debug_xmlrpc': False, 'pyver': None,
                            'plugin_paths': None, 'force_auth': False, 'config': 'path/to/config'}
        self.expanduser_values = ['path/topdir', 'cert.crt', 'serverca.crt']
        self.orig_basedir = koji.BASEDIR
        self.orig_pathinfo_topdir = koji.pathinfo.topdir
        self.orig_load_plugins = cli.load_plugins
        self.load_plugins = cli.load_plugins = mock.MagicMock()

    def tearDown(self):
        koji.BASEDIR = self.orig_basedir
        koji.pathinfo.topdir = self.orig_pathinfo_topdir
        cli.load_plugins = self.orig_load_plugins
        mock.patch.stopall()

    def test_get_options(self):
        self.read_config.return_value = self.config_dict
        self.expanduser.side_effect = self.expanduser_values
        options = ['--user', 'kojiadmin', '--password', 'testpass', '--profile', 'brew',
                   '--config', 'path/to/config', '--principal', 'testuser@kerberos.org',
                   '--runas', 'testuser2', '--noauth', '--plugin-paths', 'path/to/plugins',
                   '--force-auth', '--authtype', 'kerberos', '--debug', '--debug-xmlrpc',
                   '--quiet', '--skip-main', '--server', 'https://serverkoji.com/kojihub',
                   '--topdir', 'path/topdir', '--weburl', 'http://serverkoji.com/koji',
                   '--topurl', 'http://serverkoji.com/kojifiles', '--help-commands',
                   '--keytab', 'testkeytab']
        orig = optparse.OptionParser

        def gargs(self, args):
            return options

        original_get_args = orig._get_args
        orig._get_args = gargs
        opts, cmd, args = cli.get_options()
        orig._get_args = original_get_args
        self.assertEqual(opts.user, 'kojiadmin')
        self.assertEqual(opts.password, 'testpass')
        self.assertEqual(opts.profile, 'brew')
        self.assertEqual(opts.config, 'path/to/config')
        self.assertEqual(opts.principal, 'testuser@kerberos.org')
        self.assertEqual(opts.runas, 'testuser2')
        self.assertEqual(opts.noauth, True)
        self.assertEqual(opts.force_auth, True)
        self.assertEqual(opts.plugin_paths, 'path/to/plugins')
        self.assertEqual(opts.authtype, 'kerberos')
        self.assertEqual(opts.debug, True)
        self.assertEqual(opts.debug_xmlrpc, True)
        self.assertEqual(opts.quiet, True)
        self.assertEqual(opts.skip_main, True)
        self.assertEqual(opts.server, 'https://serverkoji.com/kojihub')
        self.assertEqual(opts.topdir, 'path/topdir')
        self.assertEqual(opts.weburl, 'http://serverkoji.com/koji')
        self.assertEqual(opts.topurl, 'http://serverkoji.com/kojifiles')
        self.assertEqual(opts.help_commands, True)
        self.assertEqual(opts.keytab, 'testkeytab')
        self.load_plugins.assert_called_once_with('path/to/plugins')

    def test_get_options_shorten(self):
        self.read_config.return_value = self.config_dict
        self.expanduser.side_effect = self.expanduser_values

        options = ['-p', 'brew', '-c', 'path/to/config', '-d', '-q', '-s',
                   'https://serverkoji.com/kojihub']

        orig = optparse.OptionParser

        def gargs(self, args):
            return options

        original_get_args = orig._get_args
        orig._get_args = gargs
        opts, cmd, args = cli.get_options()
        orig._get_args = original_get_args
        self.assertEqual(opts.profile, 'brew')
        self.assertEqual(opts.config, 'path/to/config')
        self.assertEqual(opts.debug, True)
        self.assertEqual(opts.quiet, True)
        self.assertEqual(opts.server, 'https://serverkoji.com/kojihub')
        self.load_plugins.assert_called_once_with(None)
