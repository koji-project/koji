from __future__ import absolute_import
import datetime
import os
import time
import locale
try:
    import unittest2 as unittest
except ImportError:
    import unittest

import six.moves.xmlrpc_client as xmlrpc_client

from koji import formatTime, formatTimeLong

class TestFormatTime(unittest.TestCase):
    def setUp(self):
        self._orig_tz = os.environ.get('TZ')

    def tearDown(self):
        if self._orig_tz:
            os.environ['TZ'] = self._orig_tz
        elif 'TZ' in os.environ:
            del os.environ['TZ']
        time.tzset()

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
        os.environ['TZ'] = 'GMT'
        time.tzset()

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

        # str + timezone
        d3 = '2017-10-05 09:52:31+02:00'
        desired = 'Thu, 05 Oct 2017 07:52:31 GMT'
        os.environ['TZ'] = 'GMT'
        time.tzset()
        r = formatTimeLong(d3)
        self.assertEqual(r, desired)

        # non-GMT without DST
        d3 = '2017-06-05 09:52:31+02:00'
        desired = 'Mon, 05 Jun 2017 09:52:31 CEST'
        os.environ['TZ'] = 'Europe/Prague'
        time.tzset()
        r = formatTimeLong(d3)
        self.assertEqual(r, desired)

        # non-GMT with DST
        d3 = '2017-12-05 09:52:31+02:00'
        desired = 'Tue, 05 Dec 2017 08:52:31 CET'
        os.environ['TZ'] = 'Europe/Prague'
        time.tzset()
        r = formatTimeLong(d3)
        self.assertEqual(r, desired)

        # timestamps, local timezone
        d4 = 0
        desired = 'Thu, 01 Jan 1970 01:00:00 CET'
        r = formatTimeLong(d4)
        self.assertEqual(r, desired)

        # timestamps, GMT
        desired = 'Thu, 01 Jan 1970 00:00:00 GMT'
        os.environ['TZ'] = 'GMT'
        time.tzset()
        r = formatTimeLong(d4)
        self.assertEqual(r, desired)

        locale.resetlocale()
