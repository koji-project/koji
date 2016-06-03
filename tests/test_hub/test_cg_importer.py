import unittest
import mock

import kojihub


class TestCGImporter(unittest.TestCase):
    def test_basic_instantiation(self):
        # TODO -- this doesn't make sense.  A query with no arguments should
        # probably raise an exception saying "this doesn't make sense."
        kojihub.CG_Importer()  # No exception!
