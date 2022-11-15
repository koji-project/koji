import unittest
import mock
import datetime
import sys

import kojihub

QP = kojihub.QueryProcessor


class TestGetLastHostUpdate(unittest.TestCase):
    def getQuery(self, *args, **kwargs):
        query = QP(*args, **kwargs)
        query.singleValue = self.query_singleValue
        self.queries.append(query)
        return query

    def setUp(self):
        self.exports = kojihub.RootExports()
        self.QueryProcessor = mock.patch('kojihub.QueryProcessor',
                                         side_effect=self.getQuery).start()
        self.queries = []
        self.query_singleValue = mock.MagicMock()

    def test_valid_ts(self):
        expected = 1615875554.862938
        if sys.version_info[1] <= 6:
            dt = datetime.datetime.strptime(
                "2021-03-16T06:19:14.862938+0000", "%Y-%m-%dT%H:%M:%S.%f%z")
        else:
            dt = datetime.datetime.strptime(
                "2021-03-16T06:19:14.862938+00:00", "%Y-%m-%dT%H:%M:%S.%f%z")
        self.query_singleValue.return_value = dt
        rv = self.exports.getLastHostUpdate(1, ts=True)
        self.assertEqual(rv, expected)

    def test_valid_datetime(self):
        if sys.version_info[1] <= 6:
            dt = datetime.datetime.strptime(
                "2021-03-16T06:19:14.862938+0000", "%Y-%m-%dT%H:%M:%S.%f%z")
        else:
            dt = datetime.datetime.strptime(
                "2021-03-16T06:19:14.862938+00:00", "%Y-%m-%dT%H:%M:%S.%f%z")
        self.query_singleValue.return_value = dt
        rv = self.exports.getLastHostUpdate(1)
        self.assertEqual(rv, dt)
