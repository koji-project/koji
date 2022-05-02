import unittest
import mock

import koji
import kojihub

QP = kojihub.QueryProcessor


class TestListRpms(unittest.TestCase):
    def setUp(self):
        self.QueryProcessor = mock.patch('kojihub.QueryProcessor',
                                         side_effect=self.get_query).start()
        self.queries = []
        self.get_build = mock.patch('kojihub.get_build').start()
        self.get_host = mock.patch('kojihub.get_host').start()
        self._dml = mock.patch('kojihub._dml').start()
        self.list_rpms = {'arch': 'x86_64',
                          'build_id': 1,
                          'buildroot_id': 2,
                          'buildtime': 1596090711,
                          'epoch': 2,
                          'external_repo_id': 1,
                          'external_repo_name': 'fedora-34-released',
                          'extra': None,
                          'id': 277,
                          'metadata_only': False,
                          'name': 'shadow-utils',
                          'nvr': 'shadow-utils-4.8.1-4.fc33',
                          'payloadhash': 'c5bfe5267dc6e0ca127092a82b4f260b',
                          'release': '4.fc33',
                          'size': 3891272,
                          'version': '4.8.1'}

    def tearDown(self):
        mock.patch.stopall()

    def get_query(self, *args, **kwargs):
        query = QP(*args, **kwargs)
        query.execute = mock.MagicMock()
        self.queries.append(query)
        return query

    def test_wrong_type_arches(self):
        arches = {'test-arch': 'val'}
        with self.assertRaises(koji.GenericError) as cm:
            kojihub.list_rpms(arches=arches)
        self.assertEqual(f'Invalid type for "arches" parameter: {type(arches)}', str(cm.exception))

    def test_int_values(self):
        build_id = 1
        buildroot_id = 1
        host_id = 1
        arches = 'x86_64'
        kojihub.list_rpms(arches=arches, buildID=build_id, buildrootID=buildroot_id,
                          hostID=host_id)
        self.assertEqual(len(self.queries), 1)
        query = self.queries[0]
        self.assertEqual(query.tables, ['rpminfo'])
        self.assertEqual(query.joins,
                         ['LEFT JOIN external_repo ON rpminfo.external_repo_id = external_repo.id',
                          'standard_buildroot ON rpminfo.buildroot_id = '
                          'standard_buildroot.buildroot_id'])
        self.assertEqual(query.clauses, [
            'rpminfo.arch = %(arches)s',
            'rpminfo.build_id = %(buildID)i',
            'rpminfo.buildroot_id = %(buildrootID)i',
            'standard_buildroot.host_id = %(hostID)i',
        ])

    def test_compoenent_buldroot_image_list_arch_values(self):
        comp_buildroot_id = 1
        image_id = 1
        arches = ['x86_64']
        kojihub.list_rpms(componentBuildrootID=comp_buildroot_id, imageID=image_id, arches=arches)
        self.assertEqual(len(self.queries), 1)
        query = self.queries[0]
        self.assertEqual(query.tables, ['rpminfo'])
        self.assertEqual(query.joins,
                         ['LEFT JOIN external_repo ON rpminfo.external_repo_id = external_repo.id',
                          'buildroot_listing ON rpminfo.id = buildroot_listing.rpm_id',
                          'archive_rpm_components ON rpminfo.id = archive_rpm_components.rpm_id'])
        self.assertEqual(query.clauses, [
            'archive_rpm_components.archive_id = %(imageID)i',
            'buildroot_listing.buildroot_id = %(componentBuildrootID)i',
            'rpminfo.arch IN %(arches)s',
        ])
