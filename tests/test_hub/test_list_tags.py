import unittest

import mock

import koji
import kojihub

QP = kojihub.QueryProcessor


class TestListTags(unittest.TestCase):

    def setUp(self):
        self.maxDiff = None
        self.get_build = mock.patch('kojihub.kojihub.get_build').start()
        self.exports = kojihub.RootExports()
        self.context = mock.patch('kojihub.kojihub.context').start()
        self.cursor = mock.MagicMock()
        self.QueryProcessor = mock.patch('kojihub.kojihub.QueryProcessor',
                                         side_effect=self.getQuery).start()
        self.queries = []

    def tearDown(self):
        mock.patch.stopall()

    def getQuery(self, *args, **kwargs):
        query = QP(*args, **kwargs)
        query.execute = mock.MagicMock()
        query.executeOne = mock.MagicMock()
        self.queries.append(query)
        return query

    def test_non_exist_build(self):
        build_id = 999
        self.get_build.return_value = None
        with self.assertRaises(koji.GenericError) as cm:
            self.exports.listTags(build=build_id)
        self.assertEqual(f"No such build: {build_id}", str(cm.exception))

        build_name = 'test-build-1-23'
        self.get_build.return_value = None
        with self.assertRaises(koji.GenericError) as cm:
            self.exports.listTags(build=build_name)
        self.assertEqual(f"No such build: {build_name}", str(cm.exception))

    @mock.patch('kojihub.kojihub.lookup_package')
    def test_non_exist_package(self, lookup_package):
        self.cursor.fetchone.return_value = None
        self.context.cnx.cursor.return_value = self.cursor
        lookup_package.return_value = None

        package_id = 999
        with self.assertRaises(koji.GenericError) as cm:
            self.exports.listTags(package=package_id)
        self.assertEqual(f'No such package: {package_id}', str(cm.exception))

        package_name = 'test-pkg'
        with self.assertRaises(koji.GenericError) as cm:
            self.exports.listTags(package=package_name)
        self.assertEqual(f'No such package: {package_name}', str(cm.exception))

    def test_build_package_not_none(self):
        build_id = 999
        package_id = 998

        with self.assertRaises(koji.GenericError) as cm:
            self.exports.listTags(build=build_id, package=package_id)
        self.assertEqual("only one of build and package may be specified", str(cm.exception))
        self.get_build.assert_not_called()

    @mock.patch('kojihub.kojihub.lookup_package')
    def test_exist_package_and_perms(self, lookup_package):
        package_info = {'id': 123, 'name': 'package-name'}
        self.cursor.fetchone.return_value = None
        self.context.cnx.cursor.return_value = self.cursor
        lookup_package.return_value = package_info

        self.exports.listTags(package=package_info['id'], perms=True)

        self.assertEqual(len(self.queries), 1)
        query = self.queries[0]
        self.assertEqual(query.tables, ['tag_config'])
        self.assertEqual(query.joins,
                         ['tag ON tag.id = tag_config.tag_id',
                          'LEFT OUTER JOIN permissions ON tag_config.perm_id = permissions.id',
                          'tag_packages ON tag.id = tag_packages.tag_id',
                          'tag_package_owners ON\n   '
                          'tag_packages.tag_id = tag_package_owners.tag_id '
                          'AND\n   tag_packages.package_id = tag_package_owners.package_id AND\n'
                          '   tag_package_owners.active IS TRUE',
                          'users ON tag_package_owners.owner = users.id'])
        self.assertEqual(query.clauses, [
            'tag_config.active = true',
            'tag_packages.active = true',
            'tag_packages.package_id = %(packageID)i',
        ])

    def test_exist_build_and_pattern(self):
        build_info = {'id': 123, 'name': 'package-build-1.23.0'}
        pattern = 'package-build'
        self.cursor.fetchone.return_value = None
        self.context.cnx.cursor.return_value = self.cursor
        self.get_build.return_value = build_info

        self.exports.listTags(build=build_info['id'], pattern=pattern)

        self.assertEqual(len(self.queries), 1)
        query = self.queries[0]
        self.assertEqual(query.tables, ['tag_config'])
        self.assertEqual(query.joins,
                         ['tag ON tag.id = tag_config.tag_id',
                          'LEFT OUTER JOIN permissions ON tag_config.perm_id = permissions.id',
                          'tag_listing ON tag.id = tag_listing.tag_id'])
        self.assertEqual(query.clauses, [
            'tag.name ILIKE %(pattern)s',
            'tag_config.active = true',
            'tag_listing.active = true',
            'tag_listing.build_id = %(buildID)i',
        ])
