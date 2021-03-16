import unittest
import mock
import datetime
import sys

import kojihub


class TestGetLastHostUpdate(unittest.TestCase):

    def setUp(self):
        self.exports = kojihub.RootExports()

    @mock.patch('kojihub._singleValue')
    def test_valid_ts(self, _singleValue):
        expected = 1615875554.862938
        if sys.version_info[1] <= 6:
            dt = datetime.datetime.strptime(
                "2021-03-16T06:19:14.862938+0000", "%Y-%m-%dT%H:%M:%S.%f%z")
        else:
            dt = datetime.datetime.strptime(
                "2021-03-16T06:19:14.862938+00:00", "%Y-%m-%dT%H:%M:%S.%f%z")
        _singleValue.return_value = dt
        rv = self.exports.getLastHostUpdate(1, ts=True)
        self.assertEqual(rv, expected)

    @mock.patch('kojihub._singleValue')
    def test_valid_datetime(self, _singleValue):
        if sys.version_info[1] <= 6:
            dt = datetime.datetime.strptime(
                "2021-03-16T06:19:14.862938+0000", "%Y-%m-%dT%H:%M:%S.%f%z")
        else:
            dt = datetime.datetime.strptime(
                "2021-03-16T06:19:14.862938+00:00", "%Y-%m-%dT%H:%M:%S.%f%z")
            expected = "2021-03-16T06:19:14.862938+00:00"
        _singleValue.return_value = dt
        rv = self.exports.getLastHostUpdate(1)
        self.assertEqual(rv, dt)
