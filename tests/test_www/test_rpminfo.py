from unittest import mock
import unittest

import koji
from .loadwebindex import webidx


class TestRpmInfo(unittest.TestCase):
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
        self.rpm_id = '5'

    def tearDown(self):
        mock.patch.stopall()

    def test_rpminfo_exception(self):
        """Test taskinfo function raises exception"""
        self.server.getRPM.side_effect = koji.GenericError

        self.get_server.return_value = self.server

        with self.assertRaises(koji.GenericError) as cm:
            webidx.rpminfo(self.environ, self.rpm_id)
        self.assertEqual(str(cm.exception), f'No such RPM ID: {self.rpm_id}')
        self.server.getRPM.assert_called_once_with(int(self.rpm_id), strict=True)
        self.server.getBuild.assert_not_called()
        self.server.getBuildroot.assert_not_called()
        self.server.getRPMDeps.assert_not_called()
        self.server.getRPMHeaders.assert_not_called()

    def test_rpminfo_valid(self):
        """Test taskinfo function"""
        rpm_headers = ['summary', 'description', 'license', 'disturl', 'vcs']
        self.server.getRPM.return_value = {'id': int(self.rpm_id), 'build_id': 1,
                                           'buildroot_id': 444, 'name': 'test-name',
                                           'version': 123, 'release': 5, 'epoch': 2,
                                           'arch': 'test-arch', 'suffix': 'suf',
                                           'external_repo_id': 0}
        self.server.getBuild.return_value = {'id': 1, 'name': 'test-build'}
        self.server.getBuildroot.return_value = {'id': 444}
        self.server.getRPMDeps.return_value = [{'type': 'requires'}, {'type': 'suggests'}]
        self.server.getRPMHeaders.return_value = {'summary': 'test_summary',
                                                  'description': 'test-description',
                                                  'license': 'test-license',
                                                  'disturl': 'test-disturl',
                                                  'vcs': 'test-vcs'}

        self.get_server.return_value = self.server

        webidx.rpminfo(self.environ, self.rpm_id)
        self.server.getRPM.assert_called_once_with(int(self.rpm_id), strict=True)
        self.server.getBuild.assert_called_once_with(1)
        self.server.getBuildroot.assert_called_once_with(444)
        self.server.getRPMDeps.assert_called_once_with(int(self.rpm_id))
        self.server.getRPMHeaders.assert_called_once_with(int(self.rpm_id), headers=rpm_headers)
