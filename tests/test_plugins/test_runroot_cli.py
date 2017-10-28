from __future__ import absolute_import
import mock
import six
import unittest

import koji
from . import load_plugin

runroot = load_plugin.load_plugin('cli', 'runroot')


class ParserError(Exception):
    pass


class TestListCommands(unittest.TestCase):

    def setUp(self):
        self.options = mock.MagicMock()
        self.options.debug = False
        self.session = mock.MagicMock()
        self.session.getAPIVersion.return_value = koji.API_VERSION
        self.args = ['TAG', 'ARCH', 'COMMAND']
        self.old_OptionParser = runroot.OptionParser
        runroot.OptionParser = mock.MagicMock(side_effect=self.get_parser)
        self.old_watch_tasks = runroot.watch_tasks
        runroot.watch_tasks = mock.MagicMock(name='watch_tasks')

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

    @mock.patch('sys.stdout', new_callable=six.StringIO)
    def test_handle_runroot(self, stdout):
        # Mock out the xmlrpc server
        self.session.getTaskInfo.return_value = {'state': 1}
        self.session.downloadTaskOutput.return_value = 'task output'
        self.session.listTaskOutput.return_value = {'runroot.log': ['DEFAULT']}
        self.session.runroot.return_value = 1

        # Run it and check immediate output
        runroot.handle_runroot(self.options, self.session, self.args)
        actual = stdout.getvalue()
        actual = actual.replace('nosetests', 'koji')
        expected = 'task output'
        self.assertMultiLineEqual(actual, expected)

        # Finally, assert that things were called as we expected.
        self.session.getTaskInfo.assert_called_once_with(1)
        self.session.listTaskOutput.assert_called_once_with(1, all_volumes=True)
        self.session.downloadTaskOutput.assert_called_once_with(
            1, 'runroot.log', volume='DEFAULT')
        self.session.runroot.assert_called_once_with(
            'TAG', 'ARCH', ['COMMAND'], repo_id=mock.ANY, weight=mock.ANY,
            mounts=mock.ANY, packages=mock.ANY, skip_setarch=mock.ANY,
            channel=mock.ANY,
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
