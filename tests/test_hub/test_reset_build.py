import mock
import unittest

import koji
import kojihub

DP = kojihub.DeleteProcessor
QP = kojihub.QueryProcessor
UP = kojihub.UpdateProcessor


class TestResetBuild(unittest.TestCase):

    def getDelete(self, *args, **kwargs):
        delete = DP(*args, **kwargs)
        delete.execute = mock.MagicMock()
        self.deletes.append(delete)
        return delete

    def getQuery(self, *args, **kwargs):
        query = QP(*args, **kwargs)
        query.execute = self.query_execute
        self.queries.append(query)
        return query

    def getUpdate(self, *args, **kwargs):
        update = UP(*args, **kwargs)
        update.execute = mock.MagicMock()
        self.updates.append(update)
        return update

    def setUp(self):
        self.maxDiff = None
        self.DeleteProcessor = mock.patch('kojihub.kojihub.DeleteProcessor',
                                          side_effect=self.getDelete).start()
        self.deletes = []
        self.QueryProcessor = mock.patch('kojihub.kojihub.QueryProcessor',
                                         side_effect=self.getQuery).start()
        self.queries = []
        self.query_execute = mock.MagicMock()
        self.UpdateProcessor = mock.patch('kojihub.kojihub.UpdateProcessor',
                                          side_effect=self.getUpdate).start()
        self.updates = []
        self.get_build = mock.patch('kojihub.kojihub.get_build').start()
        self.context = mock.patch('kojihub.kojihub.context').start()
        self.context.session.assertPerm = mock.MagicMock()
        # don't remove anything unexpected
        self.rmtree = mock.patch('koji.util.rmtree').start()
        self.unlink = mock.patch('os.unlink').start()
        self.build_id = 3
        self.binfo = {'id': 3, 'state': koji.BUILD_STATES['COMPLETE'], 'name': 'test_nvr',
                      'nvr': 'test_nvr-3.3-20.el8', 'version': '3.3', 'release': '20',
                      'task_id': 12, 'volume_id': 1, 'build_id': 3}
        self.del_binfo = {'id': 3, 'state': koji.BUILD_STATES['CANCELED'],
                          'name': 'test_nvr', 'nvr': 'test_nvr-3.3-20.el8', 'version': '3.3',
                          'release': '20', 'task_id': None, 'volume_id': 0}

    def tearDown(self):
        mock.patch.stopall()

    def test_reset_build_queries(self):
        self.get_build.side_effect = [self.binfo, self.del_binfo]
        self.query_execute.side_effect = [
            [(123, )],
            [(9999,)],
        ]

        kojihub.reset_build(self.build_id)

        self.assertEqual(len(self.queries), 2)
        query = self.queries[0]
        self.assertEqual(query.tables, ['rpminfo'])
        self.assertEqual(query.joins, None)
        self.assertEqual(query.clauses, ['build_id=%(id)i'])
        self.assertEqual(query.columns, ['id'])
        self.assertEqual(query.values, {'id': self.binfo['build_id']})

        query = self.queries[1]
        self.assertEqual(query.tables, ['archiveinfo'])
        self.assertEqual(query.joins, None)
        self.assertEqual(query.clauses, ['build_id=%(id)i'])
        self.assertEqual(query.columns, ['id'])
        self.assertEqual(query.values, {'id': self.binfo['build_id']})

        self.assertEqual(len(self.updates), 1)
        update = self.updates[0]
        self.assertEqual(update.table, 'build')
        self.assertEqual(update.values, {'id': self.binfo['id']})
        self.assertEqual(update.data, {'state': 4, 'task_id': None, 'volume_id': 0})
        self.assertEqual(update.rawdata, {})
        self.assertEqual(update.clauses, ['id=%(id)s'])

        self.assertEqual(len(self.deletes), 18)
        delete = self.deletes[0]
        self.assertEqual(delete.table, 'rpmsigs')
        self.assertEqual(delete.clauses, ['rpm_id=%(rpm_id)i'])
        self.assertEqual(delete.values, {'rpm_id': 123})

        delete = self.deletes[1]
        self.assertEqual(delete.table, 'buildroot_listing')
        self.assertEqual(delete.clauses, ['rpm_id=%(rpm_id)i'])
        self.assertEqual(delete.values, {'rpm_id': 123})

        delete = self.deletes[2]
        self.assertEqual(delete.table, 'archive_rpm_components')
        self.assertEqual(delete.clauses, ['rpm_id=%(rpm_id)i'])
        self.assertEqual(delete.values, {'rpm_id': 123})

        delete = self.deletes[3]
        self.assertEqual(delete.table, 'rpm_checksum')
        self.assertEqual(delete.clauses, ['rpm_id=%(rpm_id)i'])
        self.assertEqual(delete.values, {'rpm_id': 123})

        delete = self.deletes[4]
        self.assertEqual(delete.table, 'rpminfo')
        self.assertEqual(delete.clauses, ['build_id=%(id)i'])
        self.assertEqual(delete.values, {'id': self.binfo['build_id']})

        delete = self.deletes[5]
        self.assertEqual(delete.table, 'maven_archives')
        self.assertEqual(delete.clauses, ['archive_id=%(archive_id)i'])
        self.assertEqual(delete.values, {'archive_id': 9999})

        delete = self.deletes[6]
        self.assertEqual(delete.table, 'win_archives')
        self.assertEqual(delete.clauses, ['archive_id=%(archive_id)i'])
        self.assertEqual(delete.values, {'archive_id': 9999})

        delete = self.deletes[7]
        self.assertEqual(delete.table, 'image_archives')
        self.assertEqual(delete.clauses, ['archive_id=%(archive_id)i'])
        self.assertEqual(delete.values, {'archive_id': 9999})

        delete = self.deletes[8]
        self.assertEqual(delete.table, 'buildroot_archives')
        self.assertEqual(delete.clauses, ['archive_id=%(archive_id)i'])
        self.assertEqual(delete.values, {'archive_id': 9999})

        delete = self.deletes[9]
        self.assertEqual(delete.table, 'archive_rpm_components')
        self.assertEqual(delete.clauses, ['archive_id=%(archive_id)i'])
        self.assertEqual(delete.values, {'archive_id': 9999})

        delete = self.deletes[10]
        self.assertEqual(delete.table, 'archive_components')
        self.assertEqual(delete.clauses, ['archive_id=%(archive_id)i'])
        self.assertEqual(delete.values, {'archive_id': 9999})

        delete = self.deletes[11]
        self.assertEqual(delete.table, 'archive_components')
        self.assertEqual(delete.clauses, ['component_id=%(archive_id)i'])
        self.assertEqual(delete.values, {'archive_id': 9999})

        delete = self.deletes[12]
        self.assertEqual(delete.table, 'archiveinfo')
        self.assertEqual(delete.clauses, ['build_id=%(id)i'])
        self.assertEqual(delete.values, {'id': self.binfo['build_id']})

        delete = self.deletes[13]
        self.assertEqual(delete.table, 'maven_builds')
        self.assertEqual(delete.clauses, ['build_id=%(id)i'])
        self.assertEqual(delete.values, {'id': self.binfo['build_id']})

        delete = self.deletes[14]
        self.assertEqual(delete.table, 'win_builds')
        self.assertEqual(delete.clauses, ['build_id=%(id)i'])
        self.assertEqual(delete.values, {'id': self.binfo['build_id']})

        delete = self.deletes[15]
        self.assertEqual(delete.table, 'image_builds')
        self.assertEqual(delete.clauses, ['build_id=%(id)i'])
        self.assertEqual(delete.values, {'id': self.binfo['build_id']})

        delete = self.deletes[16]
        self.assertEqual(delete.table, 'build_types')
        self.assertEqual(delete.clauses, ['build_id=%(id)i'])
        self.assertEqual(delete.values, {'id': self.binfo['build_id']})

        delete = self.deletes[17]
        self.assertEqual(delete.table, 'tag_listing')
        self.assertEqual(delete.clauses, ['build_id=%(id)i'])
        self.assertEqual(delete.values, {'id': self.binfo['build_id']})

        self.get_build.assert_has_calls([mock.call(self.build_id),
                                         mock.call(self.build_id, strict=True)])

    def test_reset_build_non_exist_build(self):
        self.get_build.return_value = None
        rv = kojihub.reset_build(3)
        self.assertEqual(rv, None)
        self.assertEqual(len(self.queries), 0)
        self.assertEqual(len(self.deletes), 0)
        self.assertEqual(len(self.updates), 0)
