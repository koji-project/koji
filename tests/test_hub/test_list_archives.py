import mock
from .utils import DBQueryTestCase

import koji
import kojihub


class TestListArchives(DBQueryTestCase):
    maxDiff = None

    def test_list_archives_simple(self):
        rv = kojihub.list_archives()

        self.assertEqual(len(self.queries), 1)
        self.assertLastQueryEqual(tables=['archiveinfo'],
                                  joins=['archivetypes on archiveinfo.type_id = archivetypes.id',
                                         'btype ON archiveinfo.btype_id = btype.id'],
                                  clauses=[],
                                  values={})
        self.assertEqual(rv, [])

    def test_list_archives_strict(self):
        with self.assertRaises(koji.GenericError) as cm:
            kojihub.list_archives(strict=True)
        self.assertEqual(cm.exception.args[0], 'No archives found.')

    def test_list_archives_buildid(self):
        kojihub.list_archives(buildID=1)
        self.assertLastQueryEqual(tables=['archiveinfo'],
                                  joins=['archivetypes on archiveinfo.type_id = archivetypes.id',
                                         'btype ON archiveinfo.btype_id = btype.id'],
                                  clauses=['build_id = %(build_id)i'],
                                  values={'build_id': 1})

    def test_list_archives_buildrootid(self):
        kojihub.list_archives(buildrootID=1)
        self.assertLastQueryEqual(tables=['archiveinfo'],
                                  joins=['archivetypes on archiveinfo.type_id = archivetypes.id',
                                         'btype ON archiveinfo.btype_id = btype.id'],
                                  clauses=['buildroot_id = %(buildroot_id)i'],
                                  values={'buildroot_id': 1})

    def test_list_archives_componentbuildrootid(self):
        kojihub.list_archives(componentBuildrootID=1)
        self.assertLastQueryEqual(tables=['archiveinfo'],
                                  joins=['archivetypes on archiveinfo.type_id = archivetypes.id',
                                         'btype ON archiveinfo.btype_id = btype.id',
                                         'buildroot_archives on archiveinfo.id = buildroot_archives.archive_id'],
                                  clauses=['buildroot_archives.buildroot_id = %(component_buildroot_id)i'],
                                  values={'component_buildroot_id': 1},
                                  colsByAlias={'build_id': 'archiveinfo.build_id',
                                               'type_name': 'archivetypes.name',
                                               'component_buildroot_id': 'buildroot_archives.buildroot_id',
                                               'type_id': 'archiveinfo.type_id',
                                               'checksum': 'archiveinfo.checksum',
                                               'extra': 'archiveinfo.extra',
                                               'filename': 'archiveinfo.filename',
                                               'project': 'buildroot_archives.project_dep',
                                               'type_description': 'archivetypes.description',
                                               'metadata_only': 'archiveinfo.metadata_only',
                                               'type_extensions': 'archivetypes.extensions',
                                               'btype': 'btype.name',
                                               'checksum_type': 'archiveinfo.checksum_type',
                                               'btype_id': 'archiveinfo.btype_id',
                                               'buildroot_id': 'archiveinfo.buildroot_id',
                                               'id': 'archiveinfo.id',
                                               'size': 'archiveinfo.size'})

    def test_list_archives_imageid(self):
        kojihub.list_archives(imageID=1)
        self.assertLastQueryEqual(tables=['archiveinfo'],
                                  joins=['archivetypes on archiveinfo.type_id = archivetypes.id',
                                         'btype ON archiveinfo.btype_id = btype.id',
                                         'archive_components ON archiveinfo.id = archive_components.component_id'],
                                  clauses=['archive_components.archive_id = %(imageID)i'],
                                  values={'imageID': 1})

    def test_list_archives_hostid(self):
        kojihub.list_archives(hostID=1)
        self.assertLastQueryEqual(tables=['archiveinfo'],
                                  joins=['archivetypes on archiveinfo.type_id = archivetypes.id',
                                         'btype ON archiveinfo.btype_id = btype.id',
                                         'standard_buildroot on archiveinfo.buildroot_id = standard_buildroot.buildroot_id'],
                                  clauses=['standard_buildroot.host_id = %(host_id)i'],
                                  values={'host_id': 1},
                                  colsByAlias={'host_id': 'standard_buildroot.host_id',
                                               'build_id': 'archiveinfo.build_id',
                                               'type_name': 'archivetypes.name',
                                               'type_id': 'archiveinfo.type_id',
                                               'checksum': 'archiveinfo.checksum',
                                               'extra': 'archiveinfo.extra',
                                               'filename': 'archiveinfo.filename',
                                               'type_description': 'archivetypes.description',
                                               'metadata_only': 'archiveinfo.metadata_only',
                                               'type_extensions': 'archivetypes.extensions',
                                               'btype': 'btype.name',
                                               'checksum_type': 'archiveinfo.checksum_type',
                                               'btype_id': 'archiveinfo.btype_id',
                                               'buildroot_id': 'archiveinfo.buildroot_id',
                                               'id': 'archiveinfo.id',
                                               'size': 'archiveinfo.size'})

    def test_list_archives_filename(self):
        kojihub.list_archives(filename='somefile.txt')
        self.assertLastQueryEqual(tables=['archiveinfo'],
                                  joins=['archivetypes on archiveinfo.type_id = archivetypes.id',
                                         'btype ON archiveinfo.btype_id = btype.id'],
                                  clauses=['filename = %(filename)s'],
                                  values={'filename': 'somefile.txt'})

    def test_list_archives_size(self):
        kojihub.list_archives(size=1231831)
        self.assertLastQueryEqual(tables=['archiveinfo'],
                                  joins=['archivetypes on archiveinfo.type_id = archivetypes.id',
                                         'btype ON archiveinfo.btype_id = btype.id'],
                                  clauses=['size = %(size)i'],
                                  values={'size': 1231831})

    def test_list_archives_checksum(self):
        kojihub.list_archives(checksum='7873f0a6dbf3abc07724e000ac9b3941')
        self.assertLastQueryEqual(tables=['archiveinfo'],
                                  joins=['archivetypes on archiveinfo.type_id = archivetypes.id',
                                         'btype ON archiveinfo.btype_id = btype.id'],
                                  clauses=['checksum = %(checksum)s'],
                                  values={'checksum': '7873f0a6dbf3abc07724e000ac9b3941'})

    def test_list_archives_archiveid(self):
        kojihub.list_archives(archiveID=1)
        self.assertLastQueryEqual(tables=['archiveinfo'],
                                  joins=['archivetypes on archiveinfo.type_id = archivetypes.id',
                                         'btype ON archiveinfo.btype_id = btype.id'],
                                  clauses=['archiveinfo.id = %(archive_id)s'],
                                  values={'archive_id': 1})

    def test_list_archives_type_maven(self):
        kojihub.list_archives(type='maven', typeInfo={'group_id': 'gid',
                                                      'artifact_id': 'aid',
                                                      'version': '1.0.1'})
        self.assertLastQueryEqual(tables=['archiveinfo'],
                                  joins=['archivetypes on archiveinfo.type_id = archivetypes.id',
                                         'btype ON archiveinfo.btype_id = btype.id',
                                         'maven_archives ON archiveinfo.id = maven_archives.archive_id'],
                                  clauses=['maven_archives.artifact_id = %(artifact_id)s',
                                           'maven_archives.group_id = %(group_id)s',
                                           'maven_archives.version = %(version)s'],
                                  values={'group_id': 'gid',
                                          'artifact_id': 'aid',
                                          'version': '1.0.1'},
                                  colsByAlias={'group_id': 'maven_archives.group_id',
                                               'artifact_id': 'maven_archives.artifact_id',
                                               'version': 'maven_archives.version',
                                               'build_id': 'archiveinfo.build_id',
                                               'type_name': 'archivetypes.name',
                                               'type_id': 'archiveinfo.type_id',
                                               'checksum': 'archiveinfo.checksum',
                                               'extra': 'archiveinfo.extra',
                                               'filename': 'archiveinfo.filename',
                                               'type_description': 'archivetypes.description',
                                               'metadata_only': 'archiveinfo.metadata_only',
                                               'type_extensions': 'archivetypes.extensions',
                                               'btype': 'btype.name',
                                               'checksum_type': 'archiveinfo.checksum_type',
                                               'btype_id': 'archiveinfo.btype_id',
                                               'buildroot_id': 'archiveinfo.buildroot_id',
                                               'id': 'archiveinfo.id',
                                               'size': 'archiveinfo.size'})

    def test_list_archives_type_win(self):
        kojihub.list_archives(type='win', typeInfo={'relpath': 'somerelpath',
                                                    'platforms': 'all',
                                                    'flags': ['A', 'B']})
        self.assertLastQueryEqual(tables=['archiveinfo'],
                                  joins=sorted([
                                         'archivetypes on archiveinfo.type_id = archivetypes.id',
                                         'btype ON archiveinfo.btype_id = btype.id',
                                         'win_archives ON archiveinfo.id = win_archives.archive_id']),
                                  clauses=sorted([
                                           'win_archives.relpath = %(relpath)s',
                                           r"platforms ~ %(platforms_pattern_0)s",
                                           r"flags ~ %(flags_pattern_0)s",
                                           r"flags ~ %(flags_pattern_1)s"]),
                                  values={'relpath': 'somerelpath',
                                          'flags_pattern_0': '\\mA\\M',
                                          'flags_pattern_1': '\\mB\\M',
                                          'platforms_pattern_0': '\\mall\\M',
                                          },
                                  colsByAlias={'relpath': 'win_archives.relpath',
                                               'platforms': 'win_archives.platforms',
                                               'flags': 'win_archives.flags',
                                               'build_id': 'archiveinfo.build_id',
                                               'type_name': 'archivetypes.name',
                                               'type_id': 'archiveinfo.type_id',
                                               'checksum': 'archiveinfo.checksum',
                                               'extra': 'archiveinfo.extra',
                                               'filename': 'archiveinfo.filename',
                                               'type_description': 'archivetypes.description',
                                               'metadata_only': 'archiveinfo.metadata_only',
                                               'type_extensions': 'archivetypes.extensions',
                                               'btype': 'btype.name',
                                               'checksum_type': 'archiveinfo.checksum_type',
                                               'btype_id': 'archiveinfo.btype_id',
                                               'buildroot_id': 'archiveinfo.buildroot_id',
                                               'id': 'archiveinfo.id',
                                               'size': 'archiveinfo.size'})

    def test_list_archives_type_image(self):
        kojihub.list_archives(type='image', typeInfo={'arch': 'i386'})
        self.assertLastQueryEqual(tables=['archiveinfo'],
                                  joins=['archivetypes on archiveinfo.type_id = archivetypes.id',
                                         'btype ON archiveinfo.btype_id = btype.id',
                                         'image_archives ON archiveinfo.id = image_archives.archive_id'],
                                  clauses=['image_archives.arch = %(arch)s'],
                                  values={'arch': 'i386'},
                                  colsByAlias={'arch': 'image_archives.arch',
                                               'build_id': 'archiveinfo.build_id',
                                               'type_name': 'archivetypes.name',
                                               'type_id': 'archiveinfo.type_id',
                                               'checksum': 'archiveinfo.checksum',
                                               'extra': 'archiveinfo.extra',
                                               'filename': 'archiveinfo.filename',
                                               'type_description': 'archivetypes.description',
                                               'metadata_only': 'archiveinfo.metadata_only',
                                               'type_extensions': 'archivetypes.extensions',
                                               'btype': 'btype.name',
                                               'checksum_type': 'archiveinfo.checksum_type',
                                               'btype_id': 'archiveinfo.btype_id',
                                               'buildroot_id': 'archiveinfo.buildroot_id',
                                               'id': 'archiveinfo.id',
                                               'size': 'archiveinfo.size'})

    @mock.patch('kojihub.lookup_name', return_value={'id': 111, 'name': 'other'})
    def test_list_archives_type_others(self, lookup_name):
        kojihub.list_archives(type='other')
        self.assertLastQueryEqual(tables=['archiveinfo'],
                                  joins=['archivetypes on archiveinfo.type_id = archivetypes.id',
                                         'btype ON archiveinfo.btype_id = btype.id'],
                                  clauses=['archiveinfo.btype_id = %(btype_id)s'],
                                  values={'btype_id': 111},
                                  colsByAlias={'build_id': 'archiveinfo.build_id',
                                               'type_name': 'archivetypes.name',
                                               'type_id': 'archiveinfo.type_id',
                                               'checksum': 'archiveinfo.checksum',
                                               'extra': 'archiveinfo.extra',
                                               'filename': 'archiveinfo.filename',
                                               'type_description': 'archivetypes.description',
                                               'metadata_only': 'archiveinfo.metadata_only',
                                               'type_extensions': 'archivetypes.extensions',
                                               'btype': 'btype.name',
                                               'checksum_type': 'archiveinfo.checksum_type',
                                               'btype_id': 'archiveinfo.btype_id',
                                               'buildroot_id': 'archiveinfo.buildroot_id',
                                               'id': 'archiveinfo.id',
                                               'size': 'archiveinfo.size'})

    @mock.patch('kojihub.lookup_name', return_value=None)
    def test_list_archives_type_not_found(self, lookup_name):
        with self.assertRaises(koji.GenericError) as cm:
            kojihub.list_archives(type='other')
        self.assertEqual(cm.exception.args[0], 'unsupported archive type: other')

    @mock.patch('kojihub.lookup_name', return_value={'id': 111, 'name': 'other'})
    def test_list_archives_type_other_with_typeinfo(self, lookup_name):
        with self.assertRaises(koji.GenericError) as cm:
            kojihub.list_archives(type='other', typeInfo={'somekey': 'somevalue'})
        self.assertEqual(cm.exception.args[0], 'typeInfo queries not supported for type other')
