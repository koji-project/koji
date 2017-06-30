from __future__ import absolute_import
import mock
from mock import call
import os
import six
import sys
import unittest

from koji_cli.commands import anon_handle_download_task

progname = os.path.basename(sys.argv[0]) or 'koji'


class TestDownloadTask(unittest.TestCase):
    # Show long diffs in error output...
    maxDiff = None

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
        # Run it and check immediate output
        # args: task_id
        # expected: success
        rv = anon_handle_download_task(self.options, self.session, args)

        actual = self.stdout.getvalue()
        expected = ''
        self.assertMultiLineEqual(actual, expected)
        # Finally, assert that things were called as we expected.
        self.activate_session.assert_called_once_with(self.session, self.options)
        self.session.getTaskInfo.assert_called_once_with(task_id)
        self.session.getTaskChildren.assert_not_called()
        self.list_task_output_all_volumes.assert_called_once_with(self.session, task_id)
        self.assertEqual(self.download_file.mock_calls, [
            call('https://topurl/work/tasks/3333/123333/somerpm.src.rpm',
                 'somerpm.src.rpm', None, None, 5, 1),
            call('https://topurl/vol/vol1/work/tasks/3333/123333/somerpm.src.rpm',
                 'vol1/somerpm.src.rpm', None, None, 5, 2),
            call('https://topurl/work/tasks/3333/123333/somerpm.x86_64.rpm',
                 'somerpm.x86_64.rpm', None, None, 5, 3),
            call('https://topurl/vol/vol2/work/tasks/3333/123333/somerpm.x86_64.rpm',
                 'vol2/somerpm.x86_64.rpm', None, None, 5, 4),
            call('https://topurl/vol/vol3/work/tasks/3333/123333/somerpm.noarch.rpm',
                 'vol3/somerpm.noarch.rpm', None, None, 5, 5)])
        self.assertIsNone(rv)

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
        self.activate_session.assert_called_once_with(self.session, self.options)
        self.session.getTaskInfo.assert_called_once_with(task_id)
        self.session.getTaskChildren.assert_called_once_with(task_id)
        self.assertEqual(self.list_task_output_all_volumes.mock_calls, [
            call(self.session, 22222),
            call(self.session, 33333),
            call(self.session, 44444)])
        self.assertEqual(self.download_file.mock_calls, [
            call('https://topurl/work/tasks/3333/33333/somerpm.x86_64.rpm',
                 'somerpm.x86_64.rpm', None, None, 3, 1),
            call('https://topurl/vol/vol2/work/tasks/3333/33333/somerpm.x86_64.rpm',
                 'vol2/somerpm.x86_64.rpm', None, None, 3, 2),
            call('https://topurl/vol/vol3/work/tasks/4444/44444/somerpm.noarch.rpm',
                 'vol3/somerpm.noarch.rpm', None, None, 3, 3)])
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
        # Run it and check immediate output
        # args: task_id --log
        # expected: success
        rv = anon_handle_download_task(self.options, self.session, args)

        actual = self.stdout.getvalue()
        expected = ''
        self.assertMultiLineEqual(actual, expected)
        # Finally, assert that things were called as we expected.
        self.activate_session.assert_called_once_with(self.session, self.options)
        self.session.getTaskInfo.assert_called_once_with(task_id)
        self.session.getTaskChildren.assert_not_called()
        self.list_task_output_all_volumes.assert_called_once_with(self.session, task_id)
        self.assertEqual(self.download_file.mock_calls, [
            call('https://topurl/work/tasks/3333/123333/somerpm.src.rpm',
                 'somerpm.src.rpm', None, None, 7, 1),
            call('https://topurl/vol/vol1/work/tasks/3333/123333/somerpm.src.rpm',
                 'vol1/somerpm.src.rpm', None, None, 7, 2),
            call('https://topurl/work/tasks/3333/123333/somerpm.x86_64.rpm',
                 'somerpm.x86_64.rpm', None, None, 7, 3),
            call('https://topurl/vol/vol2/work/tasks/3333/123333/somerpm.x86_64.rpm',
                 'vol2/somerpm.x86_64.rpm', None, None, 7, 4),
            call('https://topurl/vol/vol3/work/tasks/3333/123333/somerpm.noarch.rpm',
                 'vol3/somerpm.noarch.rpm', None, None, 7, 5),
            call('https://topurl/work/tasks/3333/123333/somelog.log',
                 'some.taskarch.log', None, None, 7, 6),
            call('https://topurl/vol/vol1/work/tasks/3333/123333/somelog.log',
                 'vol1/some.taskarch.log', None, None, 7, 7)])
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
        with self.assertRaises(SystemExit) as cm:
            anon_handle_download_task(self.options, self.session, args)
        actual = self.stdout.getvalue()
        expected = ''
        self.assertMultiLineEqual(actual, expected)
        actual = self.stderr.getvalue()
        expected = 'No files for download found.\n'
        self.assertMultiLineEqual(actual, expected)
        # Finally, assert that things were called as we expected.
        self.activate_session.assert_called_once_with(self.session, self.options)
        self.session.getTaskInfo.assert_called_once_with(task_id)
        self.session.getTaskChildren.assert_not_called()
        self.list_task_output_all_volumes.assert_called_once_with(self.session, task_id)
        self.download_file.assert_not_called()
        self.assertEqual(cm.exception.code, 1)

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
        with self.assertRaises(SystemExit) as cm:
            anon_handle_download_task(self.options, self.session, args)
        actual = self.stdout.getvalue()
        expected = ''
        self.assertMultiLineEqual(actual, expected)
        actual = self.stderr.getvalue()
        expected = 'Task 123333 has not finished yet.\n'
        self.assertMultiLineEqual(actual, expected)
        # Finally, assert that things were called as we expected.
        self.activate_session.assert_called_once_with(self.session, self.options)
        self.session.getTaskInfo.assert_called_once_with(task_id)
        self.session.getTaskChildren.assert_not_called()
        self.list_task_output_all_volumes.assert_called_once_with(self.session, task_id)
        self.download_file.assert_not_called()
        self.assertEqual(cm.exception.code, 1)

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
        with self.assertRaises(SystemExit) as cm:
            anon_handle_download_task(self.options, self.session, args)
        actual = self.stdout.getvalue()
        expected = ''
        self.assertMultiLineEqual(actual, expected)
        actual = self.stderr.getvalue()
        expected = 'Child task 22222 has not finished yet.\n'
        self.assertMultiLineEqual(actual, expected)
        # Finally, assert that things were called as we expected.
        self.activate_session.assert_called_once_with(self.session, self.options)
        self.session.getTaskInfo.assert_called_once_with(task_id)
        self.session.getTaskChildren.assert_called_once_with(task_id)
        self.list_task_output_all_volumes.assert_called_once_with(self.session, 22222)
        self.download_file.assert_not_called()
        self.assertEqual(cm.exception.code, 1)

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
        with self.assertRaises(SystemExit) as cm:
            anon_handle_download_task(self.options, self.session, args)
        actual = self.stdout.getvalue()
        expected = ''
        self.assertMultiLineEqual(actual, expected)
        actual = self.stderr.getvalue()
        expected = 'Invalid file name: somerpm..src.rpm\n'
        self.assertMultiLineEqual(actual, expected)
        # Finally, assert that things were called as we expected.
        self.activate_session.assert_called_once_with(self.session, self.options)
        self.session.getTaskInfo.assert_called_once_with(task_id)
        self.session.getTaskChildren.assert_not_called()
        self.list_task_output_all_volumes.assert_called_once_with(self.session, task_id)
        self.download_file.assert_not_called()
        self.assertEqual(cm.exception.code, 1)

    def test_handle_download_help(self):
        args = ['--help']
        # Run it and check immediate output
        # args: --help
        # expected: failure
        with self.assertRaises(SystemExit) as cm:
            anon_handle_download_task(self.options, self.session, args)
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
  -q, --quiet   Suppress output
""" % progname
        self.assertMultiLineEqual(actual, expected)
        actual = self.stderr.getvalue()
        expected = ''
        self.assertEqual(actual, expected)
        self.assertEqual(cm.exception.code, 0)

    def test_handle_download_no_task_id(self):
        args = []
        # Run it and check immediate output
        # no args
        # expected: failure
        with self.assertRaises(SystemExit) as cm:
            anon_handle_download_task(self.options, self.session, args)
        actual = self.stdout.getvalue()
        expected = ''
        self.assertMultiLineEqual(actual, expected)
        actual = self.stderr.getvalue()
        expected = """Usage: %s download-task <task_id>
(Specify the --help global option for a list of other help options)

%s: error: Please specify a task ID
""" % (progname, progname)
        self.assertEqual(actual, expected)
        self.assertEqual(cm.exception.code, 2)

    def test_handle_download_multi_task_id(self):
        args = ["123", "456"]
        # Run it and check immediate output
        # args: 123 456
        # expected: failure
        with self.assertRaises(SystemExit) as cm:
            anon_handle_download_task(self.options, self.session, args)
        actual = self.stdout.getvalue()
        expected = ''
        self.assertMultiLineEqual(actual, expected)
        actual = self.stderr.getvalue()
        expected = """Usage: %s download-task <task_id>
(Specify the --help global option for a list of other help options)

%s: error: Only one task ID may be specified
""" % (progname, progname)
        self.assertEqual(actual, expected)
        self.assertEqual(cm.exception.code, 2)


if __name__ == '__main__':
    unittest.main()
