import mock
import unittest

import koji
import kojihub

QP = kojihub.QueryProcessor


class TestListArchives(unittest.TestCase):
    def setUp(self):
        self.maxDiff = None
        self.get_build = mock.patch('kojihub.kojihub.get_build').start()
        self.get_host = mock.patch('kojihub.kojihub.get_host').start()
        self.QueryProcessor = mock.patch('kojihub.kojihub.QueryProcessor',
                                         side_effect=self.get_query).start()
        self.queries = []
        self.exports = kojihub.RootExports()

    def tearDown(self):
        mock.patch.stopall()

    def get_query(self, *args, **kwargs):
        query = QP(*args, **kwargs)
        query.execute = mock.MagicMock()
        self.queries.append(query)
        return query

    def test_list_archives_simple(self):
        kojihub.list_archives()

        self.assertEqual(len(self.queries), 1)
        query = self.queries[0]
        self.assertEqual(query.tables, ['archiveinfo'])
        self.assertEqual(query.clauses, [])
        self.assertEqual(query.joins, ['archivetypes on archiveinfo.type_id = archivetypes.id',
                                       'btype ON archiveinfo.btype_id = btype.id'])

    @mock.patch('kojihub.kojihub.QueryProcessor')
    def test_list_archives_strict(self, QueryProcessor):
        query = QueryProcessor.return_value
        query.execute.return_value = None
        with self.assertRaises(koji.GenericError) as cm:
            kojihub.list_archives(strict=True)
        self.assertEqual(cm.exception.args[0], 'No archives found.')

    def test_list_archives_buildid(self):
        kojihub.list_archives(buildID=1)
        self.assertEqual(len(self.queries), 1)
        query = self.queries[0]
        self.assertEqual(query.tables, ['archiveinfo'])
        self.assertEqual(query.clauses, ['build_id = %(build_id)i'])
        self.assertEqual(query.joins, ['archivetypes on archiveinfo.type_id = archivetypes.id',
                                       'btype ON archiveinfo.btype_id = btype.id'])
        self.assertEqual(query.values, {'build_id': 1})

    def test_list_archives_buildrootid(self):
        kojihub.list_archives(buildrootID=1)
        self.assertEqual(len(self.queries), 1)
        query = self.queries[0]
        self.assertEqual(query.tables, ['archiveinfo'])
        self.assertEqual(query.clauses, ['buildroot_id = %(buildroot_id)i'])
        self.assertEqual(query.joins, ['archivetypes on archiveinfo.type_id = archivetypes.id',
                                       'btype ON archiveinfo.btype_id = btype.id'])
        self.assertEqual(query.values, {'buildroot_id': 1})

    def test_list_archives_componentbuildrootid(self):
        kojihub.list_archives(componentBuildrootID=1)
        self.assertEqual(len(self.queries), 1)
        query = self.queries[0]
        self.assertEqual(query.tables, ['archiveinfo'])
        self.assertEqual(query.clauses,
                         ['buildroot_archives.buildroot_id = %(component_buildroot_id)i'])
        self.assertEqual(query.joins,
                         ['archivetypes on archiveinfo.type_id = archivetypes.id',
                          'btype ON archiveinfo.btype_id = btype.id',
                          'buildroot_archives on archiveinfo.id = buildroot_archives.archive_id'])
        self.assertEqual(query.values, {'component_buildroot_id': 1})

    def test_list_archives_imageid(self):
        kojihub.list_archives(imageID=1)
        self.assertEqual(len(self.queries), 1)
        query = self.queries[0]
        self.assertEqual(query.tables, ['archiveinfo'])
        self.assertEqual(query.clauses, ['archive_components.archive_id = %(imageID)i'])
        self.assertEqual(query.joins,
                         ['archivetypes on archiveinfo.type_id = archivetypes.id',
                          'btype ON archiveinfo.btype_id = btype.id',
                          'archive_components ON archiveinfo.id = '
                          'archive_components.component_id'])
        self.assertEqual(query.values, {'imageID': 1})

    def test_list_archives_hostid(self):
        kojihub.list_archives(hostID=1)
        self.assertEqual(len(self.queries), 1)
        query = self.queries[0]
        self.assertEqual(query.tables, ['archiveinfo'])
        self.assertEqual(query.clauses, ['standard_buildroot.host_id = %(host_id)i'])
        self.assertEqual(query.joins,
                         ['archivetypes on archiveinfo.type_id = archivetypes.id',
                          'btype ON archiveinfo.btype_id = btype.id',
                          'standard_buildroot on archiveinfo.buildroot_id = '
                          'standard_buildroot.buildroot_id'])
        self.assertEqual(query.values, {'host_id': 1})

    def test_list_archives_filename(self):
        kojihub.list_archives(filename='somefile.txt')
        self.assertEqual(len(self.queries), 1)
        query = self.queries[0]
        self.assertEqual(query.tables, ['archiveinfo'])
        self.assertEqual(query.clauses, ['filename = %(filename)s'])
        self.assertEqual(query.joins,
                         ['archivetypes on archiveinfo.type_id = archivetypes.id',
                          'btype ON archiveinfo.btype_id = btype.id'])
        self.assertEqual(query.values, {'filename': 'somefile.txt'})

    def test_list_archives_size(self):
        kojihub.list_archives(size=1231831)
        self.assertEqual(len(self.queries), 1)
        query = self.queries[0]
        self.assertEqual(query.tables, ['archiveinfo'])
        self.assertEqual(query.clauses, ['size = %(size)i'])
        self.assertEqual(query.joins,
                         ['archivetypes on archiveinfo.type_id = archivetypes.id',
                          'btype ON archiveinfo.btype_id = btype.id'])
        self.assertEqual(query.values, {'size': 1231831})

    def test_list_archives_checksum(self):
        kojihub.list_archives(checksum='7873f0a6dbf3abc07724e000ac9b3941')
        self.assertEqual(len(self.queries), 1)
        query = self.queries[0]
        self.assertEqual(query.tables, ['archiveinfo'])
        self.assertEqual(query.clauses, ['checksum = %(checksum)s'])
        self.assertEqual(query.joins,
                         ['archivetypes on archiveinfo.type_id = archivetypes.id',
                          'btype ON archiveinfo.btype_id = btype.id'])
        self.assertEqual(query.values, {'checksum': '7873f0a6dbf3abc07724e000ac9b3941'})

    def test_list_archives_checksum_type(self):
        kojihub.list_archives(checksum_type=koji.CHECKSUM_TYPES['sha256'])
        self.assertEqual(len(self.queries), 1)
        query = self.queries[0]
        self.assertEqual(query.tables, ['archiveinfo'])
        self.assertEqual(query.clauses, ['checksum_type = %(checksum_type)s'])
        self.assertEqual(query.joins,
                         ['archivetypes on archiveinfo.type_id = archivetypes.id',
                          'btype ON archiveinfo.btype_id = btype.id'])
        self.assertEqual(query.values, {'checksum_type': koji.CHECKSUM_TYPES['sha256']})

    def test_list_archives_archiveid(self):
        kojihub.list_archives(archiveID=1)
        self.assertEqual(len(self.queries), 1)
        query = self.queries[0]
        self.assertEqual(query.tables, ['archiveinfo'])
        self.assertEqual(query.clauses, ['archiveinfo.id = %(archive_id)s'])
        self.assertEqual(query.joins,
                         ['archivetypes on archiveinfo.type_id = archivetypes.id',
                          'btype ON archiveinfo.btype_id = btype.id'])
        self.assertEqual(query.values, {'archive_id': 1})

    def test_list_archives_type_maven(self):
        kojihub.list_archives(type='maven', typeInfo={'group_id': 'gid',
                                                      'artifact_id': 'aid',
                                                      'version': '1.0.1'})
        self.assertEqual(len(self.queries), 1)
        query = self.queries[0]
        self.assertEqual(query.tables, ['archiveinfo'])
        self.assertEqual(query.clauses, ['maven_archives.artifact_id = %(artifact_id)s',
                                         'maven_archives.group_id = %(group_id)s',
                                         'maven_archives.version = %(version)s'])
        self.assertEqual(query.joins,
                         ['archivetypes on archiveinfo.type_id = archivetypes.id',
                          'btype ON archiveinfo.btype_id = btype.id',
                          'maven_archives ON archiveinfo.id = maven_archives.archive_id'])
        self.assertEqual(query.values, {'group_id': 'gid',
                                        'artifact_id': 'aid',
                                        'version': '1.0.1'})

    def test_list_archives_type_win(self):
        kojihub.list_archives(type='win', typeInfo={'relpath': 'somerelpath',
                                                    'platforms': 'all',
                                                    'flags': ['A', 'B']})
        self.assertEqual(len(self.queries), 1)
        query = self.queries[0]
        self.assertEqual(query.tables, ['archiveinfo'])
        self.assertEqual(query.clauses, sorted(['win_archives.relpath = %(relpath)s',
                                                r"platforms ~ %(platforms_pattern_0)s",
                                                r"flags ~ %(flags_pattern_0)s",
                                                r"flags ~ %(flags_pattern_1)s"]))
        self.assertEqual(query.joins,
                         ['archivetypes on archiveinfo.type_id = archivetypes.id',
                          'btype ON archiveinfo.btype_id = btype.id',
                          'win_archives ON archiveinfo.id = win_archives.archive_id'])
        self.assertEqual(query.values, {'relpath': 'somerelpath',
                                        'flags_pattern_0': '\\mA\\M',
                                        'flags_pattern_1': '\\mB\\M',
                                        'platforms_pattern_0': '\\mall\\M'})

    def test_list_archives_type_image(self):
        kojihub.list_archives(type='image', typeInfo={'arch': 'i386'})
        self.assertEqual(len(self.queries), 1)
        query = self.queries[0]
        self.assertEqual(query.tables, ['archiveinfo'])
        self.assertEqual(query.clauses, ['image_archives.arch = %(arch)s'])
        self.assertEqual(query.joins,
                         ['archivetypes on archiveinfo.type_id = archivetypes.id',
                          'btype ON archiveinfo.btype_id = btype.id',
                          'image_archives ON archiveinfo.id = image_archives.archive_id'])
        self.assertEqual(query.values, {'arch': 'i386'})

    @mock.patch('kojihub.kojihub.lookup_name', return_value={'id': 111, 'name': 'other'})
    def test_list_archives_type_others(self, lookup_name):
        kojihub.list_archives(type='other')
        self.assertEqual(len(self.queries), 1)
        query = self.queries[0]
        self.assertEqual(query.tables, ['archiveinfo'])
        self.assertEqual(query.clauses, ['archiveinfo.btype_id = %(btype_id)s'])
        self.assertEqual(query.joins,
                         ['archivetypes on archiveinfo.type_id = archivetypes.id',
                          'btype ON archiveinfo.btype_id = btype.id'])
        self.assertEqual(query.values, {'btype_id': 111})

    @mock.patch('kojihub.kojihub.lookup_name', return_value=None)
    def test_list_archives_type_not_found(self, lookup_name):
        with self.assertRaises(koji.GenericError) as cm:
            kojihub.list_archives(type='other')
        self.assertEqual(cm.exception.args[0], 'unsupported archive type: other')

    @mock.patch('kojihub.kojihub.lookup_name', return_value={'id': 111, 'name': 'other'})
    def test_list_archives_type_other_with_typeinfo(self, lookup_name):
        with self.assertRaises(koji.GenericError) as cm:
            kojihub.list_archives(type='other', typeInfo={'somekey': 'somevalue'})
        self.assertEqual(cm.exception.args[0], 'typeInfo queries not supported for type other')
