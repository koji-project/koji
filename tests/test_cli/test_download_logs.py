from __future__ import absolute_import

try:
    from unittest import mock
except ImportError:
    import mock
import six

from koji_cli.commands import anon_handle_download_logs
from . import utils


class TestDownloadLogs(utils.CliTestCase):
    def mock_builtin_open(self, filepath, *args):
        if filepath in self.custom_open:
            return self.custom_open[filepath]
        return self.builtin_open(filepath, *args)

    def setUp(self):
        # Mock out the options parsed in main
        self.options = mock.MagicMock()
        self.options.quiet = None
        self.maxDiff = None
        self.options.topurl = 'https://topurl'
        # Mock out the xmlrpc server
        self.session = mock.MagicMock()
        self.list_task_output_all_volumes = mock.patch(
            'koji_cli.commands.list_task_output_all_volumes').start()
        self.ensuredir = mock.patch('koji.ensuredir').start()
        self.download_file = mock.patch('koji_cli.commands.download_file').start()
        self.ensure_connection = mock.patch('koji_cli.commands.ensure_connection').start()
        self.stdout = mock.patch('sys.stdout', new_callable=six.StringIO).start()
        self.error_format = """Usage: %s download-logs [options] <task_id> [<task_id> ...]
       %s download-logs [options] --nvr <n-v-r> [<n-v-r> ...]

Note this command only downloads task logs, not build logs.

(Specify the --help global option for a list of other help options)

%s: error: {message}
""" % (self.progname, self.progname, self.progname)
        self.nvr = 'bash-1.2.3-f26'
        self.task_id = 123456

        self.builtin_open = None
        if six.PY2:
            self.builtin_open = __builtins__['open']
        else:
            import builtins
            self.builtin_open = builtins.open
        self.custom_open = {}

    def tearDown(self):
        mock.patch.stopall()

    def test_anon_handle_download_logs_wrong_value(self):
        task_id = 'bogus_task_id'
        self.assert_system_exit(
            anon_handle_download_logs,
            self.options, self.session, [task_id],
            stdout='',
            stderr='Task id must be a number: %r\n' % task_id,
            activate_session=None,
            exit_code=1
        )
        self.session.getBuild.assert_not_called()
        self.session.getTaskInfo.assert_not_called()
        self.session.downloadTaskOutput.assert_not_called()
        self.session.getTaskChildren.assert_not_called()

    def test_anon_handle_download_logs_no_arg(self):
        expected = self.format_error_message('Please specify at least one task id or n-v-r')
        self.assert_system_exit(
            anon_handle_download_logs,
            self.options, self.session, [],
            stdout='',
            stderr=expected,
            activate_session=None,
            exit_code=2
        )
        self.session.getBuild.assert_not_called()
        self.session.getTaskInfo.assert_not_called()
        self.session.downloadTaskOutput.assert_not_called()
        self.session.getTaskChildren.assert_not_called()

    def test_anon_handle_download_logs_wrong_nvr(self):

        self.session.getBuild.return_value = None

        self.assert_system_exit(
            anon_handle_download_logs,
            self.options, self.session, ['--nvr', self.nvr],
            stdout='',
            stderr='There is no build with n-v-r: %s\n' % self.nvr,
            activate_session=None,
            exit_code=1
        )

        self.session.getBuild.assert_called_once_with(self.nvr)
        self.session.getTaskInfo.assert_not_called()
        self.session.downloadTaskOutput.assert_not_called()
        self.session.getTaskChildren.assert_not_called()

    def test_anon_handle_download_logs_nvr(self):
        self.session.getBuild.return_value = {'task_id': self.task_id}
        self.session.getTaskInfo.return_value = {
            'arch': 'x86_64',
            'state': 'CLOSED',
        }
        self.list_task_output_all_volumes.return_value = {}
        self.session.getTaskChildren.side_effect = [[{'id': 23}], []]

        rv = anon_handle_download_logs(self.options, self.session, ['--nvr', self.nvr])
        actual = self.stdout.getvalue()
        expected = 'Using task ID: %s\n' % self.task_id
        self.assertMultiLineEqual(actual, expected)
        self.assertIsNone(rv)

        self.session.getBuild.assert_called_once_with(self.nvr)
        self.session.getTaskInfo.assert_has_calls([mock.call(self.task_id), mock.call(23), ])
        self.session.downloadTaskOutput.assert_not_called()
        self.session.getTaskChildren.assert_has_calls([mock.call(self.task_id), mock.call(23), ])

    def test_anon_handle_download_logs_nvr_without_task_id(self):
        self.session.getBuild.return_value = {'build_id': 1, 'nvr': self.nvr}
        rv = anon_handle_download_logs(self.options, self.session, ['--nvr', self.nvr])
        actual = self.stdout.getvalue()
        expected = 'Using build ID: 1\n'
        self.assertMultiLineEqual(actual, expected)
        self.assertIsNone(rv)

        self.session.getBuild.assert_called_once_with(self.nvr)
        self.session.getTaskInfo.assert_not_called()
        self.session.downloadTaskOutput.assert_not_called()
        self.session.getTaskChildren.assert_not_called()

    def test_anon_handle_download_logs(self):
        self.session.getTaskInfo.return_value = {
            'arch': 'x86_64',
            'state': 'CLOSED',
        }
        self.list_task_output_all_volumes.return_value = {
            'file1.log': ['volume1'],
            'file2_not_log': ['volume2'],
        }
        self.session.downloadTaskOutput.side_effect = ['abcde', '']
        out_file = six.StringIO()
        self.custom_open['kojilogs/x86_64-123456/volume1/file1.log'] = out_file

        if six.PY2:
            target = '__builtin__.open'
        else:
            target = 'builtins.open'
        with mock.patch(target, new=self.mock_builtin_open):
            anon_handle_download_logs(self.options, self.session, [str(self.task_id)])

        self.session.getTaskInfo.assert_called_once_with(self.task_id)
        self.list_task_output_all_volumes.assert_called_once_with(self.session, self.task_id)
        self.assertTrue(out_file.closed)
        self.assertEqual(self.session.downloadTaskOutput.call_count, 2)
        self.session.downloadTaskOutput.assert_has_calls([
            mock.call(self.task_id, 'file1.log', offset=0, size=102400, volume='volume1'),
            mock.call(self.task_id, 'file1.log', offset=5, size=102400, volume='volume1'),
        ])

    def test_anon_handle_download_logs_task_not_found(self):
        self.session.getTaskInfo.return_value = None
        self.assert_system_exit(
            anon_handle_download_logs,
            self.options, self.session, [str(self.task_id)],
            stdout='',
            stderr='No such task: %s\n' % str(self.task_id),
            activate_session=None,
            exit_code=1
        )
        self.session.getBuild.assert_not_called()
        self.session.getTaskInfo.assert_called_once_with(self.task_id)
        self.session.downloadTaskOutput.assert_not_called()
        self.session.getTaskChildren.assert_not_called()

    def test_download_logs_help(self):
        self.assert_help(
            anon_handle_download_logs,
            """Usage: %s download-logs [options] <task_id> [<task_id> ...]
       %s download-logs [options] --nvr <n-v-r> [<n-v-r> ...]

Note this command only downloads task logs, not build logs.

(Specify the --help global option for a list of other help options)

Options:
  -h, --help            show this help message and exit
  -r, --recurse         Process children of this task as well
  --nvr                 Get the logs for the task associated with this build
                        Name-Version-Release.
  -m PATTERN, --match=PATTERN
                        Get only log filenames matching PATTERN (fnmatch). May
                        be used multiple times.
  -c, --continue        Continue previous download
  -d DIRECTORY, --dir=DIRECTORY
                        Write logs to DIRECTORY
""" % (self.progname, self.progname))
