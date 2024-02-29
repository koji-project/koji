from __future__ import absolute_import

import mock

import koji
import six
from koji_cli.commands import handle_cancel
from . import utils


class TestCancel(utils.CliTestCase):

    def __vm(self, result):
        m = koji.VirtualCall('mcall_method', [], {})
        if isinstance(result, dict) and result.get('faultCode'):
            m._result = result
        else:
            m._result = (result,)
        return m

    def setUp(self):
        self.maxDiff = None
        self.options = mock.MagicMock()
        self.options.quiet = False
        self.session = mock.MagicMock()
        self.session.multicall.return_value.__enter__.return_value = self.session
        self.activate_session_mock = mock.patch('koji_cli.commands.activate_session').start()
        self.stderr = mock.patch('sys.stderr', new_callable=six.StringIO).start()
        self.stdout = mock.patch('sys.stdout', new_callable=six.StringIO).start()
        self.error_format = """Usage: %s cancel [options] <task_id|build> [<task_id|build> ...]
(Specify the --help global option for a list of other help options)

%s: error: {message}
""" % (self.progname, self.progname)
        self.session.hub_version = (1, 33, 0)
        self.session.hub_version_str = '1.33.0'

    def test_anon_cancel(self):
        args = ['123']
        self.activate_session_mock.side_effect = koji.GenericError

        with self.assertRaises(koji.GenericError):
            handle_cancel(self.options, self.session, args)

        self.activate_session_mock.assert_called_once_with(self.session, self.options)
        self.session.cancelTask.assert_not_called()
        self.session.cancelTaskFull.assert_not_called()
        self.session.cancelBuild.assert_not_called()

    def test_cancel_tasks(self):
        # integers are always treated like task IDs, not build IDs
        args = ['123', '234']

        handle_cancel(self.options, self.session, args)

        self.activate_session_mock.assert_called_once_with(self.session, self.options)
        self.session.cancelTask.assert_has_calls([mock.call(123), mock.call(234)])
        self.session.cancelTaskFull.assert_not_called()
        self.session.cancelBuild.assert_not_called()

    def test_cancel_wrong_nvr(self):
        args = ['nvr_cant_be_parsed']
        expected = self.format_error_message(
            "please specify only task ids (integer) or builds (n-v-r)")
        self.assert_system_exit(
            handle_cancel,
            self.options, self.session, args,
            stdout='',
            stderr=expected)

        self.session.cancelTask.assert_not_called()
        self.session.cancelTaskFull.assert_not_called()
        self.session.cancelBuild.assert_not_called()

    def test_cancel_builds(self):
        args = ['name-version-release']

        handle_cancel(self.options, self.session, args)

        self.activate_session_mock.assert_called_once_with(self.session, self.options)
        self.session.cancelTask.assert_not_called()
        self.session.cancelTaskFull.assert_not_called()
        self.session.cancelBuild.assert_called_once_with(args[0], strict=True)

    def test_cancel_builds_unused_options(self):
        # it is good for nothing here
        args = ['name-version-release', '--full', '--justone', '--force']
        handle_cancel(self.options, self.session, args)

        self.activate_session_mock.assert_called_once_with(self.session, self.options)
        self.session.cancelTask.assert_not_called()
        self.session.cancelTaskFull.assert_not_called()
        self.session.cancelBuild.assert_called_once_with(args[0], strict=True)

    def test_cancel_tasks_full(self):
        args = ['123', '--full']

        handle_cancel(self.options, self.session, args)

        self.activate_session_mock.assert_called_once_with(self.session, self.options)
        self.session.cancelTask.assert_not_called()
        self.session.cancelTaskFull.assert_called_once_with(123)
        self.session.cancelBuild.assert_not_called()

    def test_cancel_tasks_justone(self):
        args = ['123', '--justone']

        handle_cancel(self.options, self.session, args)

        self.activate_session_mock.assert_called_once_with(self.session, self.options)
        self.session.cancelTask.assert_called_once_with(123, recurse=False)
        self.session.cancelTaskFull.assert_not_called()
        self.session.cancelBuild.assert_not_called()

    def test_cancel_tasks_force(self):
        args = ['123', '--force', '--full']

        handle_cancel(self.options, self.session, args)

        self.activate_session_mock.assert_called_once_with(self.session, self.options)
        self.session.cancelTaskFull.assert_called_once_with(123, strict=False)
        self.session.cancelBuild.assert_not_called()

    def test_cancel_without_arguments(self):
        arguments = []
        self.assert_system_exit(
            handle_cancel,
            self.options, self.session, arguments,
            stderr=self.format_error_message("You must specify at least one task id or build"),
            stdout='',
            activate_session=None,
            exit_code=2)

        self.activate_session_mock.assert_not_called()
        self.session.cancelTask.assert_not_called()
        self.session.cancelTaskFull.assert_not_called()
        self.session.cancelBuild.assert_not_called()

    def test_non_exist_build_and_task(self):
        args = ['11111', 'nvr-1-30.1']
        expected_warn = """No such task: %s
No such build: '%s'
""" % (args[0], args[1])
        mcall = self.session.multicall.return_value.__enter__.return_value
        mcall.cancelTask.return_value = self.__vm(
            {'faultCode': 1000, 'faultString': 'No such task: %s' % args[0]})
        mcall.cancelBuild.return_value = self.__vm(
            {'faultCode': 1000, 'faultString': "No such build: '%s'" % args[1]})
        rv = handle_cancel(self.options, self.session, args)
        self.assertEqual(rv, 1)
        self.assert_console_message(self.stderr, expected_warn)
        self.activate_session_mock.assert_called_once_with(self.session, self.options)
        self.session.cancelTask.assert_called_once_with(int(args[0]))
        self.session.cancelTaskFull.assert_not_called()
        self.session.cancelBuild.assert_called_once_with(args[1], strict=True)

    def test_non_exist_build_and_task_older_hub(self):
        self.session.hub_version = (1, 32, 0)
        args = ['11111', 'nvr-1-30.1']
        expected_warn = """No such task: %s
""" % (args[0])
        mcall = self.session.multicall.return_value.__enter__.return_value
        mcall.cancelTask.return_value = self.__vm(
            {'faultCode': 1000, 'faultString': 'No such task: %s' % args[0]})
        mcall.cancelBuild.return_value = self.__vm(False)
        rv = handle_cancel(self.options, self.session, args)
        self.assertEqual(rv, 1)
        self.assert_console_message(self.stderr, expected_warn)
        self.activate_session_mock.assert_called_once_with(self.session, self.options)
        self.session.cancelTask.assert_called_once_with(int(args[0]))
        self.session.cancelTaskFull.assert_not_called()
        self.session.cancelBuild.assert_called_once_with(args[1])

    def test_cancel_help(self):
        self.assert_help(
            handle_cancel,
            """Usage: %s cancel [options] <task_id|build> [<task_id|build> ...]
(Specify the --help global option for a list of other help options)

Options:
  -h, --help  show this help message and exit
  --justone   Do not cancel subtasks
  --full      Full cancellation (admin only)
  --force     Allow subtasks with --full
""" % self.progname)
