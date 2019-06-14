from __future__ import absolute_import
import datetime
import locale
try:
    import unittest2 as unittest
except ImportError:
    import unittest

import six.moves.xmlrpc_client as xmlrpc_client

from koji import formatTime, formatTimeLong

class TestFormatTime(unittest.TestCase):
    def test_format_time(self):
        self.assertEqual(formatTime(None), '')
        self.assertEqual(formatTime(''), '')

        desired = '2017-10-05 09:52:31'
        # datetime
        d = datetime.datetime(year=2017, month=10, day=5, hour=9, minute=52, second=31, microsecond=12)
        self.assertEqual(formatTime(d), desired)

        # DateTime
        d1 = xmlrpc_client.DateTime(d)
        self.assertEqual(formatTime(d1), desired)

        # str
        self.assertEqual(formatTime(desired), desired)

        # str + microseconds
        self.assertEqual(formatTime(desired + '.123'), desired)

    def test_format_time_long(self):
        # force locale to compare 'desired' value
        locale.setlocale(locale.LC_ALL, ('en_US', 'UTF-8'))

        self.assertEqual(formatTimeLong(None), '')
        self.assertEqual(formatTimeLong(''), '')

        desired = 'Thu, 05 Oct 2017 09:52:31'

        # datetime
        d = datetime.datetime(year=2017, month=10, day=5, hour=9, minute=52, second=31, microsecond=12)
        r = formatTimeLong(d)
        r = r[:r.rfind(' ')]
        self.assertEqual(r, desired)

        # DateTime
        d1 = xmlrpc_client.DateTime(d)
        r = formatTimeLong(d1)
        r = r[:r.rfind(' ')]
        self.assertEqual(r, desired)

        # str
        d2 = '2017-10-05 09:52:31'
        r = formatTimeLong(d2)
        r = r[:r.rfind(' ')]
        self.assertEqual(r, desired)

        # str + microseconds
        r = formatTimeLong(d2 + '.123')
        r = r[:r.rfind(' ')]
        self.assertEqual(r, desired)

        locale.resetlocale()
