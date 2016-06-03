import unittest
import mock
import os

import koji
import kojihub
from koji import GenericError


class TestCGImporter(unittest.TestCase):
    def test_basic_instantiation(self):
        # TODO -- this doesn't make sense.  A query with no arguments should
        # probably raise an exception saying "this doesn't make sense."
        kojihub.CG_Importer()  # No exception!

    def test_get_metadata_is_instance(self):
        mock_input_val = {'foo': 'bar'}
        x = kojihub.CG_Importer()
        x.get_metadata(mock_input_val, '')
        assert x.raw_metadata
        assert isinstance(x.raw_metadata, str)

    def test_get_metadata_is_not_instance(self):
        x = kojihub.CG_Importer()
        with self.assertRaises(GenericError):
            x.get_metadata(42, '')

    def test_get_metadata_is_none(self):
        x = kojihub.CG_Importer()
        with self.assertRaises(GenericError):
            x.get_metadata(None, '')

    @mock.patch("koji.pathinfo.work")
    def test_get_metadata_missing_json_file(self, work):
        work.return_value = os.path.dirname(__file__)
        x = kojihub.CG_Importer()
        with self.assertRaises(GenericError):
            x.get_metadata('missing.json', 'cg_importer_json')

    @mock.patch("koji.pathinfo.work")
    def test_get_metadata_is_json_file(self, work):
        work.return_value = os.path.dirname(__file__)
        x = kojihub.CG_Importer()
        x.get_metadata('default.json', 'cg_importer_json')
        assert x.raw_metadata
        assert isinstance(x.raw_metadata, str)
