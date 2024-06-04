import mock
import unittest

from .loadwebindex import webidx


class TestArchiveInfo(unittest.TestCase):
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
        self.archive_id = '5'

    def tearDown(self):
        mock.patch.stopall()

    def test_archiveinfo(self):
        """Test archiveinfo function"""
        self.server.getArchive.return_value = {'type_id': 6, 'build_id': 1, 'buildroot_id': 444,
                                               'id': int(self.archive_id),
                                               'filename': 'test-filename'}
        self.server.getArchiveType.return_value = 'arch-type'
        self.server.getBuild.return_value = {'id': 1, 'name': 'test-build'}
        self.server.getBuildroot.return_value = {'id': 444}
        self.server.listRPMs.return_value = [{'id': 123}, {'id': 124}]
        self.server.listArchives.return_value = [{'id': 457}, {'id': 458}]

        self.get_server.return_value = self.server

        webidx.archiveinfo(self.environ, self.archive_id)
        self.server.getArchive.assert_called_once_with(int(self.archive_id))
        self.server.getArchiveType.assert_called_once_with(type_id=6)
        self.server.getBuild.assert_called_once_with(1)
        self.server.getBuildroot.assert_called_once_with(444)
        self.server.listRPMs.assert_called_once_with(
            imageID=int(self.archive_id), queryOpts={'limit': 1})
        self.server.listArchives.assert_called_once_with(
            imageID=int(self.archive_id), queryOpts={'limit': 1})
