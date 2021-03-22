from __future__ import absolute_import
import mock
import unittest

import koji
from koji_cli.commands import handle_cancel
from . import utils

class TestCancel(utils.CliTestCase):
    maxDiff = None

    def setUp(self):
        self.options = mock.MagicMock()
        self.options.quiet = False
        self.session = mock.MagicMock()
        self.session.multicall.return_value.__enter__.return_value = self.session

        self.error_format = """Usage: %s cancel [options] <task_id|build> [<task_id|build> ...]
(Specify the --help global option for a list of other help options)

%s: error: {message}
""" % (self.progname, self.progname)


    @mock.patch('koji_cli.commands.activate_session')
    def test_anon_cancel(self, activate_session_mock):
        args = ['123']
        activate_session_mock.side_effect = koji.GenericError

        with self.assertRaises(koji.GenericError):
            handle_cancel(self.options, self.session, args)

        activate_session_mock.assert_called_once_with(self.session, self.options)
        self.session.cancelTask.assert_not_called()
        self.session.cancelTaskFull.assert_not_called()
        self.session.cancelBuild.assert_not_called()

    @mock.patch('koji_cli.commands.activate_session')
    def test_cancel_tasks(self, activate_session_mock):
        # integers are always treated like task IDs, not build IDs
        args = ['123', '234']

        handle_cancel(self.options, self.session, args)

        activate_session_mock.assert_called_once_with(self.session, self.options)
        self.session.cancelTask.assert_has_calls([mock.call(123), mock.call(234)])
        self.session.cancelTaskFull.assert_not_called()
        self.session.cancelBuild.assert_not_called()

    def test_cancel_wrong_nvr(self):
        args = ['nvr_cant_be_parsed']
        expected = self.format_error_message(
            "please specify only task ids (integer) or builds (n-v-r)")
        self.assert_system_exit(
            handle_cancel,
            self.options,
            self.session,
            args,
            stdout='',
            stderr=expected)

        self.session.cancelTask.assert_not_called()
        self.session.cancelTaskFull.assert_not_called()
        self.session.cancelBuild.assert_not_called()

    @mock.patch('koji_cli.commands.activate_session')
    def test_cancel_builds(self, activate_session_mock):
        args = ['name-version-release']

        handle_cancel(self.options, self.session, args)

        activate_session_mock.assert_called_once_with(self.session, self.options)
        self.session.cancelTask.assert_not_called()
        self.session.cancelTaskFull.assert_not_called()
        self.session.cancelBuild.assert_called_once_with(args[0])

    @mock.patch('koji_cli.commands.activate_session')
    def test_cancel_builds_unused_options(self, activate_session_mock):
        # it is good for nothing here
        args = ['name-version-release', '--full', '--justone', '--force']
        handle_cancel(self.options, self.session, args)

        activate_session_mock.assert_called_once_with(self.session, self.options)
        self.session.cancelTask.assert_not_called()
        self.session.cancelTaskFull.assert_not_called()
        self.session.cancelBuild.assert_called_once_with(args[0])

    @mock.patch('koji_cli.commands.activate_session')
    def test_cancel_tasks_full(self, activate_session_mock):
        args = ['123', '--full']

        handle_cancel(self.options, self.session, args)

        activate_session_mock.assert_called_once_with(self.session, self.options)
        self.session.cancelTask.assert_not_called()
        self.session.cancelTaskFull.assert_called_once_with(123)
        self.session.cancelBuild.assert_not_called()

    @mock.patch('koji_cli.commands.activate_session')
    def test_cancel_tasks_justone(self, activate_session_mock):
        args = ['123', '--justone']

        handle_cancel(self.options, self.session, args)

        activate_session_mock.assert_called_once_with(self.session, self.options)
        self.session.cancelTask.assert_called_once_with(123, recurse=False)
        self.session.cancelTaskFull.assert_not_called()
        self.session.cancelBuild.assert_not_called()

    @mock.patch('koji_cli.commands.activate_session')
    def test_cancel_tasks_force(self, activate_session_mock):
        args = ['123', '--force', '--full']

        handle_cancel(self.options, self.session, args)

        activate_session_mock.assert_called_once_with(self.session, self.options)
        self.session.cancelTaskFull.assert_called_once_with(123, strict=False)
        self.session.cancelBuild.assert_not_called()
