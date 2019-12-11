from __future__ import absolute_import
import mock
import os
import six
import sys
try:
    import unittest2 as unittest
except ImportError:
    import unittest

import koji
from koji_cli.commands import handle_assign_task
from . import utils


class TestAssignTask(utils.CliTestCase):

    # Show long diffs in error output...
    maxDiff = None

    def setUp(self):
        self.error_format = """Usage: %s assign-task <task_id> <hostname>
(Specify the --help global option for a list of other help options)

%s: error: {message}
""" % (self.progname, self.progname)

    @mock.patch('sys.stdout', new_callable=six.StringIO)
    @mock.patch('koji_cli.commands.activate_session')
    def test_handle_assign_task(
            self, activate_session_mock, stdout):
        hostname = "host"
        task_id = "1"
        arguments = [task_id, hostname]
        options = mock.MagicMock()

        # Mock out the xmlrpc server
        session = mock.MagicMock()

        session.getTaskInfo.return_value = None
        with six.assertRaisesRegex(self, koji.GenericError,
                                   "No such task: %s" % task_id):
            handle_assign_task(options, session, arguments)

        session.getTaskInfo.return_value = "task_info"
        session.getHost.return_value = None
        with six.assertRaisesRegex(self, koji.GenericError,
                                   "No such host: %s" % hostname):
            handle_assign_task(options, session, arguments)

        arguments.append("--force")
        session.getHost.return_value = hostname
        session.hasPerm.return_value = False
        self.assert_system_exit(
            handle_assign_task,
            options, session, arguments,
            stderr=self.format_error_message("This action requires admin privileges")
        )

        # Clean stdout buffer
        stdout.truncate(0)
        stdout.seek(0)

        session.hasPerm.return_value = True
        session.assignTask.return_value = True
        handle_assign_task(options, session, arguments)
        actual = stdout.getvalue()
        expected = 'assigned task %s to host %s\n' % \
                   (task_id, hostname)
        self.assertMultiLineEqual(actual, expected)

        # Clean stdout buffer
        stdout.truncate(0)
        stdout.seek(0)

        session.assignTask.return_value = False
        handle_assign_task(options, session, arguments)
        actual = stdout.getvalue()
        expected = 'failed to assign task %s to host %s\n' % \
                   (task_id, hostname)
        self.assertMultiLineEqual(actual, expected)

        # Finally, assert that things were called as we expected.
        activate_session_mock.assert_called_with(session, options)
        session.assignTask.assert_called_with(int(task_id), hostname, True)

    @mock.patch('sys.stdout', new_callable=six.StringIO)
    @mock.patch('sys.stderr', new_callable=six.StringIO)
    @mock.patch('koji_cli.commands.activate_session')
    def test_handle_assign_task_help(
            self, activate_session_mock, stderr, stdout):
        arguments = []
        options = mock.MagicMock()

        # Mock out the xmlrpc server
        session = mock.MagicMock()

        # Run it and check immediate output
        self.assert_system_exit(
            handle_assign_task,
            options, session, arguments,
            stdout='',
            stderr=self.format_error_message('please specify a task id and a hostname'),
            activate_session=None,
            exit_code=2
        )

        # Finally, assert that things were called as we expected.
        activate_session_mock.assert_not_called()
        session.hasHost.assert_not_called()
        session.addHost.assert_not_called()


if __name__ == '__main__':
    unittest.main()
