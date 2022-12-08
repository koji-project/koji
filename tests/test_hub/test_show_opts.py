import mock
import unittest

import re
import kojihub

UP = kojihub.UpdateProcessor
IP = kojihub.InsertProcessor


class TestShowOpts(unittest.TestCase):
    def setUp(self):
        self.maxDiff = None
        self.context = mock.patch('kojihub.kojihub.context').start()
        self.context.session.assertPerm = mock.MagicMock()
        self.exports = kojihub.RootExports()
        self.context.opts = {'MaxNameLengthInternal': 15,
                             'RegexNameInternal.compiled': re.compile('^[A-Za-z0-9/_.+-]+$')}

    def tearDown(self):
        mock.patch.stopall()

    def test_as_string(self):
        rv = self.exports.showOpts()
        self.assertEqual(rv, "{'MaxNameLengthInternal': 15, "
                             "'RegexNameInternal.compiled': re.compile('^[A-Za-z0-9/_.+-]+$')}")

    def test_as_dict(self):
        rv = self.exports.showOpts(as_string=False)
        self.assertEqual(rv, {'MaxNameLengthInternal': 15,
                              'RegexNameInternal.compiled': re.compile('^[A-Za-z0-9/_.+-]+$')})
