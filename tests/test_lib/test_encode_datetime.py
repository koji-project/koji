from __future__ import absolute_import
import datetime
try:
    import unittest2 as unittest
except ImportError:
    import unittest

import koji.util
from koji.xmlrpcplus import DateTime


class testEncodeDatetime(unittest.TestCase):

    DATES = [
            [datetime.datetime(2001, 2, 3, 9, 45, 32),
                '2001-02-03 09:45:32'],
            [datetime.datetime(1970, 1, 1, 0, 0),
                '1970-01-01 00:00:00'],
            [datetime.datetime(2017, 8, 3, 10, 19, 39, 474556),
                '2017-08-03 10:19:39.474556'],
          ]

    def test_simple_dates(self):
        for dt, dstr in self.DATES:
            chk1 = koji.util.encode_datetime(dt)
            chk2 = koji.util.encode_datetime_recurse(dt)
            self.assertEqual(chk1, dstr)
            self.assertEqual(chk2, dstr)

    def test_xmlrpc_dates(self):
        # we skip the last because xmlrpc's DateTime class does not preserve
        # fractions of seconds
        for dt, dstr in self.DATES[:2]:
            dt = DateTime(dt)
            chk1 = koji.util.encode_datetime(dt)
            chk2 = koji.util.encode_datetime_recurse(dt)
            self.assertEqual(chk1, dstr)
            self.assertEqual(chk2, dstr)

    def test_embedded_dates(self):
        dt1, ds1 = self.DATES[0]
        dt2, ds2 = self.DATES[1]
        dt3, ds3 = self.DATES[2]
        data1 = [1, "2", [3, dt1], {"4": dt2}, [[[[{"five": dt3}]]]]]
        fix_1 = [1, "2", [3, ds1], {"4": ds2}, [[[[{"five": ds3}]]]]]
        data2 = {1: dt1, "2": [dt2, dt1], "three": {"3": {3: dt3}}}
        fix_2 = {1: ds1, "2": [ds2, ds1], "three": {"3": {3: ds3}}}
        chk1 = koji.util.encode_datetime_recurse(data1)
        chk2 = koji.util.encode_datetime_recurse(data2)
        self.assertEqual(chk1, fix_1)
        self.assertEqual(chk2, fix_2)
