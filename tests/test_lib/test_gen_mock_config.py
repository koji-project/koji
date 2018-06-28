from __future__ import absolute_import
import ast
import os
import os.path
try:
    import unittest2 as unittest
except ImportError:
    import unittest

import koji


class TestGenMockConfig(unittest.TestCase):

    maxDiff = None

    def test_gen_mock_config(self):
        datadir = os.path.join(os.path.dirname(__file__), 'data/mock')
        count = 0
        for fn in os.listdir(datadir):
            if not fn.endswith('.data'):
                continue
            path = os.path.join(datadir, fn)
            with open(path) as fo:
                s = fo.read()
                params = ast.literal_eval(s)
            with open(path[:-5] + '.out') as fo:
                expected = fo.read()
            output = koji.genMockConfig(**params)
            self.assertMultiLineEqual(output, expected)
            count += 1
        if not count:
            raise Exception('no test data found')

