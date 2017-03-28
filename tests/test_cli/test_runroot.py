import os
import sys
import unittest
import koji

import StringIO as stringio

import mock

import loadcli
cli = loadcli.cli


class TestListCommands(unittest.TestCase):

    def setUp(self):
        self.options = mock.MagicMock()
        self.session = mock.MagicMock()
        self.session.getAPIVersion.return_value = koji.API_VERSION
        self.args = mock.MagicMock()
        self.original_parser = cli.OptionParser
        cli.OptionParser = mock.MagicMock()
        self.parser = cli.OptionParser.return_value
        cli.options = self.options  # globals!!!

    def tearDown(self):
        cli.OptionParser = self.original_parser

    # Show long diffs in error output...
    maxDiff = None

    @mock.patch('sys.stdout', new_callable=stringio.StringIO)
    def test_handle_runroot(self, stdout):
        tag = 'tag'
        arch = 'arch'
        command = 'command'
        arguments = [tag, arch, command]
        options = mock.MagicMock()
        options.new_chroot = False
        self.parser.parse_args.return_value = [options, arguments]

        # Mock out the xmlrpc server
        self.session.getTaskInfo.return_value = {'state': 1}
        self.session.downloadTaskOutput.return_value = 'task output'
        self.session.listTaskOutput.return_value = {'runroot.log': ['DEFAULT']}
        self.session.runroot.return_value = 1

        # Run it and check immediate output
        cli.handle_runroot(self.options, self.session, self.args)
        actual = stdout.getvalue()
        actual = actual.replace('nosetests', 'koji')
        expected = 'successfully connected to hub\n1\ntask output'
        self.assertMultiLineEqual(actual, expected)

        # Finally, assert that things were called as we expected.
        self.session.getTaskInfo.assert_called_once_with(1)
        self.session.listTaskOutput.assert_called_once_with(1, all_volumes=True)
        self.session.downloadTaskOutput.assert_called_once_with(
            1, 'runroot.log', volume='DEFAULT')
        self.session.runroot.assert_called_once_with(
            tag, arch, command, repo_id=mock.ANY, weight=mock.ANY,
            mounts=mock.ANY, packages=mock.ANY, skip_setarch=mock.ANY,
            channel=mock.ANY,
        )
