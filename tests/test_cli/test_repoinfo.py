from __future__ import absolute_import

import unittest

import mock
import shutil
import six
import tempfile

from koji_cli.commands import anon_handle_repoinfo

import koji
from . import utils


class TestRepoinfo(utils.CliTestCase):

    def __vm(self, result):
        m = koji.VirtualCall('mcall_method', [], {})
        if isinstance(result, dict) and result.get('faultCode'):
            m._result = result
        else:
            m._result = (result,)
        return m

    def setUp(self):
        # Show long diffs in error output...
        self.maxDiff = None
        self.options = mock.MagicMock()
        self.options.debug = False
        self.session = mock.MagicMock()
        self.session.getAPIVersion.return_value = koji.API_VERSION
        self.ensure_connection = mock.patch('koji_cli.commands.ensure_connection').start()
        self.tempdir = tempfile.mkdtemp()
        self.error_format = """Usage: %s repoinfo [options] <repo-id> [<repo-id> ...]
(Specify the --help global option for a list of other help options)

%s: error: {message}
""" % (self.progname, self.progname)
        self.repo_id = '123'
        self.multi_broots = [
            {'id': 1101, 'repo_id': 101, 'tag_name': 'tag_101', 'arch': 'x86_64'},
            {'id': 1111, 'repo_id': 111, 'tag_name': 'tag_111', 'arch': 'x86_64'},
            {'id': 1121, 'repo_id': 121, 'tag_name': 'tag_121', 'arch': 'x86_64'}
        ]

    def tearDown(self):
        mock.patch.stopall()
        shutil.rmtree(self.tempdir)

    @mock.patch('koji.formatTimeLong', return_value='Thu, 01 Jan 2000')
    @mock.patch('sys.stderr', new_callable=six.StringIO)
    @mock.patch('sys.stdout', new_callable=six.StringIO)
    def test_repoinfo_valid_not_dist_repo_with_buildroot_opt(self, stdout, stderr, formattimelong):
        repoinfo = {'external_repo_id': 1, 'id': self.repo_id, 'tag_id': 11,
                    'tag_name': 'test-tag', 'state': 1, 'create_ts': 1632914520.353734,
                    'create_event': 999, 'dist': False, 'task_id': 555}
        self.options.topurl = 'https://www.domain.local'
        mcall = self.session.multicall.return_value.__enter__.return_value
        mcall.repoInfo.return_value = self.__vm(repoinfo)
        self.session.listBuildroots.return_value = self.multi_broots
        arguments = [self.repo_id, '--buildroots']
        rv = anon_handle_repoinfo(self.options, self.session, arguments)
        url = '{}/repos/test-tag/123'.format(self.options.topurl)
        repo_json = '{}/repos/test-tag/123/repo.json'.format(self.options.topurl)
        expected = """ID: %s
Tag ID: %d
Tag name: %s
State: %s
Created: Thu, 01 Jan 2000
Created event: %d
URL: %s
Repo json: %s
Dist repo?: no
Task ID: %d
Number of buildroots: 3
Buildroots ID:
               1101
               1111
               1121
""" % (self.repo_id, repoinfo['tag_id'], repoinfo['tag_name'],
       koji.REPO_STATES[repoinfo['state']], repoinfo['create_event'], url, repo_json,
       repoinfo['task_id'])
        actual = stdout.getvalue()
        self.assertMultiLineEqual(actual, expected)
        actual = stderr.getvalue()
        expected = ''
        self.assertMultiLineEqual(actual, expected)
        self.assertEqual(rv, None)

        self.ensure_connection.assert_called_once_with(self.session, self.options)
        self.session.multicall.assert_called_once()
        self.session.repoInfo.assert_not_called()
        self.session.listBuildroots.assert_called_once_with(repoID=self.repo_id)

    @mock.patch('koji.formatTimeLong', return_value='Thu, 01 Jan 2000')
    @mock.patch('sys.stderr', new_callable=six.StringIO)
    @mock.patch('sys.stdout', new_callable=six.StringIO)
    def test_repoinfo_valid_dist_repo(self, stdout, stderr, formattimelong):
        repoinfo = {'external_repo_id': 1, 'id': self.repo_id, 'tag_id': 11,
                    'tag_name': 'test-tag', 'state': 1, 'create_ts': 1632914520.353734,
                    'create_event': 999, 'dist': True, 'task_id': 555}
        mcall = self.session.multicall.return_value.__enter__.return_value
        mcall.repoInfo.return_value = self.__vm(repoinfo)
        self.session.listBuildroots.return_value = self.multi_broots
        self.options.topurl = 'https://www.domain.local'
        arguments = [self.repo_id]
        rv = anon_handle_repoinfo(self.options, self.session, arguments)
        url = '{}/repos/test-tag/123'.format(self.options.topurl)
        repo_json = '{}/repos-dist/test-tag/123/repo.json'.format(self.options.topurl)
        expected = """ID: %s
Tag ID: %d
Tag name: %s
State: %s
Created: Thu, 01 Jan 2000
Created event: %d
URL: %s
Repo json: %s
Dist repo?: yes
Task ID: %d
Number of buildroots: 3
""" % (self.repo_id, repoinfo['tag_id'], repoinfo['tag_name'],
       koji.REPO_STATES[repoinfo['state']], repoinfo['create_event'], url, repo_json,
       repoinfo['task_id'])
        actual = stdout.getvalue()
        self.assertMultiLineEqual(actual, expected)
        actual = stderr.getvalue()
        expected = ''
        self.assertMultiLineEqual(actual, expected)
        self.assertEqual(rv, None)

        self.ensure_connection.assert_called_once_with(self.session, self.options)
        self.session.multicall.assert_called_once()
        self.session.repoInfo.assert_not_called()
        self.session.listBuildroots.assert_called_once_with(repoID=self.repo_id)

    @mock.patch('koji.formatTimeLong', return_value='Thu, 01 Jan 2000')
    @mock.patch('sys.stderr', new_callable=six.StringIO)
    @mock.patch('sys.stdout', new_callable=six.StringIO)
    def test_repoinfo_valid_buildroot_not_available_on_hub(self, stdout, stderr, formattimelong):
        repoinfo = {'external_repo_id': 1, 'id': self.repo_id, 'tag_id': 11,
                    'tag_name': 'test-tag', 'state': 1, 'create_ts': 1632914520.353734,
                    'create_event': 999, 'dist': False, 'task_id': 555}
        self.options.topurl = 'https://www.domain.local'
        mcall = self.session.multicall.return_value.__enter__.return_value
        mcall.repoInfo.return_value = self.__vm(repoinfo)
        self.session.listBuildroots.side_effect = koji.ParameterError
        arguments = [self.repo_id, '--buildroots']
        rv = anon_handle_repoinfo(self.options, self.session, arguments)
        url = '{}/repos/test-tag/123'.format(self.options.topurl)
        repo_json = '{}/repos/test-tag/123/repo.json'.format(self.options.topurl)
        expected = """ID: %s
Tag ID: %d
Tag name: %s
State: %s
Created: Thu, 01 Jan 2000
Created event: %d
URL: %s
Repo json: %s
Dist repo?: no
Task ID: %d
""" % (self.repo_id, repoinfo['tag_id'], repoinfo['tag_name'],
       koji.REPO_STATES[repoinfo['state']], repoinfo['create_event'], url, repo_json,
       repoinfo['task_id'])
        actual = stdout.getvalue()
        self.assertMultiLineEqual(actual, expected)
        actual = stderr.getvalue()
        expecter_warn = "--buildroots option is available with hub 1.33 or newer\n"
        self.assertMultiLineEqual(actual, expecter_warn)
        self.assertEqual(rv, None)

        self.ensure_connection.assert_called_once_with(self.session, self.options)
        self.session.multicall.assert_called_once()
        self.session.repoInfo.assert_not_called()
        self.session.listBuildroots.assert_called_once_with(repoID=self.repo_id)

    @mock.patch('koji.formatTimeLong', return_value='Thu, 01 Jan 2000')
    @mock.patch('sys.stderr', new_callable=six.StringIO)
    @mock.patch('sys.stdout', new_callable=six.StringIO)
    def test_repoinfo_valid_without_buildroot_not_available_on_hub(
            self, stdout, stderr, formattimelong):
        repoinfo = {'external_repo_id': 1, 'id': self.repo_id, 'tag_id': 11,
                    'tag_name': 'test-tag', 'state': 1, 'create_ts': 1632914520.353734,
                    'create_event': 999, 'dist': False, 'task_id': 555}
        self.options.topurl = 'https://www.domain.local'
        mcall = self.session.multicall.return_value.__enter__.return_value
        mcall.repoInfo.return_value = self.__vm(repoinfo)
        self.session.listBuildroots.side_effect = koji.ParameterError
        arguments = [self.repo_id]
        rv = anon_handle_repoinfo(self.options, self.session, arguments)
        url = '{}/repos/test-tag/123'.format(self.options.topurl)
        repo_json = '{}/repos/test-tag/123/repo.json'.format(self.options.topurl)
        expected = """ID: %s
Tag ID: %d
Tag name: %s
State: %s
Created: Thu, 01 Jan 2000
Created event: %d
URL: %s
Repo json: %s
Dist repo?: no
Task ID: %d
""" % (self.repo_id, repoinfo['tag_id'], repoinfo['tag_name'],
       koji.REPO_STATES[repoinfo['state']], repoinfo['create_event'], url, repo_json,
       repoinfo['task_id'])
        actual = stdout.getvalue()
        self.assertMultiLineEqual(actual, expected)
        actual = stderr.getvalue()
        expecter_warn = ""
        self.assertMultiLineEqual(actual, expecter_warn)
        self.assertEqual(rv, None)

        self.ensure_connection.assert_called_once_with(self.session, self.options)
        self.session.multicall.assert_called_once()
        self.session.repoInfo.assert_not_called()
        self.session.listBuildroots.assert_called_once_with(repoID=self.repo_id)

    @mock.patch('sys.stdout', new_callable=six.StringIO)
    @mock.patch('sys.stderr', new_callable=six.StringIO)
    def test_repoinfo__not_exist_repo(self, stderr, stdout):
        mcall = self.session.multicall.return_value.__enter__.return_value
        mcall.repoInfo.return_value = self.__vm(None)
        arguments = [self.repo_id]
        rv = anon_handle_repoinfo(self.options, self.session, arguments)
        actual = stderr.getvalue()
        expected = "No such repo: %s\n\n" % self.repo_id
        self.assertMultiLineEqual(actual, expected)
        actual = stdout.getvalue()
        expected = ''
        self.assertMultiLineEqual(actual, expected)
        self.assertEqual(rv, None)

        self.ensure_connection.assert_called_once_with(self.session, self.options)
        self.session.multicall.assert_called_once()
        self.session.repoInfo.assert_not_called()
        self.session.listBuildroots.assert_not_called()

    def test_repoinfo_without_args(self):
        arguments = []
        # Run it and check immediate output
        self.assert_system_exit(
            anon_handle_repoinfo,
            self.options, self.session, arguments,
            stderr=self.format_error_message('Please specify a repo ID'),
            stdout='',
            activate_session=None,
            exit_code=2)

        # Finally, assert that things were called as we expected.
        self.ensure_connection.assert_not_called()
        self.session.repoInfo.assert_not_called()
        self.session.listBuildroots.assert_not_called()

    def test_repoinfo_help(self):
        self.assert_help(
            anon_handle_repoinfo,
            """Usage: %s repoinfo [options] <repo-id> [<repo-id> ...]
(Specify the --help global option for a list of other help options)

Options:
  -h, --help    show this help message and exit
  --buildroots  Prints list of buildroot IDs
""" % self.progname)

    if __name__ == '__main__':
        unittest.main()
