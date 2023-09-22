import unittest

import mock

import koji
import kojihub
import copy

QP = kojihub.QueryProcessor


class TestReadTaggedRPMS(unittest.TestCase):
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
        self.columns = ['rpminfo.name', 'rpminfo.version', 'rpminfo.release', 'rpminfo.arch',
                        'rpminfo.id', 'rpminfo.epoch', 'rpminfo.draft', 'rpminfo.payloadhash',
                        'rpminfo.size', 'rpminfo.buildtime', 'rpminfo.buildroot_id',
                        'rpminfo.build_id', 'rpminfo.metadata_only']
        self.joins = ['tag_listing ON rpminfo.build_id = tag_listing.build_id']
        self.aliases = ['name', 'version', 'release', 'arch', 'id', 'epoch', 'draft',
                        'payloadhash', 'size', 'buildtime', 'buildroot_id', 'build_id',
                        'metadata_only']
        self.clauses = ['(tag_listing.active = TRUE)',
                        'tag_id=%(tagid)s']
        self.tables = ['rpminfo']
        self.pkg_name = 'test_pkg'
        self.build_list = [
            {'build_id': 1, 'create_event': 1172, 'creation_event_id': 1171, 'epoch': None,
             'id': 1, 'name': 'test-pkg', 'nvr': 'test-pkg-2.52-1.fc35', 'owner_id': 1,
             'owner_name': 'kojiuser', 'package_id': 1, 'package_name': 'test-pkg',
             'release': '1.fc35', 'state': 1, 'tag_id': 1, 'tag_name': 'test-tag',
             'task_id': None, 'version': '2.52', 'volume_id': 0, 'volume_name': 'DEFAULT'}]

    def tearDown(self):
        mock.patch.stopall()

    def test_get_tagged_rpms_rpmsigs_arch_type_error(self):
        self.readTaggedBuilds.return_value = self.build_list
        error_message = 'Invalid type for arch option: %s' % type(1245)
        with self.assertRaises(koji.GenericError) as cm:
            kojihub.readTaggedRPMS(self.tag_name, arch=1245)
        self.assertEqual(error_message, str(cm.exception))

    def test_get_tagged_rpms_package_arch_list_without_extra(self):
        self.readTaggedBuilds.return_value = self.build_list
        kojihub.readTaggedRPMS(self.tag_name, package=self.pkg_name, arch=['x86_64', 'ppc'],
                               extra=False)

        self.assertEqual(len(self.queries), 1)
        query = self.queries[0]

        joins = copy.deepcopy(self.joins)
        joins.extend(['build ON rpminfo.build_id = build.id',
                      'package ON package.id = build.pkg_id'])
        clauses = copy.deepcopy(self.clauses)
        clauses.extend(['package.name = %(package)s', 'rpminfo.arch IN %(arch)s'])

        values = {'arch': ['x86_64', 'ppc'], 'package': 'test_pkg'}
        self.assertEqual(query.tables, self.tables)
        self.assertEqual(set(query.columns), set(self.columns))
        self.assertEqual(query.joins, joins)
        self.assertEqual(set(query.aliases), set(self.aliases))
        self.assertEqual(set(query.clauses), set(clauses))
        self.assertEqual(query.values, values)

    def test_get_tagged_rpms_rpmsigs_arch_extra(self):
        self.readTaggedBuilds.return_value = self.build_list
        kojihub.readTaggedRPMS(self.tag_name, rpmsigs='FD431D51', arch='x86_64')

        self.assertEqual(len(self.queries), 1)
        query = self.queries[0]

        joins = copy.deepcopy(self.joins)
        joins.extend(['LEFT OUTER JOIN rpmsigs on rpminfo.id = rpmsigs.rpm_id'])
        clauses = copy.deepcopy(self.clauses)
        clauses.append('rpminfo.arch = %(arch)s')
        columns = copy.deepcopy(self.columns)
        columns.extend(['rpmsigs.sigkey', 'rpminfo.extra'])
        aliases = copy.deepcopy(self.aliases)
        aliases.extend(['sigkey', 'extra'])

        values = {'arch': 'x86_64'}
        self.assertEqual(query.tables, self.tables)
        self.assertEqual(set(query.columns), set(columns))
        self.assertEqual(query.joins, joins)
        self.assertEqual(set(query.aliases), set(aliases))
        self.assertEqual(set(query.clauses), set(clauses))
        self.assertEqual(query.values, values)

    def test_get_tagged_rpms_draft(self):
        self.readTaggedBuilds.return_value = self.build_list
        kojihub.readTaggedRPMS(self.tag_name, draft=2, extra=False)

        self.assertEqual(len(self.queries), 1)
        query = self.queries[0]

        clauses = copy.deepcopy(self.clauses)
        clauses.extend(['rpminfo.draft IS NOT TRUE'])

        self.assertEqual(query.tables, self.tables)
        self.assertEqual(set(query.columns), set(self.columns))
        self.assertEqual(set(query.joins), set(self.joins))
        self.assertEqual(set(query.aliases), set(self.aliases))
        self.assertEqual(set(query.clauses), set(clauses))
        self.assertEqual(query.values, {})