from __future__ import absolute_import
try:
    from unittest import mock
except ImportError:
    import mock
import six
import unittest

import koji
from koji_cli.commands import handle_assign_task
from . import utils


class TestAssignTask(utils.CliTestCase):

    def setUp(self):
        # Show long diffs in error output...
        self.maxDiff = None
        self.options = mock.MagicMock()
        self.options.debug = False
        self.session = mock.MagicMock()
        self.session.getAPIVersion.return_value = koji.API_VERSION
        self.activate_session_mock = mock.patch('koji_cli.commands.activate_session').start()
        self.error_format = """Usage: %s assign-task <task_id> <hostname>
(Specify the --help global option for a list of other help options)

%s: error: {message}
""" % (self.progname, self.progname)

    def tearDown(self):
        mock.patch.stopall()

    @mock.patch('sys.stdout', new_callable=six.StringIO)
    def test_handle_assign_task(self, stdout):
        hostname = "host"
        task_id = "1"
        arguments = [task_id, hostname]

        self.session.getTaskInfo.return_value = None
        with six.assertRaisesRegex(self, koji.GenericError,
                                   "No such task: %s" % task_id):
            handle_assign_task(self.options, self.session, arguments)

        self.session.getTaskInfo.return_value = "task_info"
        self.session.getHost.return_value = None
        with six.assertRaisesRegex(self, koji.GenericError,
                                   "No such host: %s" % hostname):
            handle_assign_task(self.options, self.session, arguments)

        arguments.append("--force")
        self.session.getHost.return_value = hostname
        self.session.hasPerm.return_value = False
        self.assert_system_exit(
            handle_assign_task,
            self.options, self.session, arguments,
            stdout='',
            stderr=self.format_error_message("This action requires admin privileges"),
            exit_code=2
        )

        # Clean stdout buffer
        stdout.truncate(0)
        stdout.seek(0)

        self.session.hasPerm.return_value = True
        self.session.assignTask.return_value = True
        handle_assign_task(self.options, self.session, arguments)
        actual = stdout.getvalue()
        expected = 'assigned task %s to host %s\n' % \
                   (task_id, hostname)
        self.assertMultiLineEqual(actual, expected)

        # Clean stdout buffer
        stdout.truncate(0)
        stdout.seek(0)

        self.session.assignTask.return_value = False
        handle_assign_task(self.options, self.session, arguments)
        actual = stdout.getvalue()
        expected = 'failed to assign task %s to host %s\n' % \
                   (task_id, hostname)
        self.assertMultiLineEqual(actual, expected)

        # Finally, assert that things were called as we expected.
        self.activate_session_mock.assert_called_with(self.session, self.options)
        self.session.assignTask.assert_called_with(int(task_id), hostname, True)

    def test_handle_assign_task_no_args(self):
        arguments = []
        # Run it and check immediate output
        self.assert_system_exit(
            handle_assign_task,
            self.options, self.session, arguments,
            stdout='',
            stderr=self.format_error_message('please specify a task id and a hostname'),
            activate_session=None,
            exit_code=2
        )

        # Finally, assert that things were called as we expected.
        self.activate_session_mock.assert_not_called()
        self.session.hasHost.assert_not_called()
        self.session.addHost.assert_not_called()

    def test_assign_task_help(self):
        self.assert_help(
            handle_assign_task,
            """Usage: %s assign-task <task_id> <hostname>
(Specify the --help global option for a list of other help options)

Options:
  -h, --help   show this help message and exit
  -f, --force  force to assign a non-free task
""" % self.progname)


if __name__ == '__main__':
    unittest.main()
