from __future__ import absolute_import
import unittest
from unittest import mock

import koji
from koji.server import ServerRedirect
from .loadwebindex import webidx


class TestBuildTargetDelete(unittest.TestCase):
    def setUp(self):
        self.get_server = mock.patch.object(webidx, "_getServer").start()
        self.assert_login = mock.patch.object(webidx, "_assertLogin").start()
        self.session = mock.MagicMock()
        self.environ = {
            'koji.options': {
                'SiteName': 'test',
                'KojiFilesURL': 'https://server.local/files',
            },
            'koji.currentUser': None,

        }

        def __get_server(env):
            env['koji.session'] = self.session
            return self.session

        self.get_server.side_effect = __get_server
        self.buildtarget_id = 1

    def tearDown(self):
        mock.patch.stopall()

    def test_buildtargetdelete_exception_from_api_call(self):
        """Test taskinfo function raises exception"""
        self.get_server.return_value = self.session
        self.session.getBuildTarget.return_value = None

        with self.assertRaises(koji.GenericError) as cm:
            webidx.buildtargetdelete(self.environ, self.buildtarget_id)
        self.session.deleteBuildTarget.assert_not_called()
        self.assertEqual(str(cm.exception), f'No such build target: {self.buildtarget_id}')

    def test_buildtargetdelete_normal_case(self):
        """Test taskinfo function"""
        self.get_server.return_value = self.session
        self.session.getBuildTarget.return_value = {'id': self.buildtarget_id}
        webidx._assertLogin.return_value = True

        with self.assertRaises(ServerRedirect):
            webidx.buildtargetdelete(self.environ, self.buildtarget_id)
        self.session.deleteBuildTarget.assert_called_with(self.buildtarget_id)
        self.assertEqual(self.environ['koji.redirect'], 'buildtargets')
