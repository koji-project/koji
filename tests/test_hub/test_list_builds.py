import unittest

from unittest import mock

import kojihub

QP = kojihub.QueryProcessor


class TestListBuilds(unittest.TestCase):
    def getQuery(self, *args, **kwargs):
        query = QP(*args, **kwargs)
        query.execute = mock.MagicMock()
        query.executeOne = self.query_executeOne
        query.iterate = mock.MagicMock()
        self.queries.append(query)
        return query

    def setUp(self):
        # defaults
        self.tables= ['build']
        # note: QueryProcessor reports these sorted by alias
        self.columns = [
            'build.id',
            'build.completion_time',
            "date_part('epoch', build.completion_time)",
            'events.id',
            'events.time',
            "date_part('epoch', events.time)",
            'build.draft',
            'build.epoch',
            'build.extra',
            'package.name',
            "package.name || '-' || build.version || '-' || build.release",
            'users.id',
            'users.name',
            'package.id',
            'package.name',
            'promoter.id',
            'promoter.name',
            'build.promotion_time',
            "date_part('epoch', build.promotion_time)",
            'build.release',
            'build.source',
            'build.start_time',
            "date_part('epoch', build.start_time)",
            'build.state',
            'build.task_id',
            'build.version',
            'volume.id',
            'volume.name',
        ]
        self.clauses = ['package.id = %(packageID)i']
        self.joins = [
            'LEFT JOIN events ON build.create_event = events.id',
            'LEFT JOIN package ON build.pkg_id = package.id',
            'LEFT JOIN volume ON build.volume_id = volume.id',
            'LEFT JOIN users ON build.owner = users.id',
            'LEFT JOIN users AS promoter ON build.promoter = promoter.id',
        ]

        self.maxDiff = None
        self.exports = kojihub.RootExports()
        self.query_executeOne = mock.MagicMock()
        self.QueryProcessor = mock.patch('kojihub.kojihub.QueryProcessor',
                                         side_effect=self.getQuery).start()
        self.queries = []

        self.context = mock.patch('kojihub.kojihub.context').start()
        self.get_package_id = mock.patch('kojihub.kojihub.get_package_id').start()
        self.get_user = mock.patch('kojihub.kojihub.get_user').start()
        self.cursor = mock.MagicMock()
        self.build_list = [{'build_id': 9,
                            'epoch': 0,
                            'name': 'test-package',
                            'nvr': 'test-package-11-12',
                            'owner_id': 1,
                            'owner_name': 'kojiadmin',
                            'package_id': 11,
                            'package_name': 'test-package',
                            'release': '12',
                            'state': 3,
                            'task_id': 879,
                            'version': '11',
                            'volume_id': 0,
                            'volume_name': 'DEFAULT',
                            'draft': False},]

    def tearDown(self):
        mock.patch.stopall()

    def test_wrong_package(self):
        package = 'test-package'
        self.get_package_id.return_value = None
        rv = self.exports.listBuilds(packageID=package)
        self.assertEqual(rv, [])

    def test_package_string(self):
        package = 'test-package'
        package_id = 1
        self.get_package_id.return_value = package_id
        self.query_executeOne.return_value = None
        self.exports.listBuilds(packageID=package)
        self.assertEqual(len(self.queries), 1)
        args, kwargs = self.QueryProcessor.call_args
        qp = QP(**kwargs)
        self.assertEqual(qp.tables, self.tables)
        self.assertEqual(qp.columns, self.columns)
        self.assertEqual(qp.clauses, self.clauses)
        self.assertEqual(qp.joins, self.joins)

    def test_wrong_user(self):
        user = 'test-user'
        self.get_user.return_value = None
        rv = self.exports.listBuilds(userID=user)
        self.assertEqual(rv, [])
    
    def test_draft(self):
        package = 'test-package'
        package_id = 1
        self.get_package_id.return_value = package_id
        self.query_executeOne.return_value = None
        self.exports.listBuilds(packageID=package, draft=True)
        self.assertEqual(len(self.queries), 1)
        args, kwargs = self.QueryProcessor.call_args
        qp = QP(**kwargs)
        self.assertEqual(qp.tables, self.tables)
        self.assertEqual(qp.columns, self.columns)
        self.assertEqual(qp.clauses, ['draft IS TRUE'] + self.clauses)
        self.assertEqual(qp.joins, self.joins)
