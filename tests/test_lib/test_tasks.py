from __future__ import absolute_import
import random
import shutil
import six
from six.moves import range
try:
    import unittest2 as unittest
except ImportError:
    import unittest

from os import path, makedirs
from tempfile import gettempdir
from mock import patch, MagicMock, Mock, call
import requests_mock

import koji
from koji.tasks import BaseTaskHandler, FakeTask, ForkTask, SleepTask, \
                       WaitTestTask, scan_mounts, umount_all, \
                       safe_rmtree


def get_fake_mounts_file():
    """ Returns contents of /prc/mounts in a file-like object
    """
    return six.StringIO(six.text_type((
        'sysfs /sys sysfs rw,seclabel,nosuid,nodev,noexec,relatime 0 0\n'
        'proc /proc proc rw,nosuid,nodev,noexec,relatime 0 0\n'
        'devtmpfs /dev devtmpfs rw,seclabel,nosuid,size=238836k,nr_inodes=59709,mode=755 0 0\n'
        'securityfs /sys/kernel/security securityfs rw,nosuid,nodev,noexec,relatime 0 0\n'
        'tmpfs /dev/shm\\040(deleted) tmpfs rw,seclabel,nosuid,nodev 0 0\n'
        'devpts /dev/pts devpts rw,seclabel,nosuid,noexec,relatime,gid=5,mode=620,ptmxmode=000 0 0\n'
        'tmpfs /run tmpfs rw,seclabel,nosuid,nodev,mode=755 0 0\n'
        'tmpfs /sys/fs/cgroup tmpfs ro,seclabel,nosuid,nodev,noexec,mode=755 0 0\n'
        'pstore /sys/fs/pstore pstore rw,seclabel,nosuid,nodev,noexec,relatime 0 0\n'
        'cgroup /sys/fs/cgroup/devices cgroup rw,nosuid,nodev,noexec,relatime,devices 0 0\n'
        'cgroup /sys/fs/cgroup/perf_event cgroup rw,nosuid,nodev,noexec,relatime,perf_event 0 0\n'
        'cgroup /sys/fs/cgroup/net_cls,net_prio cgroup rw,nosuid,nodev,noexec,relatime,net_cls,net_prio 0 0\n'
        'cgroup /sys/fs/cgroup/cpu,cpuacct cgroup rw,nosuid,nodev,noexec,relatime,cpu,cpuacct 0 0\n'
        'cgroup /sys/fs/cgroup/blkio cgroup rw,nosuid,nodev,noexec,relatime,blkio 0 0\n'
        'cgroup /sys/fs/cgroup/cpuset cgroup rw,nosuid,nodev,noexec,relatime,cpuset 0 0\n'
        'cgroup /sys/fs/cgroup/freezer cgroup rw,nosuid,nodev,noexec,relatime,freezer 0 0\n'
        'cgroup /sys/fs/cgroup/memory cgroup rw,nosuid,nodev,noexec,relatime,memory 0 0\n'
        'cgroup /sys/fs/cgroup/hugetlb cgroup rw,nosuid,nodev,noexec,relatime,hugetlb 0 0\n'
        'configfs /sys/kernel/config configfs rw,relatime 0 0\n'
        'hugetlbfs /dev/hugepages hugetlbfs rw,seclabel,relatime 0 0\n'
        'mqueue /dev/mqueue mqueue rw,seclabel,relatime 0 0\n'
    )))


def get_temp_dir_root():
    return path.join(gettempdir(), 'koji_tests')


def get_tmp_dir_path(folder_starts_with):
    return path.join(get_temp_dir_root(), ('{0}{1}'.format(folder_starts_with, random.randint(1, 999999999999))))


class TestTask(BaseTaskHandler):
    Methods = ['some_method']
    _taskWeight = 5.2

    def handler(self, *args):
        return 42


class TestTaskNoWeight(BaseTaskHandler):
    Methods = ['some_method']

    def handler(self, *args):
        return 42


class BadTask(BaseTaskHandler):
    Methods = ['some_method']


class TasksTestCase(unittest.TestCase):

    def tearDown(self):
        temp_dir_root = get_temp_dir_root()

        if path.isdir(temp_dir_root):
            shutil.rmtree(get_temp_dir_root())

    def test_scan_mounts_results(self):
        """ Tests the scan_mounts function with a mocked /proc/mounts file. A list containing mount points
        starting with /dev are expected to be returned from the function based on the function input of /dev.
        """
        fake_mounts_file_contents = get_fake_mounts_file()

        with patch('koji.tasks.open', return_value=fake_mounts_file_contents, create=True):
            self.assertIn(scan_mounts('/dev'), [['/dev/shm', '/dev/pts', '/dev/mqueue', '/dev/hugepages', '/dev']])

    def test_scan_mounts_no_results(self):
        """ Tests the scan_mounts function with a mocked /proc/mounts file. An argument of /nonexistent/path
        to the function should return an empty list.
        """
        fake_mounts_file_contents = get_fake_mounts_file()

        with patch('koji.tasks.open', return_value=fake_mounts_file_contents, create=True):
            self.assertEquals(scan_mounts('/nonexistent/path'), [])

    # Patching the scan_mounts function instead of the built-in open function because this is only testing umount_all
    @patch('koji.tasks.scan_mounts', side_effect=[['/dev/shm', '/dev/pts', '/dev/mqueue'], []])
    @patch('os.spawnvp', return_value=0)
    def test_umount_all(self, mocked_spawnvp, mocked_scan_mounts):
        """ Tests that umount_all returns nothing when successful.
        """
        self.assertEquals(umount_all('/test'), None)

    # Patching the scan_mounts function instead of the built-in open function because this is only testing umount_all
    @patch('koji.tasks.scan_mounts', return_value=['/dev/shm', '/dev/pts', '/dev/mqueue'])
    @patch('os.spawnvp', return_value=1)
    def test_umount_all_failure(self, mocked_spawnvp, mocked_scan_mounts):
        """ Tests that umount_all raises an exception when a mount point can't be unmounted.
        """
        try:
            umount_all('/dev')
            raise Exception('A GenericError was not raised during the test')
        except koji.GenericError as e:
            self.assertEquals(e.args[0],
                              'umount failed (exit code 1) for /dev/shm')

    # Patching the scan_mounts function instead of the built-in open function because this is only testing umount_all
    @patch('koji.tasks.scan_mounts', side_effect=[['/dev/shm', '/dev/pts', '/dev/mqueue'], ['/dev/shm', '/dev/mqueue']])
    @patch('os.spawnvp', return_value=0)
    def test_umount_all_unexpected_failure(self, mocked_spawnvp, mocked_scan_mounts):
        """ Tests that umount_all will fail if the command to unmount the mount points was successful
        but a second run of scan_mounts still shows some of the unmount mount points still mounted.
        """
        try:
            umount_all('/dev')
            raise Exception('A GenericError was not raised during the test')
        except koji.GenericError as e:
            self.assertEquals(e.args[0], 'Unmounting incomplete: [\'/dev/shm\', \'/dev/mqueue\']')

    def test_BaseTaskHandler_handler_not_set(self):
        """ Tests that an exception is thrown when the handler function is not overwritten by the child class.
        """
        obj = BadTask(123, 'some_method', ['random_arg'], None, None, (get_tmp_dir_path('BadTask')))
        try:
            obj.handler()
            raise Exception('The NotImplementedError exception was not raised')
        except NotImplementedError as e:
            self.assertEquals(e.__class__.__name__, 'NotImplementedError')

    def test_BaseTaskHandler_weight_default(self):
        """ Tests that the weight function returns 1.0 when _taskWeight is not set in the child class' definition.
        """
        obj = TestTaskNoWeight(123, 'some_method', ['random_arg'], None, None, (get_tmp_dir_path('TestTaskNoWeight')))
        self.assertEquals(obj.weight(), 1.0)

    def test_BaseTaskHandler_weight_set(self):
        """ Tests that the weight function returns the value of _taskWeight when it is set in the
        child class' definition.
        """
        obj = TestTask(123, 'some_method', ['random_arg'], None, None, (get_tmp_dir_path('TestTask')))
        self.assertEquals(obj.weight(), 5.2)

    def test_BaseTaskHandler_createWorkdir_workdir_not_defined(self):
        """ Tests that the createWorkdir function does nothing when the workdir member variable is set to None.
        """
        temp_path = get_tmp_dir_path('TestTask')
        obj = TestTask(123, 'some_method', ['random_arg'], None, None, temp_path)
        obj.workdir = None
        obj.createWorkdir()
        self.assertEquals(path.isdir(temp_path), False)

    # This patch removes the dependence on removeWorkdir functioning
    @patch('{0}.TestTask.removeWorkdir'.format(__name__))
    def test_BaseTaskHandler_createWorkdir(self, mock_removeWorkDir):
        """ Tests that the createWorkdir function creates a folder based on the path given to the
        workdir member variable.
        """
        temp_path = get_tmp_dir_path('TestTask')
        obj = TestTask(123, 'some_method', ['random_arg'], None, None, temp_path)
        obj.createWorkdir()
        self.assertEquals(path.isdir(temp_path), True)
        shutil.rmtree(get_temp_dir_root())

    def test_BaseTaskHandler_removeWorkdir(self):
        """ Tests that the removeWOrkdir function deletes a folder based on the path given to the
        workdir member variable.
        """
        temp_path = get_tmp_dir_path('TestTask')
        obj = TestTask(123, 'some_method', ['random_arg'], None, None, temp_path)
        makedirs(temp_path)
        self.assertEquals(path.isdir(temp_path), True)
        obj.removeWorkdir()
        self.assertEquals(path.isdir(temp_path), False)

    def test_BaseTaskHandler_wait_all_done(self):
        """ Tests that the wait function returns the subtask results of when the taskWait function returns only
        two finished tasks
        """
        temp_path = get_tmp_dir_path('TestTask')
        obj = TestTask(12345678, 'some_method', ['random_arg'], None, None, temp_path)
        makedirs(temp_path)
        obj.session = Mock()
        obj.session.host.taskSetWait.return_value = None
        obj.session.host.taskWait.return_value = [[1551234, 1591234], []]
        taskWaitResults = [
            ['1551234', {
                'brootid': 2342345,
                'logs': ['tasks/5678/12345678/root.log',
                         'tasks/5678/12345678/state.log',
                         'tasks/5678/12345678/build.log'],
                'srpm': 'tasks/5678/12345678/some_package-1.2.3p5-25.src.rpm'
            }],

            ['1591234', {
                'brootid': 1231234,
                'logs': ['tasks/6789/2345678/root.log',
                         'tasks/6789/2345678/state.log',
                         'tasks/6789/2345678/build.log'],
                'rpms': ['tasks/6789/2345678/some_other_package-doc-1.2.3p5-25.el7.noarch.rpm'],
                'srpms': ['tasks/6789/2345678/some_other_package-1.2.3p5-25.el7.src.rpm']
            }]
        ]

        obj.session.host.taskWaitResults.return_value = taskWaitResults
        self.assertEquals(obj.wait([1551234, 1591234]), dict(taskWaitResults))
        obj.session.host.taskSetWait.assert_called_once_with(12345678, [1551234, 1591234])
        obj.session.host.taskWaitResults.assert_called_once_with(12345678, [1551234, 1591234], canfail=None)

    def test_BaseTaskHandler_wait_some_not_done(self):
        """ Tests that the wait function returns the one finished subtask results of
        when the taskWait function returns one finished task and one unfinished
        """
        temp_path = get_tmp_dir_path('TestTask')
        obj = TestTask(12345678, 'some_method', ['random_arg'], None, None, temp_path)
        makedirs(temp_path)
        obj.session = Mock()
        obj.session.host.taskSetWait.return_value = None
        obj.session.host.taskWait.return_value = [[1551234], [1591234]]
        taskWaitResults = [
            ['1551234', {
                'brootid': 2342345,
                'logs': ['tasks/5678/12345678/root.log',
                         'tasks/5678/12345678/state.log',
                         'tasks/5678/12345678/build.log'],
                'srpm': 'tasks/5678/12345678/some_package-1.2.3p5-25.src.rpm'
            }]
        ]

        obj.session.host.taskWaitResults.return_value = taskWaitResults
        self.assertEquals(obj.wait([1551234, 1591234]), dict(taskWaitResults))
        obj.session.host.taskSetWait.assert_called_once_with(12345678, [1551234, 1591234])
        obj.session.host.taskWaitResults.assert_called_once_with(12345678, [1551234], canfail=None)

    @patch('signal.pause', return_value=None)
    def test_BaseTaskHandler_wait_some_not_done_all_set(self, mock_signal_pause):
        """ Tests that the wait function returns the two subtask results since the all kwarg is set to True.
        The taskWait function should first return one finished and one unfinished task, then the second time it should
        return two finished tasks.
        """
        temp_path = get_tmp_dir_path('TestTask')
        obj = TestTask(12345678, 'some_method', ['random_arg'], None, None, temp_path)
        makedirs(temp_path)
        obj.session = Mock()
        obj.session.host.taskSetWait.return_value = None
        obj.session.host.taskWait.side_effect = [[[1551234], [1591234]], [[1551234, 1591234], []]]
        taskWaitResults = [
            ['1551234', {
                'brootid': 2342345,
                'logs': ['tasks/5678/12345678/root.log',
                         'tasks/5678/12345678/state.log',
                         'tasks/5678/12345678/build.log'],
                'srpm': 'tasks/5678/12345678/some_package-1.2.3p5-25.src.rpm'
            }],

            ['1591234', {
                'brootid': 1231234,
                'logs': ['tasks/6789/2345678/root.log',
                         'tasks/6789/2345678/state.log',
                         'tasks/6789/2345678/build.log'],
                'rpms': ['tasks/6789/2345678/some_other_package-doc-1.2.3p5-25.el7.noarch.rpm'],
                'srpms': ['tasks/6789/2345678/some_other_package-1.2.3p5-25.el7.src.rpm']
            }]
        ]

        obj.session.getTaskResult.side_effect

        obj.session.host.taskWaitResults.return_value = taskWaitResults
        self.assertEquals(obj.wait([1551234, 1591234], all=True), dict(taskWaitResults))
        obj.session.host.taskSetWait.assert_called_once_with(12345678, [1551234, 1591234])
        obj.session.host.taskWait.assert_has_calls([call(12345678), call(12345678)])
        mock_signal_pause.assert_called_once_with()
        obj.session.host.taskWaitResults.assert_called_once_with(12345678, [1551234, 1591234], canfail=None)

    def test_BaseTaskHandler_wait_some_not_done_all_set_failany_set_failed_task(self):
        """ Tests that the wait function raises an exception when one of the subtask fails when the failany flag is set
        to True.
        """
        temp_path = get_tmp_dir_path('TestTask')
        obj = TestTask(12345678, 'some_method', ['random_arg'], None, None, temp_path)
        makedirs(temp_path)
        obj.session = Mock()
        obj.session.host.taskSetWait.return_value = None
        obj.session.host.taskWait.side_effect = [[[1551234], [1591234]], [[1551234, 1591234], []]]
        obj.session.getTaskResult.side_effect = koji.GenericError('Uh oh, we\'ve got a problem here!')
        try:
            obj.wait([1551234, 1591234], all=True, failany=True)
            raise Exception('A GeneralError was not raised.')
        except koji.GenericError as e:
            self.assertEquals(e.args[0], 'Uh oh, we\'ve got a problem here!')
            obj.session.host.taskSetWait.assert_called_once_with(12345678, [1551234, 1591234])

    @patch('time.time')
    @patch('time.sleep')
    @patch('signal.pause')
    def test_BaseTaskHandler_wait_timeout(self, pause, sleep, time):
        """Tests timeout behavior in the wait function"""
        temp_path = get_tmp_dir_path('TestTask')
        obj = TestTask(95, 'some_method', ['random_arg'], None, None, temp_path)
        makedirs(temp_path)
        obj.session = MagicMock()
        obj.session.host.taskWait.return_value = [[], [99, 100, 101]]
        time.side_effect = list(range(0, 4000, 60))
        try:
            obj.wait([99, 100, 101], timeout=3600)
            raise Exception('A GenericError was not raised.')
        except koji.GenericError as e:
            self.assertEquals(e.args[0][:24], 'Subtasks timed out after')
        obj.session.host.taskSetWait.assert_called_once_with(95, [99, 100, 101])
        obj.session.cancelTaskChildren.assert_called_once_with(95)
        obj.session.getTaskResult.assert_not_called()
        pause.assert_not_called()

    @patch('time.time')
    @patch('time.sleep')
    @patch('signal.pause')
    def test_BaseTaskHandler_wait_avoid_timeout(self, pause, sleep, time):
        """Tests that timeout does not happen if tasks finish in time"""
        temp_path = get_tmp_dir_path('TestTask')
        obj = TestTask(95, 'some_method', ['random_arg'], None, None, temp_path)
        makedirs(temp_path)
        obj.session = MagicMock()
        time.side_effect = list(range(0, 4000, 20))
        # time ticks every 20s for a little over an "hour"
        # code checks time 3x each cycle (twice directly, once via logging)
        # so each cycle is a "minute"
        # report all unfinished for most of an hour
        taskWait_returns = [[[], [99, 100, 101]]] * 50
        # and then report all done
        taskWait_returns.append([[99, 100, 101], []])
        obj.session.host.taskWait.side_effect = taskWait_returns
        obj.wait([99, 100, 101], timeout=3600)

        obj.session.host.taskSetWait.assert_called_once_with(95, [99, 100, 101])
        obj.session.cancelTaskChildren.assert_not_called()
        pause.assert_not_called()

    def test_BaseTaskHandler_getUploadDir(self):
        """ Tests that the getUploadDir function returns the appropriate path based on the id of the handler.
        """
        temp_path = get_tmp_dir_path('TestTask')
        obj = TestTask(123, 'some_method', ['random_arg'], None, None, temp_path)
        self.assertEquals(obj.getUploadDir(), 'tasks/123/123')

    # This patch removes the dependence on getUploadDir functioning
    @patch('{0}.TestTask.getUploadDir'.format(__name__), return_value='tasks/123/123')
    def test_BaseTaskHandler_uploadFile(self, mock_getUploadDir):
        """ Tests that the uploadFile function calls the uploadWrapper function on the session member variable
        with the correct input
        """
        temp_path = get_tmp_dir_path('TestTask')
        makedirs(temp_path)
        temp_file = path.join(temp_path, 'test.txt')
        with open(temp_file, 'w') as temp_file_handler:
            temp_file_handler.write('Test')

        obj = TestTask(123, 'some_method', ['random_arg'], None, None, temp_path)
        obj.session = Mock()
        self.assertEquals(obj.uploadFile(temp_file), None)
        obj.session.uploadWrapper.assert_called_once_with(temp_file, 'tasks/123/123', None, volume=None)

    # This patch removes the dependence on getUploadDir functioning
    @patch('{0}.TestTask.getUploadDir'.format(__name__), return_value='tasks/123/123')
    def test_BaseTaskHandler_uploadFile_no_content(self, mock_getUploadDir):
        """ Tests that the uploadFile function calls the uploadWrapper function on the session member variable
        without including empty files.
        """
        temp_path = get_tmp_dir_path('TestTask')
        makedirs(temp_path)

        temp_file = path.join(temp_path, 'test.txt')
        temp_file_handler = open(temp_file, 'w')
        temp_file_handler.close()

        obj = TestTask(123, 'some_method', ['random_arg'], None, None, temp_path)
        obj.session = Mock()
        self.assertEquals(obj.uploadFile(temp_file), None)
        self.assertEquals(obj.session.uploadWrapper.called, False)

    def test_BaseTaskHandler_uploadTree(self):
        """ Tests that the uploadTree function calls the uploadFile function with the correct parameters.
        """
        temp_path = get_tmp_dir_path('TestTask')
        makedirs(temp_path)

        dummy_dir = path.join(temp_path, 'some_directory')
        makedirs(dummy_dir)

        dummy_file = path.join(temp_path, 'test.txt')
        with open(dummy_file, 'w') as temp_file_handler:
            temp_file_handler.write('Test')

        dummy_file2 = path.join(dummy_dir, 'test2.txt')
        with open(dummy_file2, 'w') as temp_file_handler2:
            temp_file_handler2.write('Test2')

        obj = TestTask(123, 'some_method', ['random_arg'], None, None, temp_path)
        obj.uploadFile = Mock()
        obj.uploadFile.return_value = None
        self.assertEquals(obj.uploadTree(temp_path), None)
        obj.uploadFile.assert_has_calls([call(dummy_file, '', volume=None), call(dummy_file2, 'some_directory', volume=None)])

    @patch('os.lchown', return_value=None)
    def test_BaseTaskHandler_chownTree(self, mock_lchown):
        """ Tests that the chownTree functions as expected on dummy files created in a temp directory
        """
        temp_path = get_tmp_dir_path('TestTask')
        makedirs(temp_path)

        dummy_file = path.join(temp_path, 'test.txt')
        dummy_file_handler = open(dummy_file, 'w')
        dummy_file_handler.close()

        dummy_file2 = path.join(temp_path, 'test2.txt')
        dummy_file_handler2 = open(dummy_file2, 'w')
        dummy_file_handler2.close()

        obj = TestTask(123, 'some_method', ['random_arg'], None, None, temp_path)
        self.assertEquals(obj.chownTree(temp_path, 2, 0), None)
        mock_lchown.assert_has_calls([call(temp_path, 2, 0), call(dummy_file2, 2, 0), call(dummy_file, 2, 0)], any_order=True)

    def test_BaseTaskHandler_localPath_file_exists(self):
        """ Tests the localPath function to ensure that when a file exists, it returns that path without
        trying to download it.
        """
        temp_path = get_tmp_dir_path('TestTask')
        makedirs(temp_path)

        local_folder = path.join(temp_path, 'local')
        makedirs(local_folder)

        dummy_file = path.join(local_folder, 'test.txt')
        dummy_file_handler = open(dummy_file, 'w')
        dummy_file_handler.close()
        options = Mock()
        options.topurl = 'https://www.domain.local'
        obj = TestTask(123, 'some_method', ['random_arg'], None, options, temp_path)
        self.assertEquals(obj.localPath('test.txt'), dummy_file)

    @requests_mock.Mocker()
    def test_BaseTaskHandler_localPath_no_file(self, m_requests):
        """
        """
        temp_path = get_tmp_dir_path('TestTask')
        makedirs(temp_path)

        local_folder = path.join(temp_path, 'local')
        makedirs(local_folder)

        target_file_path = path.join(local_folder, 'test.txt')

        options = Mock()
        options.topurl = 'https://www.domain.local'
        url = options.topurl + '/test.txt'
        m_requests.register_uri('GET', url, text='Important things\nSome more important things\n')
        obj = TestTask(123, 'some_method', ['random_arg'], None, options, temp_path)

        self.assertEquals(obj.localPath('test.txt'), target_file_path)
        self.assertEquals(m_requests.call_count, 1)
        self.assertEquals(m_requests.request_history[0].url, url)

    def test_BaseTaskHandler_localPath_no_topurl(self):
        """ Tests that the localPath function returns a path when options.topurl is not defined.
        """
        temp_path = get_tmp_dir_path('TestTask')
        makedirs(temp_path)

        options = Mock()
        options.topurl = None
        options.topdir = get_temp_dir_root()
        obj = TestTask(123, 'some_method', ['random_arg'], None, options, temp_path)

        self.assertEquals(obj.localPath('test.txt'), path.join(get_temp_dir_root(), 'test.txt'))

    def test_BaseTaskHandler_find_arch(self):
        """ Tests that the find_arch function returns the input for arch when the input is not "noarch".
        """
        temp_path = get_tmp_dir_path('TestTask')
        makedirs(temp_path)
        obj = TestTask(123, 'some_method', ['random_arg'], None, None, temp_path)
        self.assertEquals(obj.find_arch('x86_64', None, None), 'x86_64')

    def test_BaseTaskHandler_find_arch_noarch_bad_host(self):
        """ Tests that the find_arch function raises an exception when the host parameter doesn't contain a
        value for the arches key.
        """
        temp_path = get_tmp_dir_path('TestTask')
        makedirs(temp_path)
        host = {'arches': None, 'name': 'test.domain.local'}
        obj = TestTask(123, 'some_method', ['random_arg'], None, None, temp_path)
        try:
            obj.find_arch('noarch', host, None)
            raise Exception('The BuildError Exception was not raised')
        except koji.BuildError as e:
            self.assertEquals(e.args[0], 'No arch list for this host: test.domain.local')

    def test_BaseTaskHandler_find_arch_noarch_bad_tag(self):
        """ Tests that the find_arch function raises an exception when the tag parameter doesn't contain a
        value for the arches key.
        """
        temp_path = get_tmp_dir_path('TestTask')
        makedirs(temp_path)
        host = {'arches': 'x86_64', 'name': 'test.domain.local'}
        tag = {'arches': None, 'name': 'some_package-1.2-build'}
        obj = TestTask(123, 'some_method', ['random_arg'], None, None, temp_path)
        try:
            obj.find_arch('noarch', host, tag)
            raise Exception('The BuildError Exception was not raised')
        except koji.BuildError as e:
            self.assertEquals(e.args[0], 'No arch list for tag: some_package-1.2-build')

    def test_BaseTaskHandler_find_arch_noarch(self):
        """ Tests that the find_arch function finds a match of x86_64 when the host only supports x86_64
        and the tag supports x86_64 and aarch64.
        """
        temp_path = get_tmp_dir_path('TestTask')
        makedirs(temp_path)
        host = {'arches': 'x86_64', 'name': 'test.domain.local'}
        tag = {'arches': 'x86_64 aarch64', 'name': 'some_package-1.2-build'}
        obj = TestTask(123, 'some_method', ['random_arg'], None, None, temp_path)
        self.assertEquals(obj.find_arch('noarch', host, tag), 'x86_64')

    def test_BaseTaskHandler_find_arch__noarch_no_match(self):
        """ Tests that the find_arch function raises an exception when there isn't a common arch supported between
        the host and the tag.
        """
        temp_path = get_tmp_dir_path('TestTask')
        makedirs(temp_path)
        host = {'arches': 'i386', 'name': 'test.domain.local'}
        tag = {'arches': 'x86_64 aarch64', 'name': 'some_package-1.2-build'}
        obj = TestTask(123, 'some_method', ['random_arg'], None, None, temp_path)
        try:
            obj.find_arch('noarch', host, tag)
            raise Exception('The BuildError Exception was not raised')
        except koji.BuildError as e:
            self.assertEquals(e.args[0], ('host test.domain.local (i386) does not support '
                                          'any arches of tag some_package-1.2-build (aarch64, x86_64)'))

    def test_getRepo_tied_to_session(self):
        """ Tests that the getRepo function calls session.getRepo(), and returns the result when successful
        """
        temp_path = get_tmp_dir_path('TestTask')
        makedirs(temp_path)

        repo_dict = {
            'create_event': 13635166,
            'create_ts': 1469039671.5743899,
            'creation_time': '2016-07-20 18:34:31.574386',
            'id': 1630631,
            'state': 1
        }

        obj = TestTask(123, 'some_method', ['random_arg'], None, None, temp_path)
        obj.session = Mock()
        obj.session.getRepo.return_value = repo_dict

        self.assertEquals(obj.getRepo(8472), repo_dict)

    @patch('{0}.TestTask.wait'.format(__name__))
    def test_getRepo_not_tied_to_session(self, mock_wait):
        """ Tests that the getRepo function waits until the results are available for session.getRepo, when it is
        not available at the start of the function call.
        """
        temp_path = get_tmp_dir_path('TestTask')
        makedirs(temp_path)

        repo_dict = {
            'create_event': 13413120,
            'create_ts': 1466140834.9119599,
            'creation_time': '2016-06-17 05:20:34.911962',
            'id': 1592850,
            'state': 1
         }

        obj = TestTask(123, 'some_method', ['random_arg'], None, None, temp_path)
        obj.session = Mock()
        obj.session.getRepo.return_value = None
        obj.session.getTag.return_value = {
            'arches': 'i386 ia64 x86_64 ppc s390 s390x ppc64',
            'extra': {},
            'id': 851,
            'locked': True,
            'maven_include_all': False,
            'maven_support': False,
            'name': 'dist-3.0E-build',
            'perm': None,
            'perm_id': None
        }
        obj.session.getBuildTargets.return_value = [{
            'build_tag': 3093,
            'build_tag_name': 'dist-6E-dsrv-9-build',
            'dest_tag': 3092,
            'dest_tag_name': 'dist-6E-dsrv-9-qu-candidate',
            'id': 851,
            'name': 'dist-6E-dsrv-9-qu-candidate'
         }]

        obj.session.host.subtask.return_value = 123
        mock_wait.return_value = {123: repo_dict}

        self.assertEquals(obj.getRepo(851), repo_dict)
        obj.session.getRepo.assert_called_once_with(851)
        obj.session.getTag.assert_called_once_with(851, strict=True)

    @patch('{0}.TestTask.wait'.format(__name__))
    def test_getRepo_not_tied_to_session_no_build_targets(self, mock_wait):
        """ Tests that the getRepo function raises an exception when session.getBuildTargets returns an empty list
        """
        temp_path = get_tmp_dir_path('TestTask')
        makedirs(temp_path)

        obj = TestTask(123, 'some_method', ['random_arg'], None, None, temp_path)
        obj.session = Mock()
        obj.session.getRepo.return_value = None
        obj.session.getTag.return_value = {
            'arches': 'i686 x86_64 ppc ppc64 ppc64le s390 s390x aarch64',
            'extra': {},
            'id': 8472,
            'locked': False,
            'maven_include_all': False,
            'maven_support': False,
            'name': 'rhel-7.3-build',
            'perm': 'admin',
            'perm_id': 1
        }
        obj.session.getBuildTargets.return_value = []

        try:
            obj.getRepo(8472)
            raise Exception('The BuildError Exception was not raised')
        except koji.BuildError as e:
            obj.session.getRepo.assert_called_once_with(8472)
            self.assertEquals(e.args[0], 'no repo (and no target) for tag rhel-7.3-build')

    def test_FakeTask_handler(self):
        """ Tests that the FakeTest handler can be instantiated and returns 42 when run
        """
        obj = FakeTask(123, 'someMethod', ['random_arg'], None, None, (get_tmp_dir_path('FakeTask')))
        self.assertEquals(obj.run(), 42)

    @patch('time.sleep')
    def test_SleepTask_handler(self, mock_sleep):
        """ Tests that the SleepTask handler can be instantiated and runs appropriately based on the input
        """
        obj = SleepTask(123, 'sleep', [5], None, None, (get_tmp_dir_path('SleepTask')))
        obj.run()
        mock_sleep.assert_called_once_with(5)

    @patch('os.spawnvp')
    def test_ForkTask_handler(self, mock_spawnvp):
        """ Tests that the ForkTask handler can be instantiated and runs appropriately based on the input
        """
        obj = ForkTask(123, 'fork', [1, 20], None, None, (get_tmp_dir_path('ForkTask')))
        obj.run()
        mock_spawnvp.assert_called_once_with(1, 'sleep', ['sleep', '20'])

    @patch('signal.pause', return_value=None)
    @patch('time.sleep')
    def test_WaitTestTask_handler(self, mock_sleep, mock_signal_pause):
        """ Tests that the WaitTestTask handler can be instantiated and runs appropriately based on the input
            Specifically, that forking works and canfail behaves correctly.
        """
        self.mock_subtask_id = 1
        def mock_subtask(method, arglist, id, **opts):
            self.assertEqual(method, 'sleep')
            task_id = self.mock_subtask_id
            self.mock_subtask_id += 1
            obj = SleepTask(task_id, 'sleep', arglist, None, None, (get_tmp_dir_path('SleepTask')))
            obj.run()
            return task_id

        mock_taskWait = [
            [[], [1, 2, 3, 4]],
            [[3, 4], [1, 2]],
            [[1, 2, 3, 4], []],
        ]
        def mock_getTaskResult(task_id):
            if task_id == 4:
                raise koji.GenericError()


        obj = WaitTestTask(123, 'waittest', [3], None, None, (get_tmp_dir_path('WaitTestTask')))
        obj.session = Mock()
        obj.session.host.subtask.side_effect = mock_subtask
        obj.session.getTaskResult.side_effect = mock_getTaskResult
        obj.session.host.taskWait.side_effect = mock_taskWait
        obj.session.host.taskWaitResults.return_value = [ ['1', {}], ['2', {}], ['3', {}], ['4', {}], ]
        obj.run()
        #self.assertEqual(mock_sleep.call_count, 4)
        obj.session.host.taskSetWait.assert_called_once()
        obj.session.host.taskWait.assert_has_calls([call(123), call(123), call(123)])
        # getTaskResult should be called in 2nd round only for task 3, as 4
        # will be skipped as 'canfail'
        obj.session.getTaskResult.assert_has_calls([call(3)])

class TestSafeRmtree(unittest.TestCase):
    @patch('os.path.exists', return_value=True)
    @patch('os.path.isfile', return_value=True)
    @patch('os.path.islink', return_value=False)
    @patch('os.remove')
    @patch('koji.util.rmtree')
    def test_safe_rmtree_file(self, rmtree, remove, islink, isfile, exists):
        """ Tests that the koji.util.rmtree function returns nothing when the path parameter is a file.
        """
        path = '/mnt/folder/some_file'
        self.assertEquals(safe_rmtree(path, False, True), 0)
        isfile.assert_called_once_with(path)
        islink.assert_not_called()
        exists.assert_not_called()
        remove.assert_called_once_with(path)
        rmtree.assert_not_called()

    @patch('os.path.exists', return_value=True)
    @patch('os.path.isfile', return_value=False)
    @patch('os.path.islink', return_value=True)
    @patch('os.remove')
    @patch('koji.util.rmtree')
    def test_rmtree_link(self, rmtree, remove, islink, isfile, exists):
        """ Tests that the koji.util.rmtree function returns nothing when the path parameter is a link.
        """
        path = '/mnt/folder/some_link'
        self.assertEquals(safe_rmtree(path, False, True), 0)
        isfile.assert_called_once_with(path)
        islink.assert_called_once_with(path)
        exists.assert_not_called()
        remove.assert_called_once_with(path)
        rmtree.assert_not_called()


    @patch('os.path.exists', return_value=False)
    @patch('os.path.isfile', return_value=False)
    @patch('os.path.islink', return_value=False)
    @patch('os.remove')
    @patch('koji.util.rmtree')
    def test_rmtree_does_not_exist(self, rmtree, remove, islink, isfile, exists):
        """ Tests that the koji.util.rmtree function returns nothing if the path does not exist.
        """
        path = '/mnt/folder/some_file'
        self.assertEquals(safe_rmtree(path, False, True), 0)
        isfile.assert_called_once_with(path)
        islink.assert_called_once_with(path)
        exists.assert_called_once_with(path)
        remove.assert_not_called()
        rmtree.assert_not_called()

    @patch('os.path.exists', return_value=True)
    @patch('os.path.isfile', return_value=False)
    @patch('os.path.islink', return_value=False)
    @patch('os.remove')
    @patch('koji.util.rmtree')
    def test_rmtree_directory(self, rmtree, remove, islink, isfile, exists):
        """ Tests that the koji.util.rmtree function returns nothing when the path is a directory.
        """
        path = '/mnt/folder'
        self.assertEquals(safe_rmtree(path, False, True), 0)
        isfile.assert_called_once_with(path)
        islink.assert_called_once_with(path)
        exists.assert_called_once_with(path)
        remove.assert_not_called()
        rmtree.assert_called_once_with(path)

    @patch('os.path.exists', return_value=True)
    @patch('os.path.isfile', return_value=False)
    @patch('os.path.islink', return_value=False)
    @patch('os.remove')
    @patch('koji.util.rmtree')
    def test_rmtree_directory_scrub_file_failure(self, rmtree, remove, islink, isfile, exists):
        """ Tests that the koji.util.rmtree function returns a GeneralException when the path parameter is a directory
        and the scrub of the files in the directory fails.
        """
        rmtree.side_effect = koji.GenericError('xyz')
        path = '/mnt/folder'
        try:
            safe_rmtree(path, False, 1)
            raise Exception('A GenericError was not raised during the test')
        except koji.GenericError as e:
            self.assertEquals(e.args[0], 'xyz')
        isfile.assert_called_once_with(path)
        islink.assert_called_once_with(path)
        exists.assert_called_once_with(path)
        remove.assert_not_called()
        rmtree.assert_called_once_with(path)

    @patch('os.path.exists', return_value=True)
    @patch('os.path.isfile', return_value=False)
    @patch('os.path.islink', return_value=False)
    @patch('os.remove')
    @patch('koji.util.rmtree')
    def test_safe_rmtree_directory_scrub_directory_failure(self, rmtree, remove, islink, isfile, exists):
        """ Tests that the koji.util.rmtree function returns a GeneralException when the path parameter is a directory
        and the scrub of the directories in the directory fails.
        """
        rmtree.side_effect = OSError('xyz')
        path = '/mnt/folder'
        try:
            safe_rmtree(path, False, True)
            raise Exception('An OSError was not raised during the test')
        except OSError as e:
            self.assertEquals(e.args[0], 'xyz')

        isfile.assert_called_once_with(path)
        islink.assert_called_once_with(path)
        exists.assert_called_once_with(path)
        remove.assert_not_called()
        rmtree.assert_called_once_with(path)
