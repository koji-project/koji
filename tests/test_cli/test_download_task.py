from __future__ import absolute_import
import mock
from mock import call
import os
import six
import sys

from koji_cli.commands import anon_handle_download_task
from . import utils

progname = os.path.basename(sys.argv[0]) or 'koji'


class TestDownloadTask(utils.CliTestCase):
    # Show long diffs in error output...
    maxDiff = None

    def gen_calls(self, task_output, pattern, blacklist=[], arch=None):

        params = [(k, v) for k, vl in
                  six.iteritems(task_output)
                  if k not in blacklist
                  for v in vl]
        total = len(params)
        calls = []
        for i, (k, v) in enumerate(params):
            target = k
            if v == 'DEFAULT':
                subpath = ''
            else:
                subpath = 'vol/%s/' % v
                target = '%s/%s' % (v, k)
            url = pattern % (subpath, k)
            if target.endswith('.log') and arch is not None:
                target = "%s.%s.log" % (target.rstrip(".log"), arch)
            calls.append(call(url, target, quiet=None, noprogress=None,
                size=total, num=i + 1))
        return calls

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
        self.ensure_connection = mock.patch('koji_cli.commands.ensure_connection').start()
        self.stdout = mock.patch('sys.stdout', new_callable=six.StringIO).start()
        self.stderr = mock.patch('sys.stderr', new_callable=six.StringIO).start()

    def tearDown(self):
        mock.patch.stopall()

    def test_handle_download_task_single(self):
        task_id = 123333
        args = [str(task_id)]
        self.session.getTaskInfo.return_value = {'id': task_id,
                                                 'method': 'buildArch',
                                                 'arch': 'taskarch',
                                                 'state': 2}
        self.list_task_output_all_volumes.return_value = {
            'somerpm.src.rpm': ['DEFAULT', 'vol1'],
            'somerpm.x86_64.rpm': ['DEFAULT', 'vol2'],
            'somerpm.noarch.rpm': ['vol3'],
            'somelog.log': ['DEFAULT', 'vol1']}

        calls = self.gen_calls(self.list_task_output_all_volumes.return_value,
                               'https://topurl/%swork/tasks/3333/123333/%s',
                               ['somelog.log'])

        # Run it and check immediate output
        # args: task_id
        # expected: success
        rv = anon_handle_download_task(self.options, self.session, args)

        actual = self.stdout.getvalue()
        expected = ''
        self.assertMultiLineEqual(actual, expected)
        # Finally, assert that things were called as we expected.
        self.ensure_connection.assert_called_once_with(self.session)
        self.session.getTaskInfo.assert_called_once_with(task_id)
        self.session.getTaskChildren.assert_not_called()
        self.list_task_output_all_volumes.assert_called_once_with(self.session, task_id)
        self.assertListEqual(self.download_file.mock_calls, calls)
        self.assertIsNone(rv)

    def test_handle_download_task_not_found(self):
        task_id = 123333
        args = [str(task_id)]
        self.session.getTaskInfo.return_value = None

        # Run it and check immediate output
        # args: task_id
        # expected: error
        with self.assertRaises(SystemExit) as ex:
            anon_handle_download_task(self.options, self.session, args)
        self.assertExitCode(ex, 1)
        actual = self.stdout.getvalue()
        expected = ''
        self.assertMultiLineEqual(actual, expected)
        actual = self.stderr.getvalue()
        expected = 'No such task: #123333\n'
        self.assertMultiLineEqual(actual, expected)
        # Finally, assert that things were called as we expected.
        self.ensure_connection.assert_called_once_with(self.session)
        self.session.getTaskInfo.assert_called_once_with(task_id)
        self.session.getTaskChildren.assert_not_called()

    def test_handle_download_task_parent(self):
        task_id = 123333
        args = [str(task_id), '--arch=noarch,x86_64']
        self.session.getTaskInfo.return_value = {'id': task_id,
                                                 'method': 'build',
                                                 'arch': 'taskarch',
                                                 'state': 2}
        self.session.getTaskChildren.return_value = [{'id': 22222,
                                                      'method': 'buildArch',
                                                      'arch': 'noarch',
                                                      'state': 2},
                                                     {'id': 33333,
                                                      'method': 'buildArch',
                                                      'arch': 'x86_64',
                                                      'state': 2},
                                                     {'id': 44444,
                                                      'method': 'buildArch',
                                                      'arch': 's390',
                                                      'state': 2},
                                                     {'id': 55555,
                                                      'method': 'tagBuild',
                                                      'arch': 'noarch',
                                                      'state': 2}
                                                     ]
        self.list_task_output_all_volumes.side_effect = [
            {'somerpm.src.rpm': ['DEFAULT', 'vol1']},
            {'somerpm.x86_64.rpm': ['DEFAULT', 'vol2']},
            {'somerpm.noarch.rpm': ['vol3'],
             'somelog.log': ['DEFAULT', 'vol1']}]
        # Run it and check immediate output
        # args: task_id --arch=noarch,x86_64
        # expected: success
        rv = anon_handle_download_task(self.options, self.session, args)

        actual = self.stdout.getvalue()
        expected = ''
        self.assertMultiLineEqual(actual, expected)
        # Finally, assert that things were called as we expected.
        self.ensure_connection.assert_called_once_with(self.session)
        self.session.getTaskInfo.assert_called_once_with(task_id)
        self.session.getTaskChildren.assert_called_once_with(task_id)
        self.assertEqual(self.list_task_output_all_volumes.mock_calls, [
            call(self.session, 22222),
            call(self.session, 33333),
            call(self.session, 44444)])
        self.assertListEqual(self.download_file.mock_calls, [
            call('https://topurl/work/tasks/3333/33333/somerpm.x86_64.rpm',
                 'somerpm.x86_64.rpm', quiet=None, noprogress=None, size=3, num=1),
            call('https://topurl/vol/vol2/work/tasks/3333/33333/somerpm.x86_64.rpm',
                 'vol2/somerpm.x86_64.rpm', quiet=None, noprogress=None, size=3, num=2),
            call('https://topurl/vol/vol3/work/tasks/4444/44444/somerpm.noarch.rpm',
                 'vol3/somerpm.noarch.rpm', quiet=None, noprogress=None, size=3, num=3)])
        self.assertIsNone(rv)

    def test_handle_download_task_log(self):
        task_id = 123333
        args = [str(task_id), '--log']
        self.session.getTaskInfo.return_value = {'id': task_id,
                                                 'method': 'buildArch',
                                                 'arch': 'taskarch',
                                                 'state': 2}
        self.list_task_output_all_volumes.return_value = {
            'somerpm.src.rpm': ['DEFAULT', 'vol1'],
            'somerpm.x86_64.rpm': ['DEFAULT', 'vol2'],
            'somerpm.noarch.rpm': ['vol3'],
            'somelog.log': ['DEFAULT', 'vol1']}

        calls = self.gen_calls(self.list_task_output_all_volumes.return_value,
                               'https://topurl/%swork/tasks/3333/123333/%s', arch='taskarch')

        # Run it and check immediate output
        # args: task_id --log
        # expected: success
        rv = anon_handle_download_task(self.options, self.session, args)

        actual = self.stdout.getvalue()
        expected = ''
        self.assertMultiLineEqual(actual, expected)
        # Finally, assert that things were called as we expected.
        self.ensure_connection.assert_called_once_with(self.session)
        self.session.getTaskInfo.assert_called_once_with(task_id)
        self.session.getTaskChildren.assert_not_called()
        self.list_task_output_all_volumes.assert_called_once_with(self.session, task_id)
        self.assertListEqual(self.download_file.mock_calls, calls)
        self.assertIsNone(rv)

    def test_handle_download_no_download(self):
        task_id = 123333
        args = [str(task_id), '--arch=s390,ppc']
        self.session.getTaskInfo.return_value = {'id': task_id,
                                                 'method': 'buildArch',
                                                 'arch': 'taskarch',
                                                 'state': 2}
        self.list_task_output_all_volumes.return_value = {
            'somerpm.src.rpm': ['DEFAULT', 'vol1'],
            'somerpm.x86_64.rpm': ['DEFAULT', 'vol2'],
            'somerpm.noarch.rpm': ['vol3'],
            'somelog.log': ['DEFAULT', 'vol1'],
            'somezip.zip': ['DEFAULT']
        }

        # Run it and check immediate output
        # args: task_id --arch=s390,ppc
        # expected: failure
        with self.assertRaises(SystemExit) as ex:
            anon_handle_download_task(self.options, self.session, args)
        self.assertExitCode(ex, 1)
        actual = self.stdout.getvalue()
        expected = ''
        self.assertMultiLineEqual(actual, expected)
        actual = self.stderr.getvalue()
        expected = 'No files for download found.\n'
        self.assertMultiLineEqual(actual, expected)
        # Finally, assert that things were called as we expected.
        self.ensure_connection.assert_called_once_with(self.session)
        self.session.getTaskInfo.assert_called_once_with(task_id)
        self.session.getTaskChildren.assert_not_called()
        self.list_task_output_all_volumes.assert_called_once_with(self.session, task_id)
        self.download_file.assert_not_called()

    def test_handle_download_parent_not_finished(self):
        task_id = 123333
        args = [str(task_id)]
        self.session.getTaskInfo.return_value = {'id': task_id,
                                                 'method': 'buildArch',
                                                 'arch': 'taskarch',
                                                 'state': 3}
        self.list_task_output_all_volumes.return_value = {
            'somerpm.src.rpm': ['DEFAULT', 'vol1'],
            'somerpm.x86_64.rpm': ['DEFAULT', 'vol2'],
            'somerpm.noarch.rpm': ['vol3'],
            'somelog.log': ['DEFAULT', 'vol1'],
            'somezip.zip': ['DEFAULT']
        }
        # Run it and check immediate output
        # args: task_id
        # expected: failure
        with self.assertRaises(SystemExit) as ex:
            anon_handle_download_task(self.options, self.session, args)
        self.assertExitCode(ex, 1)
        actual = self.stdout.getvalue()
        expected = ''
        self.assertMultiLineEqual(actual, expected)
        actual = self.stderr.getvalue()
        expected = 'Task 123333 has not finished yet.\n'
        self.assertMultiLineEqual(actual, expected)
        # Finally, assert that things were called as we expected.
        self.ensure_connection.assert_called_once_with(self.session)
        self.session.getTaskInfo.assert_called_once_with(task_id)
        self.session.getTaskChildren.assert_not_called()
        self.list_task_output_all_volumes.assert_called_once_with(self.session, task_id)
        self.download_file.assert_not_called()

    def test_handle_download_child_not_finished(self):
        task_id = 123333
        args = [str(task_id)]
        self.session.getTaskInfo.return_value = {'id': task_id,
                                                 'method': 'build',
                                                 'arch': 'taskarch',
                                                 'state': 2}
        self.session.getTaskChildren.return_value = [{'id': 22222,
                                                      'method': 'buildArch',
                                                      'arch': 'noarch',
                                                      'state': 3}]
        self.list_task_output_all_volumes.return_value = {'somerpm.src.rpm': ['DEFAULT', 'vol1']}
        # Run it and check immediate output
        # args: task_id
        # expected: failure
        with self.assertRaises(SystemExit) as ex:
            anon_handle_download_task(self.options, self.session, args)
        self.assertExitCode(ex, 1)
        actual = self.stdout.getvalue()
        expected = ''
        self.assertMultiLineEqual(actual, expected)
        actual = self.stderr.getvalue()
        expected = 'Child task 22222 has not finished yet.\n'
        self.assertMultiLineEqual(actual, expected)
        # Finally, assert that things were called as we expected.
        self.ensure_connection.assert_called_once_with(self.session)
        self.session.getTaskInfo.assert_called_once_with(task_id)
        self.session.getTaskChildren.assert_called_once_with(task_id)
        self.list_task_output_all_volumes.assert_called_once_with(self.session, 22222)
        self.download_file.assert_not_called()

    def test_handle_download_invalid_file_name(self):
        task_id = 123333
        args = [str(task_id)]
        self.session.getTaskInfo.return_value = {'id': task_id,
                                                 'method': 'buildArch',
                                                 'arch': 'taskarch',
                                                 'state': 2}
        self.list_task_output_all_volumes.return_value = {'somerpm..src.rpm': ['DEFAULT', 'vol1']}
        # Run it and check immediate output
        # args: task_id
        # expected: failure
        with self.assertRaises(SystemExit) as ex:
            anon_handle_download_task(self.options, self.session, args)
        self.assertExitCode(ex, 1)
        actual = self.stdout.getvalue()
        expected = ''
        self.assertMultiLineEqual(actual, expected)
        actual = self.stderr.getvalue()
        expected = 'Invalid file name: somerpm..src.rpm\n'
        self.assertMultiLineEqual(actual, expected)
        # Finally, assert that things were called as we expected.
        self.ensure_connection.assert_called_once_with(self.session)
        self.session.getTaskInfo.assert_called_once_with(task_id)
        self.session.getTaskChildren.assert_not_called()
        self.list_task_output_all_volumes.assert_called_once_with(self.session, task_id)
        self.download_file.assert_not_called()

    def test_handle_download_help(self):
        args = ['--help']
        # Run it and check immediate output
        # args: --help
        # expected: failure
        with self.assertRaises(SystemExit) as ex:
            anon_handle_download_task(self.options, self.session, args)
        self.assertExitCode(ex, 0)
        actual = self.stdout.getvalue()
        expected = """Usage: %s download-task <task_id>
(Specify the --help global option for a list of other help options)

Options:
  -h, --help    show this help message and exit
  --arch=ARCH   Only download packages for this arch (may be used multiple
                times)
  --logs        Also download build logs
  --topurl=URL  URL under which Koji files are accessible
  --noprogress  Do not display progress meter
  --wait        Wait for running tasks to finish
  -q, --quiet   Suppress output
""" % progname
        self.assertMultiLineEqual(actual, expected)
        actual = self.stderr.getvalue()
        expected = ''
        self.assertEqual(actual, expected)

    def test_handle_download_no_task_id(self):
        args = []
        # Run it and check immediate output
        # no args
        # expected: failure
        with self.assertRaises(SystemExit) as ex:
            anon_handle_download_task(self.options, self.session, args)
        self.assertExitCode(ex, 2)
        actual = self.stdout.getvalue()
        expected = ''
        self.assertMultiLineEqual(actual, expected)
        actual = self.stderr.getvalue()
        expected = """Usage: %s download-task <task_id>
(Specify the --help global option for a list of other help options)

%s: error: Please specify a task ID
""" % (progname, progname)
        self.assertEqual(actual, expected)

    def test_handle_download_multi_task_id(self):
        args = ["123", "456"]
        # Run it and check immediate output
        # args: 123 456
        # expected: failure
        with self.assertRaises(SystemExit) as ex:
            anon_handle_download_task(self.options, self.session, args)
        self.assertExitCode(ex, 2)
        actual = self.stdout.getvalue()
        expected = ''
        self.assertMultiLineEqual(actual, expected)
        actual = self.stderr.getvalue()
        expected = """Usage: %s download-task <task_id>
(Specify the --help global option for a list of other help options)

%s: error: Only one task ID may be specified
""" % (progname, progname)
        self.assertEqual(actual, expected)
