from __future__ import absolute_import
import mock
import os
import six
import sys
try:
    import unittest2 as unittest
except ImportError:
    import unittest

from mock import call

from koji_cli.commands import handle_edit_host
from . import utils

class TestEditHost(utils.CliTestCase):

    # Show long diffs in error output...
    maxDiff = None

    @mock.patch('sys.stdout', new_callable=six.StringIO)
    @mock.patch('koji_cli.commands.activate_session')
    def test_handle_edit_host(self, activate_session_mock, stdout):
        host = 'host'
        host_info = mock.ANY
        arches = 'arch1 arch2'
        capacity = 0.22
        description = 'description'
        comment = 'comment'
        args = [host]
        args.append('--arches=' + arches)
        args.append('--capacity=' + str(capacity))
        args.append('--description=' + description)
        args.append('--comment=' + comment)
        kwargs = {'arches': arches,
                  'capacity': capacity,
                  'description': description,
                  'comment': comment}
        options = mock.MagicMock()

        # Mock out the xmlrpc server
        session = mock.MagicMock()

        session.multiCall.side_effect = [[[host_info]], [[True]]]
        # Run it and check immediate output
        # args: host, --arches='arch1 arch2', --capacity=0.22,
        # --description=description, --comment=comment
        # expected: success
        rv = handle_edit_host(options, session, args)
        actual = stdout.getvalue()
        expected = 'Edited host\n'
        self.assertMultiLineEqual(actual, expected)
        # Finally, assert that things were called as we expected.
        activate_session_mock.assert_called_once_with(session, options)
        session.getHost.assert_called_once_with(host)
        session.editHost.assert_called_once_with(host, **kwargs)
        self.assertEqual(session.multiCall.call_count, 2)
        self.assertNotEqual(rv, 1)

    @mock.patch('sys.stdout', new_callable=six.StringIO)
    @mock.patch('koji_cli.commands.activate_session')
    def test_handle_edit_host_failed(self, activate_session_mock, stdout):
        host = 'host'
        host_info = mock.ANY
        arches = 'arch1 arch2'
        capacity = 0.22
        description = 'description'
        comment = 'comment'
        args = [host]
        args.append('--arches=' + arches)
        args.append('--capacity=' + str(capacity))
        args.append('--description=' + description)
        args.append('--comment=' + comment)
        kwargs = {'arches': arches,
                  'capacity': capacity,
                  'description': description,
                  'comment': comment}
        options = mock.MagicMock()

        # Mock out the xmlrpc server
        session = mock.MagicMock()

        session.multiCall.side_effect = [[[host_info]], [[False]]]
        # Run it and check immediate output
        # args: host, --arches='arch1 arch2', --capacity=0.22,
        # --description=description, --comment=comment
        # expected: failed - session.editHost == False
        rv = handle_edit_host(options, session, args)
        actual = stdout.getvalue()
        expected = 'No changes made to host\n'
        self.assertMultiLineEqual(actual, expected)
        # Finally, assert that things were called as we expected.
        activate_session_mock.assert_called_once_with(session, options)
        session.getHost.assert_called_once_with(host)
        session.editHost.assert_called_once_with(host, **kwargs)
        self.assertEqual(session.multiCall.call_count, 2)
        self.assertNotEqual(rv, 1)

    @mock.patch('sys.stdout', new_callable=six.StringIO)
    @mock.patch('koji_cli.commands.activate_session')
    def test_handle_edit_multi_host(self, activate_session_mock, stdout):
        hosts = ['host1', 'host2']
        host_infos = [mock.ANY, mock.ANY]
        arches = 'arch1 arch2'
        capacity = 0.22
        description = 'description'
        comment = 'comment'
        args = hosts
        args.append('--arches=' + arches)
        args.append('--capacity=' + str(capacity))
        args.append('--description=' + description)
        args.append('--comment=' + comment)
        kwargs = {'arches': arches,
                  'capacity': capacity,
                  'description': description,
                  'comment': comment}
        options = mock.MagicMock()

        # Mock out the xmlrpc server
        session = mock.MagicMock()

        session.multiCall.side_effect = [[[info]
                                          for info in host_infos], [[True], [True]]]
        # Run it and check immediate output
        # args: host1, host2, --arches='arch1 arch2', --capacity=0.22,
        # --description=description, --comment=comment
        # expected: success
        rv = handle_edit_host(options, session, args)
        actual = stdout.getvalue()
        expected = 'Edited host1\nEdited host2\n'
        self.assertMultiLineEqual(actual, expected)
        # Finally, assert that things were called as we expected.
        activate_session_mock.assert_called_once_with(session, options)
        self.assertEqual(session.mock_calls,
                         [call.getHost(hosts[0]),
                          call.getHost(hosts[1]),
                             call.multiCall(strict=True),
                             call.editHost(hosts[0],
                                           **kwargs),
                             call.editHost(hosts[1],
                                           **kwargs),
                             call.multiCall(strict=True)])
        self.assertNotEqual(rv, 1)

    @mock.patch('sys.stdout', new_callable=six.StringIO)
    @mock.patch('sys.stderr', new_callable=six.StringIO)
    @mock.patch('koji_cli.commands.activate_session')
    def test_handle_edit_host_no_arg(
            self, activate_session_mock, stderr, stdout):
        args = []
        options = mock.MagicMock()
        # Mock out the xmlrpc server
        session = mock.MagicMock()
        progname = os.path.basename(sys.argv[0]) or 'koji'

        # Mock out the xmlrpc server
        session = mock.MagicMock()
        # Run it and check immediate output
        # args: _empty_
        # expected: failed - should specify host
        with self.assertRaises(SystemExit) as ex:
            handle_edit_host(options, session, args)
        self.assertExitCode(ex, 2)
        actual_stdout = stdout.getvalue()
        actual_stderr = stderr.getvalue()
        expected_stdout = ''
        expected_stderr = """Usage: %s edit-host <hostname> [<hostname> ...] [options]
(Specify the --help global option for a list of other help options)

%s: error: Please specify a hostname
""" % (progname, progname)
        self.assertMultiLineEqual(actual_stdout, expected_stdout)
        self.assertMultiLineEqual(actual_stderr, expected_stderr)

        # Finally, assert that things were called as we expected.
        activate_session_mock.assert_not_called()
        session.getHost.assert_not_called()
        session.editHost.assert_not_called()
        session.multiCall.assert_not_called()

    @mock.patch('sys.stderr', new_callable=six.StringIO)
    @mock.patch('koji_cli.commands.activate_session')
    def test_handle_edit_host_no_host(self, activate_session_mock, stderr):
        host = 'host'
        host_info = None
        arches = 'arch1 arch2'
        capacity = 0.22
        description = 'description'
        comment = 'comment'
        args = [host]
        args.append('--arches=' + arches)
        args.append('--capacity=' + str(capacity))
        args.append('--description=' + description)
        args.append('--comment=' + comment)
        options = mock.MagicMock()

        # Mock out the xmlrpc server
        session = mock.MagicMock()

        session.multiCall.return_value = [[host_info]]
        # Run it and check immediate output
        # args: host, --arches='arch1 arch2', --capacity=0.22,
        # --description=description, --comment=comment
        # expected: failed -- getHost() == None
        with self.assertRaises(SystemExit) as ex:
            handle_edit_host(options, session, args)
        self.assertExitCode(ex, 1)
        actual = stderr.getvalue()
        expected = """Host host does not exist
No changes made, please correct the command line
"""
        self.assertMultiLineEqual(actual, expected)
        # Finally, assert that things were called as we expected.
        activate_session_mock.assert_called_once_with(session, options)
        session.getHost.assert_called_once_with(host)
        session.editHost.assert_not_called()
        self.assertEqual(session.multiCall.call_count, 1)

if __name__ == '__main__':
    unittest.main()
