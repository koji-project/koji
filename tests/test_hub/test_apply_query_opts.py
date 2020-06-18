import copy
import unittest
from nose.tools import eq_

import kojihub


class TestApplyQueryOpts(unittest.TestCase):
    def setUp(self):
        self.original = [
            {'foo': 1, 'bar': 1},
            {'foo': 2, 'bar': -1},
            {'foo': 0, 'bar': 0},
        ]
    def test_basic(self):
        opts = None
        expected = copy.copy(self.original)
        actual = kojihub._applyQueryOpts(self.original, opts)
        eq_(expected, actual)

    def test_order_by_foo(self):
        opts = {'order': 'foo'}
        expected = [
            {'foo': 0, 'bar': 0},
            {'foo': 1, 'bar': 1},
            {'foo': 2, 'bar': -1},
        ]
        actual = kojihub._applyQueryOpts(self.original, opts)
        eq_(expected, actual)

    def test_order_by_bar(self):
        opts = {'order': 'bar'}
        expected = [
            {'foo': 2, 'bar': -1},
            {'foo': 0, 'bar': 0},
            {'foo': 1, 'bar': 1},
        ]
        actual = kojihub._applyQueryOpts(self.original, opts)
        eq_(expected, actual)

    def test_order_in_reverse(self):
        opts = {'order': '-foo'}
        expected = [
            {'foo': 2, 'bar': -1},
            {'foo': 1, 'bar': 1},
            {'foo': 0, 'bar': 0},
        ]
        actual = kojihub._applyQueryOpts(self.original, opts)
        eq_(expected, actual)

    def test_offset(self):
        opts = {'offset': 1}
        expected = [
            {'foo': 2, 'bar': -1},
            {'foo': 0, 'bar': 0},
        ]
        actual = kojihub._applyQueryOpts(self.original, opts)
        eq_(expected, actual)

    def test_limit(self):
        opts = {'limit': 2}
        expected = [
            {'foo': 1, 'bar': 1},
            {'foo': 2, 'bar': -1},
        ]
        actual = kojihub._applyQueryOpts(self.original, opts)
        eq_(expected, actual)

    def test_limit_and_offset(self):
        opts = {'limit': 1, 'offset': 1}
        expected = [
            {'foo': 2, 'bar': -1},
        ]
        actual = kojihub._applyQueryOpts(self.original, opts)
        eq_(expected, actual)

    def test_count_only(self):
        opts = {'countOnly': True}
        expected = 3
        actual = kojihub._applyQueryOpts(self.original, opts)
        eq_(expected, actual)

        opts = {'countOnly': True, 'offset': 2}
        expected = 1
        actual = kojihub._applyQueryOpts(self.original, opts)
        eq_(expected, actual)
