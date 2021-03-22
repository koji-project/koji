import mock
import unittest

import koji
from .loadwebindex import webidx


class TestFileInfo(unittest.TestCase):
    def setUp(self):
        self.get_server = mock.patch.object(webidx, "_getServer").start()

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
        """Test taskinfo function raises exception"""
        server = mock.MagicMock()
        server.getRPM.return_value = None

        self.get_server.return_value = server

        with self.assertRaises(koji.GenericError) as cm:
            webidx.fileinfo(self.environ, self.filename, rpmID=self.rpm_id)
        self.assertEqual(
            str(cm.exception), 'No such RPM ID: %s' % self.rpm_id)

    def test_fileinfo_exception_archive(self):
        """Test taskinfo function raises exception"""
        server = mock.MagicMock()
        server.getArchive.return_value = None

        self.get_server.return_value = server

        with self.assertRaises(koji.GenericError) as cm:
            webidx.fileinfo(self.environ, self.filename, archiveID=self.archive_id)
        self.assertEqual(
            str(cm.exception), 'No such archive ID: %s' % self.archive_id)

    def test_fileinfo_exception_rpm_file(self):
        """Test taskinfo function raises exception"""
        server = mock.MagicMock()
        server.getRPMFile.return_value = None
        server.getRPM.return_value = {'id': 123}

        self.get_server.return_value = server

        with self.assertRaises(koji.GenericError) as cm:
            webidx.fileinfo(self.environ, self.filename, rpmID=self.rpm_id)
        self.assertEqual(
            str(cm.exception), 'no file %s in RPM %i' % (self.filename, int(self.rpm_id)))

    def test_fileinfo_exception_archive_file(self):
        """Test taskinfo function raises exception"""
        server = mock.MagicMock()
        server.getArchiveFile.return_value = None
        server.getArchive.return_value = {'id': 123}

        self.get_server.return_value = server

        with self.assertRaises(koji.GenericError) as cm:
            webidx.fileinfo(self.environ, self.filename, archiveID=self.archive_id)
        self.assertEqual(
            str(cm.exception), 'no file %s in archive %i' % (self.filename, int(self.archive_id)))

    def test_fileinfo_exception(self):
        """Test taskinfo function raises exception"""
        server = mock.MagicMock()

        self.get_server.return_value = server

        with self.assertRaises(koji.GenericError) as cm:
            webidx.fileinfo(self.environ, self.filename)
        self.assertEqual(str(cm.exception), 'either rpmID or archiveID must be specified')
