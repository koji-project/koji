from __future__ import absolute_import
import io
try:
    from unittest import mock
except ImportError:
    import mock
import six
import unittest
import os
import sys

import koji
from . import load_plugin

runroot = load_plugin.load_plugin('cli', 'runroot')


class ParserError(Exception):
    pass


def mock_stdout():
    def get_mock():
        if six.PY2:
            return six.StringIO()
        else:
            return io.TextIOWrapper(six.BytesIO())
    return mock.patch('sys.stdout', new_callable=get_mock)


def get_stdout_value(stdout):
    if six.PY2:
        return stdout.getvalue()
    else:
        # we have to force the TextIOWrapper to stop buffering
        return stdout.detach().getvalue()


class TestListCommands(unittest.TestCase):

    def setUp(self):
        self.options = mock.MagicMock()
        self.options.debug = False
        self.options.quiet = False
        self.session = mock.MagicMock()
        self.session.getAPIVersion.return_value = koji.API_VERSION
        self.args = [
            '--skip-setarch',
            '--use-shell',
            '--new-chroot',
            '--task-id',
            '--package', 'rpm_a',
            '--package', 'rpm_b',
            '--mount', 'mount_a',
            '--mount', 'mount_b',
            '--weight', '3',
            '--channel-override', 'some_channel',
            '--repo-id', '12345',
            'TAG', 'ARCH', 'COMMAND']
        self.old_OptionParser = runroot.OptionParser
        runroot.OptionParser = mock.MagicMock(side_effect=self.get_parser)
        self.old_watch_tasks = runroot.watch_tasks
        runroot.watch_tasks = mock.MagicMock(name='watch_tasks')
        self.progname = os.path.basename(sys.argv[0]) or 'koji'

    def tearDown(self):
        runroot.OptionParser = self.old_OptionParser
        runroot.watch_tasks = self.old_watch_tasks

    def get_parser(self, *a, **kw):
        # we don't want parser.error to exit
        parser = self.old_OptionParser(*a, **kw)
        parser.error = mock.MagicMock(side_effect=ParserError)
        return parser

    # Show long diffs in error output...
    maxDiff = None

    @mock.patch('time.sleep')
    @mock_stdout()
    def test_handle_runroot(self, stdout, sleep):
        # Mock out the xmlrpc server
        self.session.getTaskInfo.return_value = {'state': 1}
        self.session.downloadTaskOutput.return_value = six.b('task output')
        self.session.listTaskOutput.return_value = {'runroot.log': ['DEFAULT']}
        self.session.runroot.return_value = 1
        self.session.taskFinished.side_effect = [False, True]

        # Run it and check immediate output
        runroot.handle_runroot(self.options, self.session, self.args)
        actual = get_stdout_value(stdout)
        expected = b'1\ntask output'
        self.assertEqual(actual, expected)

        # Finally, assert that things were called as we expected.
        self.session.getTaskInfo.assert_called_once_with(1)
        self.session.listTaskOutput.assert_called_once_with(1, all_volumes=True)
        self.session.downloadTaskOutput.assert_called_once_with(
            1, 'runroot.log', volume='DEFAULT')
        self.session.runroot.assert_called_once_with(
            'TAG', 'ARCH', 'COMMAND',
            repo_id=12345, weight=3,
            mounts=['mount_a', 'mount_b'],
            packages=['rpm_a', 'rpm_b'],
            skip_setarch=True,
            channel='some_channel',
            new_chroot=True,
        )

    def test_handle_runroot_watch(self):
        args = ['--watch', 'TAG', 'ARCH', 'COMMAND']

        # Mock out the xmlrpc server
        self.session.runroot.return_value = 1

        # Run it and check immediate output
        runroot.handle_runroot(self.options, self.session, args)

        # Finally, assert that things were called as we expected.
        runroot.watch_tasks.assert_called_once()
        self.session.getTaskInfo.assert_not_called()
        self.session.listTaskOutput.assert_not_called()
        self.session.downloadTaskOutput.assert_not_called()
        self.session.runroot.assert_called_once()

    def test_invalid_arguments(self):
        args = ['TAG', 'COMMAND']  # no arch

        # Run it and check immediate output
        with self.assertRaises(ParserError):
            runroot.handle_runroot(self.options, self.session, args)

        # Finally, assert that things were called as we expected.
        self.session.getTaskInfo.assert_not_called()
        self.session.listTaskOutput.assert_not_called()
        self.session.downloadTaskOutput.assert_not_called()
        self.session.runroot.assert_not_called()

    def test_nowait(self):
        args = ['--nowait', 'TAG', 'ARCH', 'COMMAND']

        # Mock out the xmlrpc server
        self.session.runroot.return_value = 1

        # Run it and check immediate output
        runroot.handle_runroot(self.options, self.session, args)

        # Finally, assert that things were called as we expected.
        runroot.watch_tasks.assert_not_called()
        self.session.getTaskInfo.assert_not_called()
        self.session.listTaskOutput.assert_not_called()
        self.session.downloadTaskOutput.assert_not_called()
        self.session.runroot.assert_called_once()

    def test_fail_call(self):
        args = ['--nowait', 'TAG', 'ARCH', 'COMMAND']

        # Mock out the xmlrpc server
        self.session.runroot.side_effect = koji.GenericError()

        with self.assertRaises(koji.GenericError):
            runroot.handle_runroot(self.options, self.session, args)

    @mock_stdout()
    def test_missing_plugin(self, stdout):
        args = ['--nowait', 'TAG', 'ARCH', 'COMMAND']

        # Mock out the xmlrpc server
        self.session.runroot.side_effect = koji.GenericError('Invalid method')

        with self.assertRaises(koji.GenericError):
            runroot.handle_runroot(self.options, self.session, args)

        actual = get_stdout_value(stdout).strip()
        self.assertEqual(actual,
                         b"* The runroot plugin appears to not be installed on the"
                         b" koji hub.  Please contact the administrator.")

    @mock_stdout()
    def test_runroot_help(self, stdout):
        with self.assertRaises(SystemExit) as ex:
            runroot.handle_runroot(self.options, self.session, ['--help'])
        std_output = get_stdout_value(stdout).decode('utf-8')
        expected_help = """Usage: %s runroot [options] <tag> <arch> <command>
(Specify the --help global option for a list of other help options)

Options:
  -h, --help            show this help message and exit
  -p PACKAGE, --package=PACKAGE
                        make sure this package is in the chroot
  -m MOUNT, --mount=MOUNT
                        mount this directory read-write in the chroot
  --skip-setarch        bypass normal setarch in the chroot
  -w WEIGHT, --weight=WEIGHT
                        set task weight
  --channel-override=CHANNEL_OVERRIDE
                        use a non-standard channel
  --task-id             Print the ID of the runroot task
  --use-shell           Run command through a shell, otherwise uses exec
  --new-chroot          Run command with the --new-chroot (systemd-nspawn)
                        option to mock
  --old-chroot          Run command with the --old-chroot (systemd-nspawn)
                        option to mock
  --repo-id=REPO_ID     ID of the repo to use
  --nowait              Do not wait on task
  --watch               Watch task instead of printing runroot.log
  --quiet               Do not print the task information
""" % self.progname
        self.assertMultiLineEqual(std_output, expected_help)
        self.assertEqual('0', str(ex.exception))
