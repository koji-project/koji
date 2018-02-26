from __future__ import absolute_import
import mock
from mock import call
import six

from . import utils
from koji_cli.commands import anon_handle_download_logs

class TestDownloadLogs(utils.CliTestCase):
    def mock_builtin_open(self, filepath, *args):
        if filepath in self.custom_open:
            return self.custom_open[filepath]
        return self.builtin_open(filepath, *args)

    def setUp(self):
        # Mock out the options parsed in main
        self.options = mock.MagicMock()
        self.options.quiet = None
        self.options.topurl = 'https://topurl'
        # Mock out the xmlrpc server
        self.session = mock.MagicMock()
        self.list_task_output_all_volumes = mock.patch('koji_cli.commands.list_task_output_all_volumes').start()
        self.ensuredir = mock.patch('koji.ensuredir').start()
        self.download_file = mock.patch('koji_cli.commands.download_file').start()
        self.activate_session = mock.patch('koji_cli.commands.activate_session').start()
        self.stdout = mock.patch('sys.stdout', new_callable=six.StringIO).start()
        self.stderr = mock.patch('sys.stderr', new_callable=six.StringIO).start()

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
        with self.assertRaises(SystemExit):
            anon_handle_download_logs(self.options, self.session, ['bogus_task_id'])

    def test_anon_handle_download_logs_no_arg(self):
        with self.assertRaises(SystemExit):
            anon_handle_download_logs(self.options, self.session, [])

    def test_anon_handle_download_logs_wrong_nvr(self):
        nvr = 'bash-1.2.3-f26'
        self.session.getBuild.return_value = None

        with self.assertRaises(SystemExit):
            anon_handle_download_logs(self.options, self.session, ['--nvr', nvr])

        self.session.getBuild.assert_called_once_with(nvr)

    def test_anon_handle_download_logs_nvr(self):
        nvr = 'bash-1.2.3-f26'
        task_id = 123456
        self.session.getBuild.return_value = {'task_id': task_id}
        self.session.getTaskInfo.return_value = {
            'arch': 'x86_64',
            'state': 'CLOSED',
        }
        self.list_task_output_all_volumes.return_value = {}
        self.session.getTaskChildren.side_effect = [[{'id': 23}], []]

        anon_handle_download_logs(self.options, self.session, ['--nvr', nvr])

        self.session.getBuild.assert_called_once_with(nvr)
        self.session.getTaskInfo.assert_has_calls([
            mock.call(task_id),
            mock.call(23),
        ])
        self.session.downloadTaskOutput.assert_not_called()

    def test_anon_handle_download_logs(self):
        task_id = 123456
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
            anon_handle_download_logs(self.options, self.session, [str(task_id)])

        self.session.getTaskInfo.assert_called_once_with(task_id)
        self.list_task_output_all_volumes.assert_called_once_with(self.session, task_id)
        self.assertTrue(out_file.closed)
        self.assertEqual(self.session.downloadTaskOutput.call_count, 2)
        self.session.downloadTaskOutput.assert_has_calls([
            mock.call(123456, 'file1.log', offset=0, size=102400, volume='volume1'),
            mock.call(123456, 'file1.log', offset=5, size=102400, volume='volume1'),
        ])

