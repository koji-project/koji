import unittest

import mock

import koji
import kojihub
import copy

QP = kojihub.QueryProcessor


class TestReadTaggedArchives(unittest.TestCase):
    def getQuery(self, *args, **kwargs):
        self.maxDiff = None
        query = QP(*args, **kwargs)
        query.execute = mock.MagicMock()
        query.executeOne = mock.MagicMock()
        self.queries.append(query)
        return query

    def setUp(self):
        self.QueryProcessor = mock.patch('kojihub.kojihub.QueryProcessor',
                                         side_effect=self.getQuery).start()
        self.queries = []
        self.context = mock.patch('kojihub.kojihub.context').start()
        # It seems MagicMock will not automatically handle attributes that
        # start with "assert"
        self.exports = kojihub.RootExports()
        self.readTaggedBuilds = mock.patch('kojihub.kojihub.readTaggedBuilds').start()
        self.tag_name = 'test-tag'
        self.columns = ['archiveinfo.id', 'archiveinfo.type_id', 'archiveinfo.btype_id',
                        'btype.name', 'archiveinfo.build_id', 'archiveinfo.buildroot_id',
                        'archiveinfo.filename', 'archiveinfo.size', 'archiveinfo.checksum',
                        'archiveinfo.checksum_type', 'archiveinfo.metadata_only']
        self.joins = ['tag_listing ON archiveinfo.build_id = tag_listing.build_id',
                      'btype ON archiveinfo.btype_id = btype.id']
        self.aliases = ['id', 'type_id', 'btype_id', 'btype', 'build_id', 'buildroot_id',
                        'filename', 'size', 'checksum', 'checksum_type', 'metadata_only']
        self.clauses = ['(active = TRUE)',
                        'tag_listing.tag_id = %(tagid)i']
        self.tables = ['archiveinfo']
        self.pkg_name = 'test_pkg'
        self.build_list = [
            {'build_id': 1, 'create_event': 1172, 'creation_event_id': 1171, 'epoch': None,
             'id': 1, 'name': 'test-pkg', 'nvr': 'test-pkg-2.52-1.fc35', 'owner_id': 1,
             'owner_name': 'kojiuser', 'package_id': 1, 'package_name': 'test-pkg',
             'release': '1.fc35', 'state': 1, 'tag_id': 1, 'tag_name': 'test-tag',
             'task_id': None, 'version': '2.52', 'volume_id': 0, 'volume_name': 'DEFAULT'}]

    def tearDown(self):
        mock.patch.stopall()

    def test_get_tagged_archives_default(self):
        self.readTaggedBuilds.return_value = self.build_list
        kojihub.readTaggedArchives(self.tag_name)

        self.assertEqual(len(self.queries), 1)
        query = self.queries[0]

        columns = copy.deepcopy(self.columns)
        columns.append('archiveinfo.extra')
        aliases = copy.deepcopy(self.aliases)
        aliases.append('extra')

        values = {'package': None, 'tagid': self.tag_name}
        self.assertEqual(query.tables, self.tables)
        self.assertEqual(query.joins, self.joins)
        self.assertEqual(set(query.columns), set(columns))
        self.assertEqual(set(query.aliases), set(aliases))
        self.assertEqual(set(query.clauses), set(self.clauses))
        self.assertEqual(query.values, values)

    def test_get_tagged_archives_package_type_maven_without_extra(self):
        self.readTaggedBuilds.return_value = self.build_list
        kojihub.readTaggedArchives(self.tag_name, package=self.pkg_name, type='maven', extra=False)

        self.assertEqual(len(self.queries), 1)
        query = self.queries[0]

        columns = copy.deepcopy(self.columns)
        columns.extend(['maven_archives.group_id', 'maven_archives.artifact_id',
                        'maven_archives.version'])
        aliases = copy.deepcopy(self.aliases)
        aliases.extend(['maven_group_id', 'maven_artifact_id', 'maven_version'])
        clauses = copy.deepcopy(self.clauses)
        clauses.extend(['package.name = %(package)s'])
        joins = copy.deepcopy(self.joins)
        joins.extend(['build ON archiveinfo.build_id = build.id',
                      'package ON build.pkg_id = package.id',
                      'maven_archives ON archiveinfo.id = maven_archives.archive_id'])

        values = {'package': self.pkg_name, 'tagid': self.tag_name}
        self.assertEqual(query.tables, self.tables)
        self.assertEqual(query.joins, joins)
        self.assertEqual(set(query.columns), set(columns))
        self.assertEqual(set(query.aliases), set(aliases))
        self.assertEqual(set(query.clauses), set(clauses))
        self.assertEqual(query.values, values)

    def test_get_tagged_archives_package_type_win_without_extra(self):
        self.readTaggedBuilds.return_value = self.build_list
        kojihub.readTaggedArchives(self.tag_name, type='win', extra=False)

        self.assertEqual(len(self.queries), 1)
        query = self.queries[0]

        columns = copy.deepcopy(self.columns)
        columns.extend(['win_archives.relpath', 'win_archives.platforms', 'win_archives.flags'])
        aliases = copy.deepcopy(self.aliases)
        aliases.extend(['relpath', 'platforms', 'flags'])
        joins = copy.deepcopy(self.joins)
        joins.append('win_archives ON archiveinfo.id = win_archives.archive_id')

        values = {'package': None, 'tagid': self.tag_name}
        self.assertEqual(query.tables, self.tables)
        self.assertEqual(query.joins, joins)
        self.assertEqual(set(query.columns), set(columns))
        self.assertEqual(set(query.aliases), set(aliases))
        self.assertEqual(set(query.clauses), set(self.clauses))
        self.assertEqual(query.values, values)

    def test_get_tagged_archives_type_non_exist(self):
        self.readTaggedBuilds.return_value = self.build_list
        error_message = "unsupported archive type: non-exist-type"
        with self.assertRaises(koji.GenericError) as cm:
            kojihub.readTaggedArchives(self.tag_name, type='non-exist-type')
        self.assertEqual(error_message, str(cm.exception))
