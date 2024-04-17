import mock
import unittest

import koji
from .loadwebindex import webidx


class TestFileInfo(unittest.TestCase):
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
        self.filename = 'testfilename'
        self.rpm_id = '11'
        self.archive_id = '111'

    def tearDown(self):
        mock.patch.stopall()

    def test_fileinfo_exception_rpm(self):
        """Test fileinfo function raises exception"""
        self.server.getRPM.return_value = None
        self.get_server.return_value = self.server

        with self.assertRaises(koji.GenericError) as cm:
            webidx.fileinfo(self.environ, self.filename, rpmID=self.rpm_id)
        self.assertEqual(
            str(cm.exception), f'No such RPM ID: {self.rpm_id}')
        self.server.getRPM.assert_called_once_with(int(self.rpm_id))
        self.server.getRPMFile.assert_not_called()
        self.server.getArchive.assert_not_called()
        self.server.getArchiveFile.assert_not_called()

    def test_fileinfo_exception_archive(self):
        """Test fileinfo function raises exception"""
        self.server.getArchive.return_value = None
        self.get_server.return_value = self.server

        with self.assertRaises(koji.GenericError) as cm:
            webidx.fileinfo(self.environ, self.filename, archiveID=self.archive_id)
        self.assertEqual(
            str(cm.exception), f'No such archive ID: {self.archive_id}')
        self.server.getRPM.assert_not_called()
        self.server.getRPMFile.assert_not_called()
        self.server.getArchive.assert_called_once_with(int(self.archive_id))
        self.server.getArchiveFile.assert_not_called()

    def test_fileinfo_exception_rpm_file(self):
        """Test fileinfo function raises exception"""
        self.server.getRPMFile.return_value = None
        self.server.getRPM.return_value = {'id': self.rpm_id}
        self.get_server.return_value = self.server

        with self.assertRaises(koji.GenericError) as cm:
            webidx.fileinfo(self.environ, self.filename, rpmID=self.rpm_id)
        self.assertEqual(str(cm.exception), f'no file {self.filename} in RPM {self.rpm_id}')
        self.server.getRPM.assert_called_once_with(int(self.rpm_id))
        self.server.getRPMFile.assert_called_once_with(self.rpm_id, self.filename)
        self.server.getArchive.assert_not_called()
        self.server.getArchiveFile.assert_not_called()

    def test_fileinfo_exception_archive_file(self):
        """Test fileinfo function raises exception"""
        self.server.getArchiveFile.return_value = None
        self.server.getArchive.return_value = {'id': self.archive_id}
        self.get_server.return_value = self.server

        with self.assertRaises(koji.GenericError) as cm:
            webidx.fileinfo(self.environ, self.filename, archiveID=self.archive_id)
        self.assertEqual(str(cm.exception),
                         f'no file {self.filename} in archive {self.archive_id}')
        self.server.getRPM.assert_not_called()
        self.server.getRPMFile.assert_not_called()
        self.server.getArchive.assert_called_once_with(int(self.archive_id))
        self.server.getArchiveFile.assert_called_once_with(self.archive_id, self.filename)

    def test_fileinfo_exception(self):
        """Test fileinfo function raises exception"""
        self.get_server.return_value = self.server

        with self.assertRaises(koji.GenericError) as cm:
            webidx.fileinfo(self.environ, self.filename)
        self.assertEqual(str(cm.exception), 'either rpmID or archiveID must be specified')
        self.server.getRPM.assert_not_called()
        self.server.getRPMFile.assert_not_called()
        self.server.getArchive.assert_not_called()
        self.server.getArchiveFile.assert_not_called()

    def test_fileinfo_archive_file_valid(self):
        """Test fileinfo function valid"""
        self.server.getArchiveFile.return_value = {'name': self.filename}
        self.server.getArchive.return_value = {'id': self.archive_id}
        self.get_server.return_value = self.server

        webidx.fileinfo(self.environ, self.filename, archiveID=self.archive_id)
        self.server.getRPM.assert_not_called()
        self.server.getRPMFile.assert_not_called()
        self.server.getArchive.assert_called_once_with(int(self.archive_id))
        self.server.getArchiveFile.assert_called_once_with(self.archive_id, self.filename)

    def test_fileinfo_rpm_file_valid(self):
        """Test fileinfo function valid"""
        self.server.getRPMFile.return_value = {'name': f'{self.filename}.rpm'}
        self.server.getRPM.return_value = {'id': self.rpm_id}
        self.get_server.return_value = self.server

        webidx.fileinfo(self.environ, self.filename, rpmID=self.rpm_id)
        self.server.getRPM.assert_called_once_with(int(self.rpm_id))
        self.server.getRPMFile.assert_called_once_with(self.rpm_id, self.filename)
        self.server.getArchive.assert_not_called()
        self.server.getArchiveFile.assert_not_called()
