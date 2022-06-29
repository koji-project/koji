from __future__ import absolute_import

import os
import sys

import mock
import six
from mock import call

from koji_cli.commands import anon_handle_download_task
from . import utils

progname = os.path.basename(sys.argv[0]) or 'koji'


class TestDownloadTask(utils.CliTestCase):

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
        # Show long diffs in error output...
        self.maxDiff = None
        # Mock out the options parsed in main
        self.options = mock.MagicMock()
        self.options.quiet = None
        self.options.topurl = 'https://topurl'
        # Mock out the xmlrpc server
        self.session = mock.MagicMock()
        self.list_task_output_all_volumes = mock.patch(
            'koji_cli.commands.list_task_output_all_volumes').start()
        self.ensuredir = mock.patch('koji.ensuredir').start()
        self.download_file = mock.patch('koji_cli.commands.download_file').start()
        self.ensure_connection = mock.patch('koji_cli.commands.ensure_connection').start()
        self.stdout = mock.patch('sys.stdout', new_callable=six.StringIO).start()
        self.stderr = mock.patch('sys.stderr', new_callable=six.StringIO).start()
        self.parent_task_id = 123333
        self.parent_task_info = {'id': self.parent_task_id, 'method': 'buildArch',
                                 'arch': 'taskarch', 'state': 2, 'parent': None}
        self.error_format = """Usage: %s download-task <task_id>
Default behavior without --all option downloads .rpm files only for build and buildArch tasks.

(Specify the --help global option for a list of other help options)

%s: error: {message}
""" % (self.progname, self.progname)

    def tearDown(self):
        mock.patch.stopall()

    def test_handle_download_task_single(self):
        args = [str(self.parent_task_id)]
        self.session.getTaskInfo.return_value = self.parent_task_info
        self.session.getTaskChildren.return_value = []
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
        self.ensure_connection.assert_called_once_with(self.session, self.options)
        self.session.getTaskInfo.assert_called_once_with(self.parent_task_id)
        self.session.getTaskChildren.assert_called_once_with(self.parent_task_id)
        self.list_task_output_all_volumes.assert_called_once_with(self.session,
                                                                  self.parent_task_id)
        self.assertListEqual(self.download_file.mock_calls, calls)
        self.assertIsNone(rv)

    def test_handle_download_task_not_found(self):
        args = [str(self.parent_task_id)]
        self.session.getTaskInfo.return_value = None

        # Run it and check immediate output
        # args: task_id
        # expected: error
        self.assert_system_exit(
            anon_handle_download_task,
            self.options, self.session, args,
            stderr='No such task: %s\n' % self.parent_task_id,
            stdout='',
            activate_session=None,
            exit_code=1)
        # Finally, assert that things were called as we expected.
        self.ensure_connection.assert_called_once_with(self.session, self.options)
        self.session.getTaskInfo.assert_called_once_with(self.parent_task_id)
        self.session.getTaskChildren.assert_not_called()

    def test_handle_download_task_parent(self):
        args = [str(self.parent_task_id), '--arch=noarch,x86_64']
        self.session.getTaskInfo.return_value = self.parent_task_info
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
             'somelog.log': ['DEFAULT', 'vol1']},
        ]
        # Run it and check immediate output
        # args: task_id --arch=noarch,x86_64
        # expected: success
        rv = anon_handle_download_task(self.options, self.session, args)

        actual = self.stdout.getvalue()
        expected = ''
        self.assertMultiLineEqual(actual, expected)
        # Finally, assert that things were called as we expected.
        self.ensure_connection.assert_called_once_with(self.session, self.options)
        self.session.getTaskInfo.assert_called_once_with(self.parent_task_id)
        self.session.getTaskChildren.assert_called_once_with(self.parent_task_id)
        self.assertEqual(self.list_task_output_all_volumes.mock_calls, [
            call(self.session, 22222),
            call(self.session, 33333),
            call(self.session, 55555)])
        self.assertListEqual(self.download_file.mock_calls, [
            call('https://topurl/work/tasks/3333/33333/somerpm.x86_64.rpm',
                 'somerpm.x86_64.rpm', quiet=None, noprogress=None, size=2, num=1),
            call('https://topurl/vol/vol2/work/tasks/3333/33333/somerpm.x86_64.rpm',
                 'vol2/somerpm.x86_64.rpm', quiet=None, noprogress=None, size=2, num=2)])
        self.assertIsNone(rv)

    def test_handle_download_task_log(self):
        args = [str(self.parent_task_id), '--log']
        self.session.getTaskInfo.return_value = self.parent_task_info
        self.session.getTaskChildren.return_value = [{'id': 22222,
                                                      'method': 'buildArch',
                                                      'arch': 'noarch',
                                                      'state': 2}]
        self.list_task_output_all_volumes.side_effect = [{}, {
            'somerpm.src.rpm': ['DEFAULT', 'vol1'],
            'somerpm.x86_64.rpm': ['DEFAULT', 'vol2'],
            'somerpm.noarch.rpm': ['vol3'],
            'somelog.log': ['DEFAULT', 'vol1']}]

        # Run it and check immediate output
        # args: task_id --log
        # expected: success
        rv = anon_handle_download_task(self.options, self.session, args)

        actual = self.stdout.getvalue()
        expected = ''
        self.assertMultiLineEqual(actual, expected)
        # Finally, assert that things were called as we expected.
        self.ensure_connection.assert_called_once_with(self.session, self.options)
        self.session.getTaskInfo.assert_called_once_with(self.parent_task_id)
        self.session.getTaskChildren.assert_called_once_with(self.parent_task_id)
        self.list_task_output_all_volumes.assert_has_calls([
            mock.call(self.session, self.parent_task_id), mock.call(self.session, 22222)])
        self.assertListEqual(self.download_file.mock_calls, [
            call('https://topurl/work/tasks/2222/22222/somerpm.src.rpm',
                 'somerpm.src.rpm', quiet=None, noprogress=None, size=7, num=1),
            call('https://topurl/vol/vol1/work/tasks/2222/22222/somerpm.src.rpm',
                 'vol1/somerpm.src.rpm', quiet=None, noprogress=None, size=7, num=2),
            call('https://topurl/work/tasks/2222/22222/somerpm.x86_64.rpm',
                 'somerpm.x86_64.rpm', quiet=None, noprogress=None, size=7, num=3),
            call('https://topurl/vol/vol2/work/tasks/2222/22222/somerpm.x86_64.rpm',
                 'vol2/somerpm.x86_64.rpm', quiet=None, noprogress=None, size=7, num=4),
            call('https://topurl/vol/vol3/work/tasks/2222/22222/somerpm.noarch.rpm',
                 'vol3/somerpm.noarch.rpm', quiet=None, noprogress=None, size=7, num=5),
            call('https://topurl/work/tasks/2222/22222/somelog.log',
                 'somelog.noarch.log', quiet=None, noprogress=None, size=7, num=6),
            call('https://topurl/vol/vol1/work/tasks/2222/22222/somelog.log',
                 'vol1/somelog.noarch.log', quiet=None, noprogress=None, size=7, num=7)
        ])
        self.assertIsNone(rv)

    def test_handle_download_no_download(self):
        args = [str(self.parent_task_id), '--arch=s390,ppc']
        self.session.getTaskInfo.return_value = self.parent_task_info

        # Run it and check immediate output
        # args: task_id --arch=s390,ppc
        # expected: pass
        anon_handle_download_task(self.options, self.session, args)
        actual = self.stdout.getvalue()
        expected = 'No files for download found.\n'
        self.assertMultiLineEqual(actual, expected)
        actual = self.stderr.getvalue()
        expected = ''
        self.assertMultiLineEqual(actual, expected)
        # Finally, assert that things were called as we expected.
        self.ensure_connection.assert_called_once_with(self.session, self.options)
        self.session.getTaskInfo.assert_called_once_with(self.parent_task_id)
        self.session.getTaskChildren.assert_called_once_with(self.parent_task_id)
        self.list_task_output_all_volumes.assert_not_called()
        self.download_file.assert_not_called()

    def test_handle_download_parent_not_finished(self):
        args = [str(self.parent_task_id)]
        self.session.getTaskInfo.return_value = {'id': self.parent_task_id,
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
        self.assert_system_exit(
            anon_handle_download_task,
            self.options, self.session, args,
            stderr="Task 123333 has not finished yet.\n",
            stdout='',
            activate_session=None,
            exit_code=1)
        # Finally, assert that things were called as we expected.
        self.ensure_connection.assert_called_once_with(self.session, self.options)
        self.session.getTaskInfo.assert_called_once_with(self.parent_task_id)
        self.session.getTaskChildren.assert_called_once_with(self.parent_task_id)
        self.list_task_output_all_volumes.assert_not_called()
        self.download_file.assert_not_called()

    def test_handle_download_child_not_finished(self):
        args = [str(self.parent_task_id)]
        self.session.getTaskInfo.return_value = self.parent_task_info
        self.session.getTaskChildren.return_value = [{'id': 22222,
                                                      'method': 'buildArch',
                                                      'arch': 'noarch',
                                                      'state': 3}]
        self.list_task_output_all_volumes.side_effect = [
            {'somerpm.src.rpm': ['DEFAULT', 'vol1']},
            {'somenextrpm.src.rpm': ['DEFAULT', 'vol1']}]
        # Run it and check immediate output
        # args: task_id
        # expected: failure
        self.assert_system_exit(
            anon_handle_download_task,
            self.options, self.session, args,
            stderr="Child task 22222 has not finished yet.\n",
            stdout='',
            activate_session=None,
            exit_code=1)
        # Finally, assert that things were called as we expected.
        self.ensure_connection.assert_called_once_with(self.session, self.options)
        self.session.getTaskInfo.assert_called_once_with(self.parent_task_id)
        self.session.getTaskChildren.assert_called_once_with(self.parent_task_id)
        self.list_task_output_all_volumes.assert_not_called()
        self.download_file.assert_not_called()

    def test_handle_download_invalid_file_name(self):
        args = [str(self.parent_task_id)]
        self.session.getTaskInfo.return_value = self.parent_task_info
        self.list_task_output_all_volumes.return_value = {'somerpm..src.rpm': ['DEFAULT', 'vol1']}
        # Run it and check immediate output
        # args: task_id
        # expected: failure
        self.assert_system_exit(
            anon_handle_download_task,
            self.options, self.session, args,
            stderr="Invalid file name: somerpm..src.rpm\n",
            stdout='',
            activate_session=None,
            exit_code=1)
        # Finally, assert that things were called as we expected.
        self.ensure_connection.assert_called_once_with(self.session, self.options)
        self.session.getTaskInfo.assert_called_once_with(self.parent_task_id)
        self.session.getTaskChildren.assert_called_once_with(self.parent_task_id)
        self.list_task_output_all_volumes.assert_called_once_with(self.session,
                                                                  self.parent_task_id)
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
Default behavior without --all option downloads .rpm files only for build and buildArch tasks.

(Specify the --help global option for a list of other help options)

Options:
  -h, --help    show this help message and exit
  --arch=ARCH   Only download packages for this arch (may be used multiple
                times), only for build and buildArch task methods
  --logs        Also download build logs
  --topurl=URL  URL under which Koji files are accessible
  --noprogress  Do not display progress meter
  --wait        Wait for running tasks to finish, even if running in the
                background
  --nowait      Do not wait for running tasks to finish
  -q, --quiet   Suppress output
  --all         Download all files, all methods instead of build and buildArch
  --dirpertask  Download files to dir per task
  --parentonly  Download parent's files only
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
        self.assert_system_exit(
            anon_handle_download_task,
            self.options, self.session, args,
            stderr=self.format_error_message("Please specify a task ID"),
            stdout='',
            activate_session=None,
            exit_code=2)

    def test_handle_download_multi_task_id(self):
        args = ["123", "456"]
        # Run it and check immediate output
        # args: 123 456
        # expected: failure
        self.assert_system_exit(
            anon_handle_download_task,
            self.options, self.session, args,
            stderr=self.format_error_message("Only one task ID may be specified"),
            stdout='',
            activate_session=None,
            exit_code=2)

    def test_handle_download_task_parent_dirpertask(self):
        args = [str(self.parent_task_id), '--arch=noarch,x86_64', '--dirpertask', '--log']
        self.session.getTaskInfo.return_value = self.parent_task_info
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
            {'somerpm.src.rpm': ['DEFAULT', 'vol1'], 'somerpm.noarch.rpm': ['DEFAULT']},
            {'somerpm.x86_64.rpm': ['DEFAULT', 'vol2']},
            {'somerpm.noarch.rpm': ['vol3'],
             'somelog.log': ['DEFAULT', 'vol1']},
        ]
        # Run it and check immediate output
        # args: task_id --arch=noarch,x86_64 --dirpertask --log
        # expected: success
        rv = anon_handle_download_task(self.options, self.session, args)

        actual = self.stdout.getvalue()
        expected = ''
        self.assertMultiLineEqual(actual, expected)
        # Finally, assert that things were called as we expected.
        self.ensure_connection.assert_called_once_with(self.session, self.options)
        self.session.getTaskInfo.assert_called_once_with(self.parent_task_id)
        self.session.getTaskChildren.assert_called_once_with(self.parent_task_id)
        self.assertEqual(self.list_task_output_all_volumes.mock_calls, [
            call(self.session, 22222),
            call(self.session, 33333),
            call(self.session, 55555)])
        self.assertListEqual(self.download_file.mock_calls, [
            call('https://topurl/work/tasks/2222/22222/somerpm.noarch.rpm',
                 '22222/somerpm.noarch.rpm', quiet=None, noprogress=None, size=5, num=1),
            call('https://topurl/work/tasks/3333/33333/somerpm.x86_64.rpm',
                 '33333/somerpm.x86_64.rpm', quiet=None, noprogress=None, size=5, num=2),
            call('https://topurl/vol/vol2/work/tasks/3333/33333/somerpm.x86_64.rpm',
                 '33333/vol2/somerpm.x86_64.rpm', quiet=None, noprogress=None, size=5, num=3),
            call('https://topurl/work/tasks/5555/55555/somelog.log',
                 '55555/somelog.log', quiet=None, noprogress=None, size=5, num=4),
            call('https://topurl/vol/vol1/work/tasks/5555/55555/somelog.log',
                 '55555/vol1/somelog.log', quiet=None, noprogress=None, size=5, num=5),
        ])
        self.assertIsNone(rv)

    def test_handle_download_task_parent_all(self):
        args = [str(self.parent_task_id), '--arch=noarch,x86_64', '--all']
        self.session.getTaskInfo.return_value = self.parent_task_info
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
            {'somerpm.json': ['DEFAULT', 'vol2']},
            {'somerpm.noarch.rpm': ['vol3'],
             'somelog.log': ['DEFAULT', 'vol1']},
        ]
        # Run it and check immediate output
        # args: task_id --arch=noarch,x86_64 --all
        # expected: success
        rv = anon_handle_download_task(self.options, self.session, args)

        actual = self.stdout.getvalue()
        expected = ''
        self.assertMultiLineEqual(actual, expected)
        # Finally, assert that things were called as we expected.
        self.ensure_connection.assert_called_once_with(self.session, self.options)
        self.session.getTaskInfo.assert_called_once_with(self.parent_task_id)
        self.session.getTaskChildren.assert_called_once_with(self.parent_task_id)
        self.assertEqual(self.list_task_output_all_volumes.mock_calls, [
            call(self.session, 22222),
            call(self.session, 33333),
            call(self.session, 55555)])
        self.assertListEqual(self.download_file.mock_calls, [
            call('https://topurl/work/tasks/3333/33333/somerpm.json',
                 'somerpm.x86_64.json', quiet=None, noprogress=None, size=3, num=1),
            call('https://topurl/vol/vol2/work/tasks/3333/33333/somerpm.json',
                 'vol2/somerpm.x86_64.json', quiet=None, noprogress=None, size=3, num=2),
            call('https://topurl/vol/vol3/work/tasks/5555/55555/somerpm.noarch.rpm',
                 'vol3/somerpm.noarch.rpm', quiet=None, noprogress=None, size=3, num=3),
        ])
        self.assertIsNone(rv)

    def test_handle_download_task_parent_only(self):
        args = [str(self.parent_task_id), '--parentonly']
        self.session.getTaskInfo.return_value = self.parent_task_info
        self.list_task_output_all_volumes.return_value = {}
        # Run it and check immediate output
        # args: task_id --parentonly
        # expected: pass
        anon_handle_download_task(self.options, self.session, args)
        actual = self.stdout.getvalue()
        expected = 'No files for download found.\n'
        self.assertMultiLineEqual(actual, expected)
        actual = self.stderr.getvalue()
        expected = ''
        self.assertMultiLineEqual(actual, expected)
        # Finally, assert that things were called as we expected.
        self.ensure_connection.assert_called_once_with(self.session, self.options)
        self.session.getTaskInfo.assert_called_once_with(self.parent_task_id)
        self.session.getTaskChildren.assert_not_called()
        self.list_task_output_all_volumes.assert_called_once_with(self.session,
                                                                  self.parent_task_id)
        self.download_file.assert_not_called()

    def test_handle_download_task_parent_dirpertask_all(self):
        args = [str(self.parent_task_id), '--dirpertask', '--all']
        self.session.getTaskInfo.return_value = self.parent_task_info
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
            {},
            {'somerpm.src.rpm': ['DEFAULT', 'vol1'], 'somerpm.noarch.rpm': ['DEFAULT']},
            {'somerpm.x86_64.rpm': ['DEFAULT', 'vol2']},
            {'somerpm.s390.rpm': ['vol2']},
            {'somerpm.noarch.rpm': ['vol3'],
             'somelog.log': ['DEFAULT', 'vol1']},
        ]
        # Run it and check immediate output
        # args: task_id --dirpertask --log
        # expected: success
        rv = anon_handle_download_task(self.options, self.session, args)

        actual = self.stdout.getvalue()
        expected = ''
        self.assertMultiLineEqual(actual, expected)
        # Finally, assert that things were called as we expected.
        self.ensure_connection.assert_called_once_with(self.session, self.options)
        self.session.getTaskInfo.assert_called_once_with(self.parent_task_id)
        self.session.getTaskChildren.assert_called_once_with(self.parent_task_id)
        self.assertEqual(self.list_task_output_all_volumes.mock_calls, [
            call(self.session, self.parent_task_id),
            call(self.session, 22222),
            call(self.session, 33333),
            call(self.session, 44444),
            call(self.session, 55555)])
        self.assertListEqual(self.download_file.mock_calls, [
            call('https://topurl/work/tasks/2222/22222/somerpm.src.rpm',
                 '22222/somerpm.src.rpm', quiet=None, noprogress=None, size=7, num=1),
            call('https://topurl/vol/vol1/work/tasks/2222/22222/somerpm.src.rpm',
                 '22222/vol1/somerpm.src.rpm', quiet=None, noprogress=None, size=7, num=2),
            call('https://topurl/work/tasks/2222/22222/somerpm.noarch.rpm',
                 '22222/somerpm.noarch.rpm', quiet=None, noprogress=None, size=7, num=3),
            call('https://topurl/work/tasks/3333/33333/somerpm.x86_64.rpm',
                 '33333/somerpm.x86_64.rpm', quiet=None, noprogress=None, size=7, num=4),
            call('https://topurl/vol/vol2/work/tasks/3333/33333/somerpm.x86_64.rpm',
                 '33333/vol2/somerpm.x86_64.rpm', quiet=None, noprogress=None, size=7, num=5),
            call('https://topurl/vol/vol2/work/tasks/4444/44444/somerpm.s390.rpm',
                 '44444/vol2/somerpm.s390.rpm', quiet=None, noprogress=None, size=7, num=6),
            call('https://topurl/vol/vol3/work/tasks/5555/55555/somerpm.noarch.rpm',
                 '55555/vol3/somerpm.noarch.rpm', quiet=None, noprogress=None, size=7, num=7),
        ])
        self.assertIsNone(rv)

    def test_handle_download_task_log_with_arch(self):
        args = [str(self.parent_task_id), '--arch=noarch', '--log']
        self.session.getTaskInfo.return_value = self.parent_task_info
        self.session.getTaskChildren.return_value = [{'id': 22222,
                                                      'method': 'buildArch',
                                                      'arch': 'noarch',
                                                      'state': 2}]
        self.list_task_output_all_volumes.side_effect = [{
            'somerpm.src.rpm': ['DEFAULT', 'vol1'],
            'somerpm.x86_64.rpm': ['DEFAULT', 'vol2'],
            'somerpm.noarch.rpm': ['vol3'],
            'somelog.noarch.log': ['DEFAULT', 'vol1']}]

        # Run it and check immediate output
        # args: task_id --log --arch=noarch
        # expected: success
        rv = anon_handle_download_task(self.options, self.session, args)

        actual = self.stdout.getvalue()
        expected = ''
        self.assertMultiLineEqual(actual, expected)
        # Finally, assert that things were called as we expected.
        self.ensure_connection.assert_called_once_with(self.session, self.options)
        self.session.getTaskInfo.assert_called_once_with(self.parent_task_id)
        self.session.getTaskChildren.assert_called_once_with(self.parent_task_id)
        self.list_task_output_all_volumes.assert_has_calls([mock.call(self.session, 22222)])
        self.assertListEqual(self.download_file.mock_calls, [
            call('https://topurl/vol/vol3/work/tasks/2222/22222/somerpm.noarch.rpm',
                 'vol3/somerpm.noarch.rpm', quiet=None, noprogress=None, size=3, num=1),
            call('https://topurl/work/tasks/2222/22222/somelog.noarch.log',
                 'somelog.noarch.log', quiet=None, noprogress=None, size=3, num=2),
            call('https://topurl/vol/vol1/work/tasks/2222/22222/somelog.noarch.log',
                 'vol1/somelog.noarch.log', quiet=None, noprogress=None, size=3, num=3)
        ])
        self.assertIsNone(rv)

    def test_handle_download_task_all_log(self):
        args = [str(self.parent_task_id), '--all', '--log']
        self.session.getTaskInfo.return_value = self.parent_task_info
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
            {},
            {'somerpm.src.rpm': ['DEFAULT', 'vol1'], 'somerpm.noarch.rpm': ['DEFAULT']},
            {'somerpm.x86_64.rpm': ['DEFAULT', 'vol2']},
            {'somerpm.s390.rpm': ['vol2']},
            {'somelog.log': ['DEFAULT', 'vol1'], 'somerpm.noarch.rpm': ['vol3']},
        ]
        # Run it and check immediate output
        # args: task_id --all --log
        # expected: success
        rv = anon_handle_download_task(self.options, self.session, args)

        actual = self.stdout.getvalue()
        expected = ''
        self.assertMultiLineEqual(actual, expected)
        # Finally, assert that things were called as we expected.
        self.ensure_connection.assert_called_once_with(self.session, self.options)
        self.session.getTaskInfo.assert_called_once_with(self.parent_task_id)
        self.session.getTaskChildren.assert_called_once_with(self.parent_task_id)
        self.assertEqual(self.list_task_output_all_volumes.mock_calls, [
            call(self.session, self.parent_task_id),
            call(self.session, 22222),
            call(self.session, 33333),
            call(self.session, 44444),
            call(self.session, 55555)])
        self.assertListEqual(self.download_file.mock_calls, [
            call('https://topurl/work/tasks/2222/22222/somerpm.src.rpm',
                 'somerpm.src.rpm', quiet=None, noprogress=None, size=9, num=1),
            call('https://topurl/vol/vol1/work/tasks/2222/22222/somerpm.src.rpm',
                 'vol1/somerpm.src.rpm', quiet=None, noprogress=None, size=9, num=2),
            call('https://topurl/work/tasks/2222/22222/somerpm.noarch.rpm',
                 'somerpm.noarch.rpm', quiet=None, noprogress=None, size=9, num=3),
            call('https://topurl/work/tasks/3333/33333/somerpm.x86_64.rpm',
                 'somerpm.x86_64.rpm', quiet=None, noprogress=None, size=9, num=4),
            call('https://topurl/vol/vol2/work/tasks/3333/33333/somerpm.x86_64.rpm',
                 'vol2/somerpm.x86_64.rpm', quiet=None, noprogress=None, size=9, num=5),
            call('https://topurl/vol/vol2/work/tasks/4444/44444/somerpm.s390.rpm',
                 'vol2/somerpm.s390.rpm', quiet=None, noprogress=None, size=9, num=6),
            call('https://topurl/work/tasks/5555/55555/somelog.log',
                 'somelog.noarch.log', quiet=None, noprogress=None, size=9, num=7),
            call('https://topurl/vol/vol1/work/tasks/5555/55555/somelog.log',
                 'vol1/somelog.noarch.log', quiet=None, noprogress=None, size=9, num=8),
            call('https://topurl/vol/vol3/work/tasks/5555/55555/somerpm.noarch.rpm',
                 'vol3/somerpm.noarch.rpm', quiet=None, noprogress=None, size=9, num=9),
        ])
        self.assertIsNone(rv)

    def test_handle_download_task_parent_dirpertask_all_conflict_names(self):
        args = [str(self.parent_task_id), '--all']
        self.session.getTaskInfo.return_value = self.parent_task_info
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
            {},
            {'somerpm.src.rpm': ['DEFAULT', 'vol1'], 'somerpm.noarch.rpm': ['DEFAULT']},
            {'somerpm.x86_64.rpm': ['DEFAULT', 'vol2']},
            {'somerpm.s390.rpm': ['vol2']},
            {'somerpm.noarch.rpm': ['DEFAULT'],
             'somelog.log': ['DEFAULT', 'vol1']},
        ]
        # Run it and check immediate output
        # args: task_id --dirpertask --log
        # expected: failure
        self.assert_system_exit(
            anon_handle_download_task,
            self.options, self.session, args,
            stderr="Download files names conflict, use --dirpertask\n",
            stdout='',
            activate_session=None,
            exit_code=1)
        actual = self.stdout.getvalue()
        expected = ''
        self.assertMultiLineEqual(actual, expected)
        # Finally, assert that things were called as we expected.
        self.ensure_connection.assert_called_once_with(self.session, self.options)
        self.session.getTaskInfo.assert_called_once_with(self.parent_task_id)
        self.session.getTaskChildren.assert_called_once_with(self.parent_task_id)
        self.assertEqual(self.list_task_output_all_volumes.mock_calls, [
            call(self.session, self.parent_task_id),
            call(self.session, 22222),
            call(self.session, 33333),
            call(self.session, 44444),
            call(self.session, 55555)])
        self.assertListEqual(self.download_file.mock_calls, [])

    def test_handle_download_task_without_all_json_not_downloaded(self):
        args = [str(self.parent_task_id)]
        self.session.getTaskInfo.return_value = self.parent_task_info
        self.session.getTaskChildren.return_value = []
        self.list_task_output_all_volumes.return_value = {
            'somerpm.src.rpm': ['DEFAULT', 'vol1'],
            'somerpm.x86_64.rpm': ['DEFAULT', 'vol2'],
            'somerpm.noarch.rpm': ['vol3'],
            'somelog.log': ['DEFAULT', 'vol1'],
            'somefile.json': ['DEFAULT', 'vol1'],
        }

        calls = self.gen_calls(self.list_task_output_all_volumes.return_value,
                               'https://topurl/%swork/tasks/3333/123333/%s',
                               ['somelog.log', 'somefile.json'])

        # Run it and check immediate output
        # args: task_id
        # expected: success
        rv = anon_handle_download_task(self.options, self.session, args)

        actual = self.stdout.getvalue()
        expected = ''
        self.assertMultiLineEqual(actual, expected)
        # Finally, assert that things were called as we expected.
        self.ensure_connection.assert_called_once_with(self.session, self.options)
        self.session.getTaskInfo.assert_called_once_with(self.parent_task_id)
        self.session.getTaskChildren.assert_called_once_with(self.parent_task_id)
        self.list_task_output_all_volumes.assert_called_once_with(self.session,
                                                                  self.parent_task_id)
        self.assertListEqual(self.download_file.mock_calls, calls)
        self.assertIsNone(rv)
