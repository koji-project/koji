import unittest
import mock

import koji
import kojihub


class TestGetRPM(unittest.TestCase):

    def test_wrong_type_rpminfo(self):
        rpminfo = ['test-user']
        with self.assertRaises(koji.GenericError) as cm:
            kojihub.get_rpm(rpminfo)
        self.assertEqual("Invalid type for rpminfo: %s" % type(rpminfo), str(cm.exception))


class TestGetRPMHeaders(unittest.TestCase):

    def setUp(self):
        self.exports = kojihub.RootExports()
        self.exports.getLoggedInUser = mock.MagicMock()
        self.context = mock.patch('kojihub.context').start()
        self.cursor = mock.MagicMock()

    def test_taskid_invalid_path(self):
        self.cursor.fetchone.return_value = None
        self.context.cnx.cursor.return_value = self.cursor
        filepath = '../test/path'
        with self.assertRaises(koji.GenericError) as cm:
            self.exports.getRPMHeaders(taskID=99, filepath=filepath)
        self.assertEqual("Invalid filepath: %s" % filepath, str(cm.exception))

    def test_taskid_without_filepath(self):
        self.cursor.fetchone.return_value = None
        self.context.cnx.cursor.return_value = self.cursor
        with self.assertRaises(koji.GenericError) as cm:
            self.exports.getRPMHeaders(taskID=99)
        self.assertEqual("filepath must be specified with taskID", str(cm.exception))
