import unittest

import mock

import koji
import kojihub
import copy

from koji.util import dslice

QP = kojihub.QueryProcessor


class TestReadTaggedBuilds(unittest.TestCase):
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
        self.readPackageList = mock.patch('kojihub.kojihub.readPackageList').start()
        self.lookup_name = mock.patch('kojihub.kojihub.lookup_name').start()
        self.tag_name = 'test-tag'
        self.columns = ['build.id', 'build.completion_time', 'tag_listing.create_event',
                        'events.id', 'events.time', 'build.draft', 'build.epoch', 'build.id',
                        'package.name',
                        "package.name || '-' || build.version || '-' || build.release",
                        'users.id', 'users.name', 'package.id', 'package.name', 'promoter.id',
                        'promoter.name', 'build.promotion_time', 'build.release',
                        'build.start_time', 'build.state', 'tag.id', 'tag.name', 'build.task_id',
                        'build.version', 'volume.id', 'volume.name']
        self.values = {'owner': None,
                       'package': None,
                       'st_complete': 1,
                       'tagid': self.tag_name,
                      }
        self.joins = ['tag ON tag.id = tag_listing.tag_id',
                      'build ON build.id = tag_listing.build_id',
                      'events ON events.id = build.create_event',
                      'package ON package.id = build.pkg_id',
                      'volume ON volume.id = build.volume_id',
                      'users ON users.id = build.owner',
                      'LEFT JOIN users AS promoter ON promoter.id = build.promoter',
                      ]
        self.aliases = ['build_id', 'completion_time', 'create_event', 'creation_event_id',
                        'creation_time', 'draft', 'epoch', 'id', 'name', 'nvr', 'owner_id',
                        'owner_name', 'package_id', 'package_name', 'promoter_id',
                        'promoter_name', 'promotion_time', 'release', 'start_time', 'state',
                        'tag_id', 'tag_name', 'task_id', 'version', 'volume_id', 'volume_name']
        self.clauses = ['(tag_listing.active = TRUE)',
                        'tag_id = %(tagid)s',
                        'build.state = %(st_complete)i']
        self.tables = ['tag_listing']
        self.pkg_name = 'test_pkg'
        self.username = 'testuser'
        self.package_list = {1: {'blocked': False, 'extra_arches': '', 'package_id': 1,
                                 'package_name': self.pkg_name, 'tag_id': 4,
                                 'tag_name': self.tag_name},
                             'owner_name': self.username}

    def tearDown(self):
        mock.patch.stopall()

    def test_get_tagged_builds_default(self):
        self.readPackageList.return_value = self.package_list
        kojihub.readTaggedBuilds(self.tag_name)

        self.assertEqual(len(self.queries), 1)
        query = self.queries[0]

        values = self.values.copy()
        self.assertEqual(query.tables, self.tables)
        self.assertEqual(query.joins, self.joins)
        self.assertEqual(set(query.columns), set(self.columns))
        self.assertEqual(set(query.aliases), set(self.aliases))
        self.assertEqual(set(query.clauses), set(self.clauses))
        # function passes values=locals(), so we only check the relevant values
        self.assertEqual(dslice(query.values, values.keys()), values)

    def test_get_tagged_builds_package_owner_type_maven_extra(self):
        self.readPackageList.return_value = self.package_list
        kojihub.readTaggedBuilds(self.tag_name, package=self.pkg_name, owner=self.username,
                                 type='maven', extra=True)

        self.assertEqual(len(self.queries), 1)
        query = self.queries[0]

        columns = copy.deepcopy(self.columns)
        columns.extend(['maven_builds.group_id', 'maven_builds.artifact_id',
                       'maven_builds.version', 'build.extra'])
        aliases = copy.deepcopy(self.aliases)
        aliases.extend(['maven_group_id', 'maven_artifact_id', 'maven_version', 'extra'])
        clauses = copy.deepcopy(self.clauses)
        clauses.extend(['package.name = %(package)s', 'users.name = %(owner)s'])
        joins = copy.deepcopy(self.joins)
        joins.append('maven_builds ON maven_builds.build_id = tag_listing.build_id')

        values = self.values.copy()
        values['owner'] = self.username
        values['package'] = self.pkg_name
        self.assertEqual(query.tables, self.tables)
        self.assertEqual(query.joins, joins)
        self.assertEqual(set(query.columns), set(columns))
        self.assertEqual(set(query.aliases), set(aliases))
        self.assertEqual(set(query.clauses), set(clauses))
        # function passes values=locals(), so we only check the relevant values
        self.assertEqual(dslice(query.values, values.keys()), values)

    def test_get_tagged_builds_type_win_latest(self):
        self.readPackageList.return_value = self.package_list
        kojihub.readTaggedBuilds(self.tag_name, type='win', latest=True)

        self.assertEqual(len(self.queries), 1)
        query = self.queries[0]

        columns = copy.deepcopy(self.columns)
        columns.append('win_builds.platform')
        aliases = copy.deepcopy(self.aliases)
        aliases.append('platform')
        joins = copy.deepcopy(self.joins)
        joins.append('win_builds ON win_builds.build_id = tag_listing.build_id')

        values = self.values.copy()
        self.assertEqual(query.tables, self.tables)
        self.assertEqual(query.joins, joins)
        self.assertEqual(set(query.columns), set(columns))
        self.assertEqual(set(query.aliases), set(aliases))
        self.assertEqual(set(query.clauses), set(self.clauses))
        # function passes values=locals(), so we only check the relevant values
        self.assertEqual(dslice(query.values, values.keys()), values)

    def test_get_tagged_builds_type_image(self):
        self.readPackageList.return_value = self.package_list
        kojihub.readTaggedBuilds(self.tag_name, type='image')

        self.assertEqual(len(self.queries), 1)
        query = self.queries[0]

        columns = copy.deepcopy(self.columns)
        columns.append('image_builds.build_id')
        aliases = copy.deepcopy(self.aliases)
        aliases.append('build_id')
        joins = copy.deepcopy(self.joins)
        joins.append('image_builds ON image_builds.build_id = tag_listing.build_id')

        values = self.values.copy()
        self.assertEqual(query.tables, self.tables)
        self.assertEqual(query.joins, joins)
        self.assertEqual(set(query.columns), set(columns))
        self.assertEqual(set(query.aliases), set(aliases))
        self.assertEqual(set(query.clauses), set(self.clauses))
        # function passes values=locals(), so we only check the relevant values
        self.assertEqual(dslice(query.values, values.keys()), values)

    def test_get_tagged_builds_type_non_exist(self):
        self.readPackageList.return_value = self.package_list
        self.lookup_name.return_value = None
        error_message = "unsupported build type: non-exist-type"
        with self.assertRaises(koji.GenericError) as cm:
            kojihub.readTaggedBuilds(self.tag_name, type='non-exist-type')
        self.assertEqual(error_message, str(cm.exception))

    def test_get_tagged_builds_type_exists(self):
        self.readPackageList.return_value = self.package_list
        type = 'exist-type'
        typeinfo = {'id': 11, 'name': type}
        self.lookup_name.return_value = typeinfo
        kojihub.readTaggedBuilds(self.tag_name, type=type)

        self.assertEqual(len(self.queries), 1)
        query = self.queries[0]

        joins = copy.deepcopy(self.joins)
        joins.append('build_types ON build.id = build_types.build_id AND btype_id = %(btype_id)s')

        values = self.values.copy()
        self.assertEqual(query.tables, self.tables)
        self.assertEqual(query.joins, joins)
        self.assertEqual(set(query.columns), set(self.columns))
        self.assertEqual(set(query.aliases), set(self.aliases))
        self.assertEqual(set(query.clauses), set(self.clauses))
        # function passes values=locals(), so we only check the relevant values
        self.assertEqual(dslice(query.values, values.keys()), values)
    
    def test_get_tagged_builds_draft(self):
        self.readPackageList.return_value = self.package_list
        kojihub.readTaggedBuilds(self.tag_name, draft=True)

        self.assertEqual(len(self.queries), 1)
        query = self.queries[0]

        clauses = copy.deepcopy(self.clauses)
        clauses.extend(['draft IS TRUE'])

        values = self.values.copy()
        self.assertEqual(query.tables, self.tables)
        self.assertEqual(query.joins, self.joins)
        self.assertEqual(set(query.columns), set(self.columns))
        self.assertEqual(set(query.aliases), set(self.aliases))
        self.assertEqual(set(query.clauses), set(clauses))
        # function passes values=locals(), so we only check the relevant values
        self.assertEqual(dslice(query.values, values.keys()), values)
