import unittest

import mock

import koji
import kojihub


class TestListTags(unittest.TestCase):

    def setUp(self):
        self.get_build = mock.patch('kojihub.get_build').start()
        self.exports = kojihub.RootExports()
        self.context = mock.patch('kojihub.context').start()
        self.cursor = mock.MagicMock()

    def test_non_exist_build(self):
        build_id = 999
        self.get_build.return_value = None
        with self.assertRaises(koji.GenericError) as cm:
            self.exports.listTags(build=build_id)
        self.assertEqual("No such build: %s" % build_id, str(cm.exception))

        build_name = 'test-build-1-23'
        self.get_build.return_value = None
        with self.assertRaises(koji.GenericError) as cm:
            self.exports.listTags(build=build_name)
        self.assertEqual("No such build: %s" % build_name, str(cm.exception))

    def test_non_exist_package(self):
        package_id = 999
        self.cursor.fetchone.return_value = None
        self.context.cnx.cursor.return_value = self.cursor
        kojihub.lookup_package.return_value = koji.GenericError
        with self.assertRaises(koji.GenericError) as cm:
            self.exports.listTags(package=package_id)
        self.assertEqual("No such package: %s" % package_id, str(cm.exception))

        package_name = 'test-pkg'
        self.cursor.fetchone.return_value = None
        self.context.cnx.cursor.return_value = self.cursor
        kojihub.lookup_package.return_value = koji.GenericError
        with self.assertRaises(koji.GenericError) as cm:
            self.exports.listTags(package=package_name)
        self.assertEqual("No such package: %s" % package_name, str(cm.exception))
