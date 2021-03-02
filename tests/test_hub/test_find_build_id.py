import unittest

import mock

import koji
import kojihub


class TestFindBuildId(unittest.TestCase):

    def setUp(self):
        self.context = mock.patch('kojihub.context').start()
        self.cursor = mock.MagicMock()

    def test_non_exist_build_dict(self):
        build = {
            'name': 'test_name',
            'version': 'test_version',
            'release': 'test_release',
        }
        self.cursor.fetchone.return_value = None
        self.context.cnx.cursor.return_value = self.cursor
        with self.assertRaises(koji.GenericError) as cm:
            kojihub.find_build_id(build, strict=True)
        self.assertEqual("No such build: %s" % build, str(cm.exception))

    def test_invalid_argument(self):
        build = ['test-build']
        self.cursor.fetchone.return_value = None
        self.context.cnx.cursor.return_value = self.cursor
        with self.assertRaises(koji.GenericError) as cm:
            kojihub.find_build_id(build)
        self.assertEqual("Invalid type for argument: %s" % type(build), str(cm.exception))

    def test_build_dict_without_release(self):
        build = {
            'name': 'test_name',
            'version': 'test_version',
            'epoch': 'test_epoch',
            'owner': 'test_owner',
            'extra': {'extra_key': 'extra_value'},
        }
        self.cursor.fetchone.return_value = None
        self.context.cnx.cursor.return_value = self.cursor
        with self.assertRaises(koji.GenericError) as cm:
            kojihub.find_build_id(build, strict=True)
        self.assertEqual("did not provide name, version, and release", str(cm.exception))
