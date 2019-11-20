from __future__ import absolute_import
import mock
import shutil
import tempfile
try:
    import unittest2 as unittest
except ImportError:
    import unittest

import koji.tasks


class TestRestartTask(unittest.TestCase):

    def setUp(self):
        self.session = mock.MagicMock()
        self.options = mock.MagicMock()
        self.manager = mock.MagicMock()
        self.workdir = tempfile.mkdtemp()
        self.options.workdir = self.workdir
        self.safe_rmtree = mock.patch('koji.tasks.safe_rmtree').start()

    def tearDown(self):
        shutil.rmtree(self.workdir)
        mock.patch.stopall()

    def get_handler(self, *args, **kwargs):
        params = koji.encode_args(*args, **kwargs)
        handler = koji.tasks.RestartTask(137, 'restart', params, self.session,
                    self.options)
        # this is a foreground task
        handler.setManager(self.manager)
        return handler

    def test_restart_task(self):
        host = {'id': 'HOST ID'}
        self.session.host.getID.return_value = "HOST ID"
        handler = self.get_handler(host)
        self.assertEqual(handler.Foreground, True)
        handler.run()

        self.assertEqual(self.manager.restart_pending, True)

    def test_restart_wrong_host(self):
        host = {'id': 'HOST ID'}
        self.session.host.getID.return_value = "ANOTHER HOST"
        handler = self.get_handler(host)
        self.assertEqual(handler.Foreground, True)
        with self.assertRaises(koji.GenericError):
            handler.run()


class TestRestartVerifyTask(unittest.TestCase):

    def setUp(self):
        self.session = mock.MagicMock()
        self.options = mock.MagicMock()
        self.manager = mock.MagicMock()
        self.workdir = tempfile.mkdtemp()
        self.options.workdir = self.workdir
        self.safe_rmtree = mock.patch('koji.tasks.safe_rmtree').start()

    def tearDown(self):
        shutil.rmtree(self.workdir)
        mock.patch.stopall()

    def get_handler(self, *args, **kwargs):
        params = koji.encode_args(*args, **kwargs)
        handler = koji.tasks.RestartVerifyTask(137, 'restartVerify', params, self.session,
                    self.options)
        # this is a foreground task
        handler.setManager(self.manager)
        return handler

    def test_restart_verify_task(self):
        task1 = {
            'id': 'TASK ID',
            'state': koji.TASK_STATES['CLOSED'],
            'completion_ts': 10,
        }
        host = {'id': 'HOST ID'}
        self.session.host.getID.return_value = "HOST ID"
        self.session.getTaskInfo.return_value = task1
        handler = self.get_handler(task1['id'], host)
        self.manager.start_ts = 100  # greater than task1['start_time']
        self.assertEqual(handler.Foreground, True)
        handler.run()

    def test_restart_verify_not_closed(self):
        task1 = {
            'id': 'TASK ID',
            'state': koji.TASK_STATES['OPEN'],
            'completion_ts': 10,
        }
        host = {'id': 'HOST ID'}
        self.session.host.getID.return_value = "HOST ID"
        self.session.getTaskInfo.return_value = task1
        handler = self.get_handler(task1['id'], host)
        try:
            handler.run()
        except koji.GenericError as e:
            self.assertEqual(e.args[0], 'Stage one restart task is OPEN')
        else:
            raise Exception('Error not raised')

    def test_restart_verify_wrong_host(self):
        task1 = {
            'id': 'TASK ID',
            'state': koji.TASK_STATES['CLOSED'],
            'completion_ts': 10,
        }
        host = {'id': 'HOST ID'}
        self.session.host.getID.return_value = "OTHER HOST"
        self.session.getTaskInfo.return_value = task1
        handler = self.get_handler(task1['id'], host)
        try:
            handler.run()
        except koji.GenericError as e:
            self.assertEqual(e.args[0], 'Host mismatch')
        else:
            raise Exception('Error not raised')

    def test_restart_verify_wrong_time(self):
        task1 = {
            'id': 'TASK ID',
            'state': koji.TASK_STATES['CLOSED'],
            'completion_ts': 10,
        }
        host = {'id': 'HOST ID'}
        self.session.host.getID.return_value = "HOST ID"
        self.session.getTaskInfo.return_value = task1
        handler = self.get_handler(task1['id'], host)
        self.manager.start_ts = 0  # LESS THAN task1['start_time']
        try:
            handler.run()
        except koji.GenericError as e:
            self.assertEqual(e.args[0][:30], 'Restart failed - start time is')
        else:
            raise Exception('Error not raised')


class TestRestartHostsTask(unittest.TestCase):

    def setUp(self):
        self.session = mock.MagicMock()
        self.options = mock.MagicMock()
        self.manager = mock.MagicMock()
        self.workdir = tempfile.mkdtemp()
        self.options.workdir = self.workdir
        self.safe_rmtree = mock.patch('koji.tasks.safe_rmtree').start()

    def tearDown(self):
        shutil.rmtree(self.workdir)
        mock.patch.stopall()

    def get_handler(self, *args, **kwargs):
        params = koji.encode_args(*args, **kwargs)
        handler = koji.tasks.RestartHostsTask(137, 'restartHosts', params, self.session,
                    self.options)
        handler.wait = mock.MagicMock()
        handler.subtask = mock.MagicMock()
        return handler

    def test_restart_hosts_task(self):
        self.session.host.getID.return_value = "THIS HOST"
        host = {'id': 99}
        self.session.listHosts.return_value = [host]
        handler = self.get_handler({})
        handler.subtask.side_effect = [101, 102]
        handler.run()

        self.session.listHosts.assert_called_once_with(enabled=True)
        self.session.taskFinished.assert_not_called()
        handler.wait.assert_called_once_with([101, 102], all=True, timeout=3600*24)
        # subtask calls
        call1 = mock.call('restart', [host], assign=host['id'], label="restart %i" % host['id'])
        call2 = mock.call('restartVerify', [101, host], assign=host['id'], label="sleep %i" % host['id'])
        handler.subtask.assert_has_calls([call1, call2])

    def test_restart_hosts_no_host(self):
        self.session.listHosts.return_value = []
        handler = self.get_handler({})
        try:
            handler.run()
        except koji.GenericError as e:
            self.assertEqual(e.args[0], 'No matching hosts')
        else:
            raise Exception('Error not raised')

        self.session.listHosts.assert_called_once_with(enabled=True)
        self.session.taskFinished.assert_not_called()
        handler.wait.assert_not_called()
        handler.subtask.assert_not_called()

    def test_restart_hosts_with_opts(self):
        self.session.host.getID.return_value = "THIS HOST"
        host = {'id': 99}
        self.session.listHosts.return_value = [host]
        self.session.getChannel.return_value = {'id': 1, 'name': 'default'}
        handler = self.get_handler({'channel': 'default', 'arches': ['x86_64']})
        handler.subtask.side_effect = [101, 102]
        handler.run()

        self.session.listHosts.assert_called_once_with(enabled=True, channelID=1, arches=['x86_64'])
        self.session.taskFinished.assert_not_called()
        handler.wait.assert_called_once_with([101, 102], all=True, timeout=3600*24)
        # subtask calls
        call1 = mock.call('restart', [host], assign=host['id'], label="restart %i" % host['id'])
        call2 = mock.call('restartVerify', [101, host], assign=host['id'], label="sleep %i" % host['id'])
        handler.subtask.assert_has_calls([call1, call2])

    def test_restart_hosts_self_finished(self):
        self.session.host.getID.return_value = 99
        host = {'id': 99}
        self.session.listHosts.return_value = [host]
        handler = self.get_handler({})
        self.session.taskFinished.return_value = True
        handler.subtask.side_effect = [101, 102]
        handler.run()

        self.session.listHosts.assert_called_once_with(enabled=True)
        self.session.taskFinished.assert_called_once()
        call1 = mock.call('restart', [host], assign=host['id'], label="restart %i" % host['id'])
        call2 = mock.call('restartVerify', [101, host], assign=host['id'], label="sleep %i" % host['id'])
        handler.subtask.assert_has_calls([call1, call2])
        call1 = mock.call(101, timeout=3600*24)
        call2 = mock.call([101, 102], all=True, timeout=3600*24)
        handler.wait.assert_has_calls([call1, call2])

    def test_restart_hosts_self_unfinished(self):
        self.session.host.getID.return_value = 99
        host = {'id': 99}
        self.session.listHosts.return_value = [host]
        handler = self.get_handler({})
        self.session.taskFinished.return_value = False
        handler.subtask.side_effect = [101, 102]
        with self.assertRaises(koji.tasks.ServerRestart):
            handler.run()

        self.session.listHosts.assert_called_once_with(enabled=True)
        self.session.taskFinished.assert_called_once()
        call1 = mock.call('restart', [host], assign=host['id'], label="restart %i" % host['id'])
        call2 = mock.call('restartVerify', [101, host], assign=host['id'], label="sleep %i" % host['id'])
        handler.subtask.assert_has_calls([call1, call2])
        handler.wait.assert_called_once_with(101, timeout=3600*24)
