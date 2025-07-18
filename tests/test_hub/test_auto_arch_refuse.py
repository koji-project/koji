import datetime
from unittest import mock
import unittest

import koji
import kojihub
import kojihub.db
from kojihub import scheduler


QP = scheduler.QueryProcessor
IP = scheduler.InsertProcessor
UP = scheduler.UpdateProcessor
TASK = kojihub.Task


class MyError(Exception):
    pass


class AutoRefuseTest(unittest.TestCase):

    def setUp(self):
        self._dml = mock.patch('kojihub.db._dml').start()
        # self.exports = kojihub.RootExports()
        self.task = mock.MagicMock()
        self.Task = mock.patch('kojihub.kojihub.Task', return_value=self.task).start()
        self.get_build_target = mock.patch('kojihub.kojihub.get_build_target').start()
        self.get_tag = mock.patch('kojihub.kojihub.get_tag').start()
        self.context = mock.patch('kojihub.scheduler.context').start()
        self.set_refusal = mock.patch('kojihub.scheduler.set_refusal').start()
        self.handlers = {
            'getBuildConfig': mock.MagicMock(),
            'listHosts': mock.MagicMock(),
        }
        self.context.handlers.call.side_effect = self._my_handler_call
        self.set_base_data()

    def tearDown(self):
        mock.patch.stopall()

    def set_base_data(self):
        request = [
            'tasks/8755/59888755/release-e2e-test-1.0.4474-1.el9.src.rpm',
            'TAG_ID',
            'x86_64',
            True,
            {'repo_id': 8075973}]
        self.taskinfo = {
            'arch': 'noarch',
            'channel_id': 35,
            'id': 59888794,
            'method': 'buildArch',
            'request': request,
            'state': 1,
        }
        self.task.getInfo.return_value = self.taskinfo
        self.task.isFinished.return_value = False
        self.get_tag.return_value = {'id': 'TAGID', 'name': 'MYTAG'}
        self.handlers['listHosts'].return_value = [{'id': 'HOST', 'arches': 'x86_64 i686'}]
        self.handlers['getBuildConfig'].return_value = {'arches': 'x86_64 s390x ppc64le aarch64'}

    def _my_handler_call(self, method, *a, **kw):
        handler = self.handlers[method]
        return handler(*a, **kw)

    def test_arch_overlap(self):
        # we mostly test the underlying function to avoid masking errors
        scheduler._auto_arch_refuse(100)

        self.Task.assert_called_once_with(100)
        self.get_tag.assert_called_once_with('TAG_ID')
        self.set_refusal.assert_not_called()

    def test_arch_disjoint(self):
        self.handlers['listHosts'].return_value = [{'id': 'HOST', 'arches': 'riscv128'}]
        scheduler._auto_arch_refuse(100)

        self.Task.assert_called_once_with(100)
        self.get_tag.assert_called_once_with('TAG_ID')
        self.set_refusal.assert_called_once()

    def test_no_tag_arches(self):
        self.handlers['getBuildConfig'].return_value = {'arches': ''}
        scheduler._auto_arch_refuse(100)

        self.Task.assert_called_once_with(100)
        self.get_tag.assert_called_once_with('TAG_ID')
        self.handlers['listHosts'].assert_not_called()
        self.set_refusal.assert_not_called()

    def test_mixed_hosts(self):
        good1 = [{'id': n, 'arches': 'x86_64 i686'} for n in range(0,5)]
        bad1 = [{'id': n, 'arches': 'ia64'} for n in range(5,10)]
        good2 = [{'id': n, 'arches': 'aarch64'} for n in range(10,15)]
        bad2 = [{'id': n, 'arches': 'sparc64'} for n in range(15,20)]
        hosts = good1 + bad1 + good2 + bad2
        self.handlers['listHosts'].return_value = hosts
        scheduler._auto_arch_refuse(100)

        self.Task.assert_called_once_with(100)
        self.get_tag.assert_called_once_with('TAG_ID')

        # should only refuse the bad ones
        expect = [mock.call(h['id'], 100, soft=False, msg='automatic arch refusal') for h in bad1 + bad2]
        self.assertListEqual(self.set_refusal.mock_calls, expect)

    def test_not_noarch(self):
        self.taskinfo['arch'] = 'x86_64'

        scheduler._auto_arch_refuse(100)

        self.task.isFinished.assert_not_called()

    def test_other_method(self):
        self.taskinfo['method'] = 'build'

        scheduler._auto_arch_refuse(100)

        self.task.isFinished.assert_not_called()

    def test_task_finished(self):
        self.task.isFinished.return_value = True

        scheduler._auto_arch_refuse(100)

        self.get_tag.assert_not_called()

    def test_bad_tag(self):
        self.get_tag.return_value = None

        scheduler._auto_arch_refuse(100)

        self.context.handlers.call.assert_not_called()

    def test_bad_params(self):
        self.taskinfo['request'] = []

        scheduler._auto_arch_refuse(100)

        self.get_tag.assert_not_called()

    def test_unexpected_error(self):
        self.get_tag.side_effect = MyError('should be caught')

        # the wrapper should catch this
        scheduler.auto_arch_refuse(100)

        self.context.handlers.call.assert_not_called()

    def test_unexpected_error2(self):
        self.get_tag.side_effect = MyError('should not be caught')

        # the underlying call should not
        with self.assertRaises(MyError):
            scheduler._auto_arch_refuse(100)

        self.context.handlers.call.assert_not_called()

    def test_from_scm(self):
        self.taskinfo['method'] = 'buildSRPMFromSCM'
        self.taskinfo['request'] = [
            'git+https://HOST/PATH',
            'TAG_ID',
            {'repo_id': 8075973, 'scratch': None}]

        scheduler._auto_arch_refuse(100)

        self.Task.assert_called_once_with(100)
        self.get_tag.assert_called_once_with('TAG_ID')
        self.set_refusal.assert_not_called()

    def test_from_srpm(self):
        self.taskinfo['method'] = 'rebuildSRPM'
        self.taskinfo['request'] = [
            'cli-build/1709137799.6498768.BFGhzghk/fake-1.1-35.src.rpm',
            'TAG_ID',
            {'repo_id': 2330, 'scratch': True}]

        scheduler._auto_arch_refuse(100)

        self.Task.assert_called_once_with(100)
        self.get_tag.assert_called_once_with('TAG_ID')
        self.set_refusal.assert_not_called()

    def test_wrapper(self):
        self.taskinfo['method'] = 'wrapperRPM'
        self.taskinfo['request'] = [
            'git://HOST/PATH',
            'TARGET',
             {'build_id': 421},
             None,
             {'repo_id': 958, 'scratch': True}]
        self.get_build_target.return_value = {'build_tag': 'TAG_ID'}

        scheduler._auto_arch_refuse(100)

        self.Task.assert_called_once_with(100)
        self.get_build_target.assert_called_once_with('TARGET')
        self.get_tag.assert_called_once_with('TAG_ID')
        self.set_refusal.assert_not_called()

    def test_bad_target(self):
        self.taskinfo['method'] = 'wrapperRPM'
        self.taskinfo['request'] = [
            'git://HOST/PATH',
            'TARGET',
             {'build_id': 421},
             None,
             {'repo_id': 958, 'scratch': True}]
        self.get_build_target.return_value = None

        scheduler._auto_arch_refuse(100)

        self.Task.assert_called_once_with(100)
        self.get_build_target.assert_called_once_with('TARGET')
        self.get_tag.assert_not_called()
