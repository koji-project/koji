import os
import re
import time
from optparse import Values

import six
import mock

import koji
from koji_cli.commands import anon_handle_list_targets
from . import utils

_mock_targets = [
    {
        'build_tag': 10,
        'build_tag_name': 'f33-build',
        'dest_tag': 20,
        'dest_tag_name':
        'f33-updates-candidate',
        'id': 1,
        'name': 'f33'
    }
]


class TestCliListTargets(utils.CliTestCase):
    def setUp(self):
        self.original_timezone = os.environ.get('TZ')
        os.environ['TZ'] = 'US/Eastern'
        time.tzset()

    def tearDown(self):
        if self.original_timezone is None:
            del os.environ['TZ']
        else:
            os.environ['TZ'] = self.original_timezone
        time.tzset()

    @mock.patch('sys.stderr', new_callable=six.StringIO)
    @mock.patch('koji_cli.commands.activate_session')
    def test_list_targets_error_args(self, ensure_connection_mock, stderr):
        session = mock.MagicMock(getAPIVersion=lambda: koji.API_VERSION,
                                 getBuildTargets=lambda n: [])
        options = mock.MagicMock(quiet=False)
        with self.assertRaises(SystemExit) as ex:
            anon_handle_list_targets(options, session, ['aaa'])
        self.assertExitCode(ex, 2)

    @mock.patch('sys.stderr', new_callable=six.StringIO)
    @mock.patch('koji_cli.commands.activate_session')
    def test_list_targets_error_all_not_found(self, ensure_connection_mock, stderr):
        session = mock.MagicMock(getAPIVersion=lambda: koji.API_VERSION,
                                 getBuildTargets=lambda n: [])
        options = mock.MagicMock(quiet=False)
        with self.assertRaises(SystemExit) as ex:
            anon_handle_list_targets(options, session, [])
        self.assertExitCode(ex, 2)
        self.assertTrue('No targets were found' in stderr.getvalue())

    @mock.patch('optparse.OptionParser.parse_args',
                return_value=(Values({'quiet': False, 'name': 'f50'}), []))
    @mock.patch('sys.stderr', new_callable=six.StringIO)
    @mock.patch('koji_cli.commands.activate_session')
    def test_list_targets_error_name_not_found(self, ensure_connection_mock, stderr, opt):
        session = mock.MagicMock(getAPIVersion=lambda: koji.API_VERSION,
                                 getBuildTargets=lambda n: [])
        options = mock.MagicMock(quiet=False)
        with self.assertRaises(SystemExit) as ex:
            anon_handle_list_targets(options, session, [])
        self.assertExitCode(ex, 2)
        self.assertTrue('No such build target:' in stderr.getvalue())

    @mock.patch('sys.stdout', new_callable=six.StringIO)
    @mock.patch('koji_cli.commands.activate_session')
    def test_list_targets_all(self, ensure_connection_mock, stdout):
        session = mock.MagicMock(getAPIVersion=lambda: koji.API_VERSION,
                                 getBuildTargets=lambda n: _mock_targets)
        options = mock.MagicMock(quiet=False)
        anon_handle_list_targets(options, session, [])
        expected = [
            'Name|Buildroot|Destination|',
            '---------------------------------------------------------------------------------------------',
            'f33|f33-build|f33-updates-candidate|',
            ''
        ]
        self.assertEqual(expected, [re.sub(' +', '|', l) for l in stdout.getvalue().split('\n')])

    @mock.patch('optparse.OptionParser.parse_args',
                return_value=(Values({'quiet': False, 'name': 'f50'}), []))
    @mock.patch('sys.stdout', new_callable=six.StringIO)
    @mock.patch('koji_cli.commands.activate_session')
    def test_list_targets_one(self, ensure_connection_mock, stdout, opt):
        session = mock.MagicMock(getAPIVersion=lambda: koji.API_VERSION,
                                 getBuildTargets=lambda n: _mock_targets)
        options = mock.MagicMock(quiet=False)
        anon_handle_list_targets(options, session, [])
        expected = [
            'Name|Buildroot|Destination|',
            '---------------------------------------------------------------------------------------------',
            'f33|f33-build|f33-updates-candidate|',
            ''
        ]
        self.assertEqual(expected, [re.sub(' +', '|', l) for l in stdout.getvalue().split('\n')])
