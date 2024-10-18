from unittest import mock
import unittest

import koji
from .loadwebindex import webidx


class TestBuildTargetInfo(unittest.TestCase):
    def setUp(self):
        self.get_server = mock.patch.object(webidx, "_getServer").start()
        self.gen_html = mock.patch.object(webidx, '_genHTML').start()
        self.server = mock.MagicMock()
        self.environ = {
            'koji.options': {
                'SiteName': 'test',
                'KojiFilesURL': 'https://server.local/files',
            },
            'koji.currentUser': None
        }
        self.buildtarget_id = '1'
        self.buildtarget_name = 'test-name'

    def tearDown(self):
        mock.patch.stopall()

    def test_buildtargetinfo_exception_id(self):
        """Test buildtargetinfo function raises exception"""
        self.server.getBuildTarget.return_value = None
        self.get_server.return_value = self.server

        with self.assertRaises(koji.GenericError) as cm:
            webidx.buildtargetinfo(self.environ, targetID=self.buildtarget_id)
        self.assertEqual(str(cm.exception), f'No such build target: {self.buildtarget_id}')

    def test_buildtargetinfo_exception_name(self):
        """Test buildtargetinfo function raises exception"""
        self.server.getBuildTarget.return_value = None
        self.get_server.return_value = self.server

        with self.assertRaises(koji.GenericError) as cm:
            webidx.buildtargetinfo(self.environ, name=self.buildtarget_name)
        self.assertEqual(str(cm.exception), f'No such build target: {self.buildtarget_name}')

    def test_buildtargetinfo_without_current_user(self):
        """Test buildtargetinfo function valid without current user"""
        self.server.getBuildTarget.return_value = {'name': 'test-build-target',
                                                   'build_tag': 'test-build-tag',
                                                   'dest_tag': 'test-dest-tag'}
        self.server.getTag.side_effect = [{'id': 123, 'name': 'test-build-tag'},
                                          {'id': 234, 'name': 'test-dest-tag'}]
        self.get_server.return_value = self.server
        webidx.buildtargetinfo(self.environ, name=self.buildtarget_name)

    def test_buildtargetinfo_with_current_user(self):
        """Test buildtargetinfo function valid with current user"""
        environ = {
            'koji.options': {
                'SiteName': 'test',
                'KojiFilesURL': 'https://server.local/files',
            },
            'koji.currentUser': {'id': 5}
        }
        self.server.getBuildTarget.return_value = {'name': 'test-build-target',
                                                   'build_tag': 'test-build-tag',
                                                   'dest_tag': 'test-dest-tag'}
        self.server.getTag.side_effect = [{'id': 123, 'name': 'test-build-tag'},
                                          {'id': 234, 'name': 'test-dest-tag'}]
        self.server.getUserPerms.return_value = ['perm-1', 'perm-2']
        self.get_server.return_value = self.server
        webidx.buildtargetinfo(environ, name=self.buildtarget_name)
