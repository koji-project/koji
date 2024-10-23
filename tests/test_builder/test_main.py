from __future__ import absolute_import
import signal
import unittest
try:
    from unittest import mock
except ImportError:
    import mock

import koji
from .loadkojid import kojid


class MyError(Exception):
    """sentinel exception"""
    pass


class TestMain(unittest.TestCase):

    def setUp(self):
        # set up task handler
        self.session = mock.MagicMock()
        self.options = mock.MagicMock()
        self.options.plugin = []
        self.options.sleeptime = 1
        self.options.pluginpath = ''
        self.setup_rlimits = mock.patch('koji.util.setup_rlimits').start()
        self.TaskManager = mock.MagicMock()
        # the kojid import is weird, so we use patch.object
        self.tm_class = mock.patch.object(kojid, 'TaskManager',
                                          return_value=self.TaskManager).start()
        self.PluginTracker = mock.patch('koji.plugin.PluginTracker').start()
        self.signal = mock.patch('signal.signal').start()
        self.sleep = mock.patch('time.sleep').start()
        self.exit = mock.patch('sys.exit').start()  # XXX safe?
        self.execv = mock.patch('os.execv').start()

    def tearDown(self):
        mock.patch.stopall()

    def test_kojid_main_no_tasks(self):
        # simulate getting no task for a few iterations
        self.TaskManager.getNextTask.side_effect = [False, False, False, KeyboardInterrupt()]
        kojid.main(self.options, self.session)

        self.assertEqual(len(self.TaskManager.updateBuildroots.mock_calls), 4)
        self.assertEqual(len(self.TaskManager.updateTasks.mock_calls), 4)
        self.assertEqual(len(self.TaskManager.getNextTask.mock_calls), 4)
        self.assertEqual(len(self.sleep.mock_calls), 3)
        self.TaskManager.shutdown.assert_called_once()
        self.session.logout.assert_called_once()

    def test_kojid_main_several_tasks(self):
        # simulate getting a block of tasks
        self.TaskManager.getNextTask.side_effect = [True, True, True, False, KeyboardInterrupt()]
        kojid.main(self.options, self.session)

        self.assertEqual(len(self.TaskManager.updateBuildroots.mock_calls), 2)
        self.assertEqual(len(self.TaskManager.updateTasks.mock_calls), 5)
        self.assertEqual(len(self.TaskManager.getNextTask.mock_calls), 5)
        self.assertEqual(len(self.sleep.mock_calls), 1)
        self.TaskManager.shutdown.assert_called_once()
        self.session.logout.assert_called_once()

    def test_kojid_main_restart(self):
        self.TaskManager.getNextTask.side_effect = kojid.ServerRestart()
        self.execv.side_effect = Exception('execv')
        with self.assertRaises(Exception):
            kojid.main(self.options, self.session)

        self.assertEqual(len(self.TaskManager.updateBuildroots.mock_calls), 1)
        self.assertEqual(len(self.TaskManager.updateTasks.mock_calls), 1)
        self.assertEqual(len(self.TaskManager.getNextTask.mock_calls), 1)
        self.sleep.assert_not_called()
        self.TaskManager.shutdown.assert_not_called()
        self.session.logout.assert_not_called()  # XXX

    def test_kojid_main_auth_expired(self):
        self.TaskManager.getNextTask.side_effect = koji.AuthExpired()
        kojid.main(self.options, self.session)

        self.assertEqual(len(self.TaskManager.updateBuildroots.mock_calls), 1)
        self.assertEqual(len(self.TaskManager.updateTasks.mock_calls), 1)
        self.assertEqual(len(self.TaskManager.getNextTask.mock_calls), 1)
        self.sleep.assert_not_called()
        self.TaskManager.shutdown.assert_called_once()
        self.session.logout.assert_called_once()  # XXX
        self.exit.assert_called_once_with(1)

    def test_kojid_main_auth_error(self):
        self.TaskManager.getNextTask.side_effect = koji.AuthError()
        kojid.main(self.options, self.session)

        self.assertEqual(len(self.TaskManager.updateBuildroots.mock_calls), 1)
        self.assertEqual(len(self.TaskManager.updateTasks.mock_calls), 1)
        self.assertEqual(len(self.TaskManager.getNextTask.mock_calls), 1)
        self.sleep.assert_not_called()
        self.TaskManager.shutdown.assert_called_once()
        self.session.logout.assert_called_once()  # XXX
        self.exit.assert_called_once_with(1)

    def test_kojid_main_general_error(self):
        self.TaskManager.getNextTask.side_effect = [Exception('weird error'), SystemExit]
        # the SystemExit is to ensure we exit, but we shouldn't reach it
        self.sleep.side_effect = MyError('stop here')
        with self.assertRaises(MyError):
            kojid.main(self.options, self.session)

        self.sleep.assert_called_once()
        self.TaskManager.shutdown.assert_not_called()
        self.session.logout.assert_not_called()  # XXX

    def test_kojid_main_retry_error(self):
        self.TaskManager.getNextTask.side_effect = koji.RetryError()
        with self.assertRaises(koji.RetryError):
            kojid.main(self.options, self.session)

        self.assertEqual(len(self.TaskManager.updateBuildroots.mock_calls), 1)
        self.assertEqual(len(self.TaskManager.updateTasks.mock_calls), 1)
        self.assertEqual(len(self.TaskManager.getNextTask.mock_calls), 1)
        self.sleep.assert_not_called()
        # XXX should kojid try to clean up on retry errors?
        self.TaskManager.shutdown.assert_not_called()

    def test_kojid_shutdown_handler(self):
        self.signal.side_effect = Exception('stop here')
        with self.assertRaises(Exception):
            kojid.main(self.options, self.session)

        # grab the handler
        self.signal.assert_called_once()
        self.assertEqual(self.signal.mock_calls[0][1][0], signal.SIGTERM)
        handler = self.signal.mock_calls[0][1][1]

        self.signal.side_effect = None

        # make sure the handler does what it should
        with self.assertRaises(SystemExit):
            handler()

        # make sure main handles such an exception correctly
        self.TaskManager.updateTasks.side_effect = SystemExit
        # should catch and exit
        kojid.main(self.options, self.session)

        self.exit.assert_called_once()

    def test_kojid_sleep_exit(self):
        # SystemExit handling in sleep call
        self.TaskManager.getNextTask.return_value = False
        self.sleep.side_effect = SystemExit
        kojid.main(self.options, self.session)
        self.exit.assert_called_once()

    def test_kojid_restart_handler(self):
        self.signal.side_effect = [None, Exception('stop here')]
        with self.assertRaises(Exception):
            kojid.main(self.options, self.session)

        # grab the handler
        self.assertEqual(self.signal.mock_calls[1][1][0], signal.SIGUSR1)
        handler = self.signal.mock_calls[1][1][1]

        self.signal.side_effect = None

        # make sure the handler does what it should
        handler()

        self.assertEqual(self.TaskManager.restart_pending, True)

    def test_kojid_plugins(self):
        self.options.plugin = ['PLUGIN']
        pt = mock.MagicMock()
        self.PluginTracker.return_value = pt
        # make sure main stops
        self.TaskManager.updateTasks.side_effect = SystemExit
        kojid.main(self.options, self.session)

        pt.load.assert_called_once_with('PLUGIN')


# the end
