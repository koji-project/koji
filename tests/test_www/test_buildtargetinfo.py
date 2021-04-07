import mock
import unittest

import koji
from .loadwebindex import webidx


class TestBuildTargetInfo(unittest.TestCase):
    def setUp(self):
        self.get_server = mock.patch.object(webidx, "_getServer").start()
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
        """Test taskinfo function raises exception"""
        server = mock.MagicMock()
        server.getBuildTarget.return_value = None
        self.get_server.return_value = server

        with self.assertRaises(koji.GenericError) as cm:
            webidx.buildtargetinfo(self.environ, targetID=self.buildtarget_id)
        self.assertEqual(str(cm.exception), 'No such build target: %s' % self.buildtarget_id)

    def test_buildtargetinfo_exception_name(self):
        """Test taskinfo function raises exception"""
        server = mock.MagicMock()
        server.getBuildTarget.return_value = None
        self.get_server.return_value = server

        with self.assertRaises(koji.GenericError) as cm:
            webidx.buildtargetinfo(self.environ, name=self.buildtarget_name)
        self.assertEqual(str(cm.exception), 'No such build target: %s' % self.buildtarget_name)
