import mock
import copy
import datetime
import unittest

from mock import call

import koji
from .loadwebindex import webidx


class TestTaskInfo(unittest.TestCase):
    def setUp(self):
        self.get_server = mock.patch.object(webidx, "_getServer").start()
        self.task_label = mock.patch('koji.taskLabel').start()
        self.gen_html = mock.patch.object(webidx, '_genHTML').start()

        self.environ = {
            'koji.options': {
                'SiteName': 'test',
                'KojiFilesURL': 'https://server.local/files',
            },
            'koji.currentUser': None
        }

        self.task_id = 1001
        self.task = {
            'id': self.task_id,
            'state': 2,
            'parent': 1000,
            'start_ts': 1234567.89012,
            'create_ts': 1234567.89012,
            'completion_ts': 1234567.89012,
            'request': [
                'cli-build/1234567.89012.zWxRvT/less-487-3.fc26.src.rpm',
                2,
                'x86_64',
                True,
                {'repo_id': 2}
            ],
            'arch': 'x86_64',
            'method': 'buildArch',
            'channel_id': 1,
            'host_id': 2,
            'owner': 3,
        }

        self.parent_task = copy.copy(self.task)
        self.parent_task['id'] = 1000
        self.parent_task['parent'] = None

    def __get_server(self, task=None):
        server = mock.MagicMock()
        server.getTaskInfo.side_effect = [
            task if task else self.task,
            self.parent_task
        ]

        server.getTaskDescendents.return_value = {
            str(self.task_id): []
        }

        server.getChannel.return_value = {
            'name': 'TestChannel'
        }

        server.getHost.return_value = {
            'name': 'TestHost'
        }

        server.getUser.return_value = {
            'name': 'Tester'
        }

        server.getUserPerms.return_value = ['admin']

        server.listBuilds.return_value = [
            {
                "package_name": "less",
                "extra": "None",
                "package_id": 2,
                "build_id": 2,
                "state": 1,
                "source": "None",
                "epoch": "None",
                "version": "487",
                "owner_id": 1,
                "nvr": "less-487-3.fc26",
                "volume_id": 0,
                "name": "less",
                "task_id": self.task_id,
                "volume_name": "DEFAULT",
                "release": "3.fc26",
                "creation_ts": 1234567.89012
            },
        ]

        server.listBuildroots.return_value = {
            "arch": "x86_64",
            "host_name": "builder",
            "task_id": self.task_id,
            "id": 1
        }

        server.getTag.return_value = {
            "id": 2,
            "arches": "x86_64",
            "name": "fedora-build",
            "extra": {},
            "perm": None
        }

        server.getTaskResult.return_value = {
            "brootid": 1,
            "srpms": [
                "tasks/8/8/less-487-3.fc26.src.rpm"
            ],
            "rpms": [
                "tasks/8/8/less-487-3.fc26.x86_64.rpm",
                "tasks/8/8/less-debuginfo-487-3.fc26.x86_64.rpm"
            ],
            "logs": [
                "tasks/8/8/hw_info.log",
                "tasks/8/8/state.log",
                "tasks/8/8/build.log",
                "tasks/8/8/root.log",
                "tasks/8/8/installed_pkgs.log",
                "tasks/8/8/mock_output.log"
            ]
        }

        server.listTaskOutput.return_value = {
            "root.log": ["DEFAULT"],
            "hw_info.log": ["DEFAULT"],
            "less-debuginfo-487-3.fc26.x86_64.rpm": ["DEFAULT"],
            "build.log": ["DEFAULT"],
            "less-487-3.fc26.src.rpm": ["DEFAULT"],
            "state.log": ["DEFAULT"],
            "mock_output.log": ["DEFAULT"],
            "less-487-3.fc26.x86_64.rpm": ["DEFAULT"],
            "installed_pkgs.log": ["DEFAULT"]
        }
        return server

    def tearDown(self):
        mock.patch.stopall()

    def test_taskinfo_exception(self):
        """Test taskinfo function raises exception"""
        server = mock.MagicMock()
        server.getTaskInfo.return_value = None

        self.get_server.return_value = server

        with self.assertRaises(koji.GenericError) as cm:
            webidx.taskinfo(self.environ, self.task_id)
        self.assertEqual(
            str(cm.exception), 'invalid task ID: %s' % self.task_id)

    def test_taskinfo_getTaskResult_exception(self):
        """Test taskinfo function with exception raised from getTaskResult"""
        server = self.__get_server()
        err = koji.GenericError('a fake error raised from getTaskResult')
        server.getTaskResult.side_effect = err
        self.get_server.return_value = server

        webidx.taskinfo(self.environ, self.task_id)
        self.assertEqual(self.environ['koji.values']['result'], err)
        self.assertEqual(self.environ['koji.values']['excClass'], err.__class__)

    def test_taskinf_other_task_state(self):
        """Test taskinfo function with different task states"""
        for s in (0, 1, 3, 4):      # FREE, OPEN, CANCLED, ASSIGNED states
            server = self.__get_server()
            self.get_server.return_value = server
            self.task['state'] = s

            webidx.taskinfo(self.environ, self.task_id)
            self.assertEqual(self.environ['koji.values']['result'], None)
            self.assertEqual(self.environ['koji.values']['excClass'], None)

    def test_taskinfo_common_setter_check(self):
        """Test taskinfo function setter behavior"""
        currentUid = 123
        environ = copy.deepcopy(self.environ)
        environ.update({'koji.currentUser': {'id': currentUid}})

        # channel, host, owner
        channel, host, owner = 111, 222, 333
        task = copy.deepcopy(self.task)
        task.update({'channel_id': channel,
                     'host_id': host,
                     'owner': owner})

        server = self.__get_server(task)

        # set build time stamp and state = 0
        ts, delta = 1234567.89012, 9999
        server.listBuilds.return_value[0].update({'creation_ts': ts, 'state': 0})
        server.getAverageBuildDuration.return_value = delta
        self.get_server.return_value = server

        webidx.taskinfo(environ, self.task_id)
        server.getChannel.assert_called_with(channel)
        server.getHost.assert_called_with(host)
        server.getUser.assert_called_with(owner)
        server.getUserPerms.assert_called_with(currentUid)
        server.getAverageBuildDuration.assert_called_once()
        estTime = datetime.datetime.fromtimestamp(ts + delta)
        self.assertEqual(
            environ['koji.values']['estCompletion'], estTime)

    def test_taskinfo_no_common_setter(self):
        """Test taskinfo function setter are not invoked cases"""
        environ = copy.deepcopy(self.environ)
        environ.update({'koji.currentUser': None})

        # channel, host, owner
        task = copy.deepcopy(self.task)
        task.update({'parent': None,
                     'channel_id': None,
                     'host_id': None,
                     'owner': None})

        server = self.__get_server(task)
        server.listBuilds.return_value = []
        self.get_server.return_value = server

        webidx.taskinfo(environ, self.task_id)
        server.getChannel.assert_not_called()
        server.getHost.assert_not_called()
        server.getUser.assert_not_called()
        server.getUserPerms.assert_not_called()

    def test_taskinfo_method_setter_check(self):
        """Test taskinfo function setter on different methods"""
        # case 1. buildArch
        task = copy.deepcopy(self.task)
        task.update({'method': 'buildArch'})
        server = self.__get_server(task)
        self.get_server.return_value = server
        webidx.taskinfo(self.environ, self.task_id)
        server.getTag.assert_called_with(2, strict=True)

        # case 2. buildMaven
        task = copy.deepcopy(self.task)
        task.update({'method': 'buildMaven'})
        task.update({'request': ['arg1', 'testBuildMaven']})
        server = self.__get_server(task)
        self.get_server.return_value = server
        webidx.taskinfo(self.environ, self.task_id)
        server.getTag.assert_not_called()
        self.assertEqual(self.environ['koji.values']['buildTag'], 'testBuildMaven')

        # case 3. buildSRPMFromSCM
        task = copy.deepcopy(self.task)
        task.update({'method': 'buildSRPMFromSCM'})
        task.update({'request': ['arg1', 'testSRPM']})
        server = self.__get_server(task)
        self.get_server.return_value = server
        webidx.taskinfo(self.environ, self.task_id)
        server.getTag.assert_called_with('testSRPM', strict=True)

        # case 4. tagBuild
        task = copy.deepcopy(self.task)
        task.update({'method': 'tagBuild'})
        task.update({'request': ['testTag', 'testBuild']})
        server = self.__get_server(task)
        self.get_server.return_value = server
        webidx.taskinfo(self.environ, self.task_id)
        server.getTag.assert_called_with('testTag')
        server.getBuild.assert_called_with('testBuild')

        # case 5. newRepo, distRepo, createdstrepo
        for m in ('newRepo', 'distRepo', 'createdistrepo'):
            task = copy.deepcopy(self.task)
            task.update({'method': m})
            task.update({'request': ['RepoTag']})
            server = self.__get_server(task)
            self.get_server.return_value = server
            webidx.taskinfo(self.environ, self.task_id)
            server.getTag.assert_called_with('RepoTag')

        # case 6. tagNotification
        task = copy.deepcopy(self.task)
        task.update({'method': 'tagNotification'})
        task.update({'request': ['', '', 'destTag', 'srcTag', 'theBuild', 'user']})
        server = self.__get_server(task)
        self.get_server.return_value = server
        webidx.taskinfo(self.environ, self.task_id)
        server.getTag.assert_has_calls([call('destTag'), call('srcTag')])
        server.getBuild.assert_called_with('theBuild')
        server.getUser.assert_called_with('user')

        # case 7. dependentTask
        task = copy.deepcopy(self.task)
        task.update({'method': 'dependantTask'})
        task.update({'request': [[]]})
        server = self.__get_server(task)
        self.get_server.return_value = server
        webidx.taskinfo(self.environ, self.task_id)
        self.assertEqual(self.environ['koji.values']['deps'], [])

        # case 8. wrapperRPM
        task = copy.deepcopy(self.task)
        task.update({'method': 'wrapperRPM'})
        task.update({'request': ['', 'target', '', {'id': 999}]})
        server = self.__get_server(task)
        server.getTaskInfo.side_effect = [
            task,
            self.parent_task,
            'wrapTask'
        ]
        self.get_server.return_value = server
        webidx.taskinfo(self.environ, self.task_id)
        self.assertEqual(self.environ['koji.values']['wrapTask'], 'wrapTask')

        # case 7. restartVerify
        task = copy.deepcopy(self.task)
        task.update({'method': 'restartVerify'})
        task.update({'request': [[]]})
        server = self.__get_server(task)
        server.getTaskInfo.side_effect = [
            task,
            self.parent_task,
            'restartVerify'
        ]
        self.get_server.return_value = server
        webidx.taskinfo(self.environ, self.task_id)
        self.assertEqual(self.environ['koji.values']['rtask'], 'restartVerify')

    def test_taskinfo_sorting_compare(self):
        """Test taskinfo function sorting results"""
        expect_output = [
            ('DEFAULT', 'build.log'),
            ('DEFAULT', 'hw_info.log'),
            ('DEFAULT', 'installed_pkgs.log'),
            ('DEFAULT', 'mock_output.log'),
            ('DEFAULT', 'root.log'),
            ('DEFAULT', 'state.log'),
            ('DEFAULT', 'less-487-3.fc26.src.rpm'),
            ('DEFAULT', 'less-487-3.fc26.x86_64.rpm'),
            ('DEFAULT', 'less-debuginfo-487-3.fc26.x86_64.rpm'),
        ]

        self.get_server.return_value = self.__get_server()
        self.task_label.return_value = "build (fedora, less-487-3.fc26.src.rpm) | Task Info"

        webidx.taskinfo(self.environ, self.task_id)
        # output should be eqaul including order
        for i, ele in enumerate(self.environ['koji.values']['output']):
            self.assertEqual(ele, expect_output[i])
