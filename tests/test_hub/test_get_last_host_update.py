import datetime
import sys

import kojihub
from .utils import DBQueryTestCase


class TestGetLastHostUpdate(DBQueryTestCase):

    def setUp(self):
        super(TestGetLastHostUpdate, self).setUp()
        self.exports = kojihub.RootExports()

    def test_valid_ts(self):
        expected = 1615875554.862938
        if sys.version_info[1] <= 6:
            dt = datetime.datetime.strptime(
                "2021-03-16T06:19:14.862938+0000", "%Y-%m-%dT%H:%M:%S.%f%z")
        else:
            dt = datetime.datetime.strptime(
                "2021-03-16T06:19:14.862938+00:00", "%Y-%m-%dT%H:%M:%S.%f%z")
        self.qp_single_value_return_value = dt
        rv = self.exports.getLastHostUpdate(1, ts=True)
        self.assertEqual(rv, expected)
        self.assertEqual(len(self.queries), 1)
        query = self.queries[0]
        self.assertEqual(query.tables, ['sessions'])
        self.assertEqual(query.joins, ['host ON sessions.user_id = host.user_id'])
        self.assertEqual(query.clauses, ['host.id = %(hostID)i'])
        self.assertEqual(query.values, {'hostID': 1})
        self.assertEqual(query.columns, ['sessions.update_time'])

    def test_valid_datetime(self):
        if sys.version_info[1] <= 6:
            dt = datetime.datetime.strptime(
                "2021-03-16T06:19:14.862938+0000", "%Y-%m-%dT%H:%M:%S.%f%z")
        else:
            dt = datetime.datetime.strptime(
                "2021-03-16T06:19:14.862938+00:00", "%Y-%m-%dT%H:%M:%S.%f%z")
        self.qp_single_value_return_value = dt
        rv = self.exports.getLastHostUpdate(1)
        self.assertEqual(rv, dt)
