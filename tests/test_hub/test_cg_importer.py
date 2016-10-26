import unittest
import mock
import os
import shutil

import koji
import kojihub
from koji import GenericError


class TestCGImporter(unittest.TestCase):
    TMP_PATH = os.path.join(os.path.dirname(__file__), 'tmptest')

    def setUp(self):
        if not os.path.exists(self.TMP_PATH):
            os.mkdir(self.TMP_PATH)

    def tearDown(self):
        if os.path.exists(self.TMP_PATH):
            shutil.rmtree(self.TMP_PATH)

    def test_basic_instantiation(self):
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

    @mock.patch('kojihub.context')
    @mock.patch("koji.pathinfo.work")
    def test_assert_cg_access(self, work, context):
        work.return_value = os.path.dirname(__file__)
        cursor = mock.MagicMock()
        context.session.user_id = 42
        context.cnx.cursor.return_value = cursor
        cursor.fetchall.return_value = [(1, 'foo'), (2, 'bar')]
        x = kojihub.CG_Importer()
        x.get_metadata('default.json', 'cg_importer_json')
        x.assert_cg_access()
        assert x.cgs
        assert isinstance(x.cgs, set)

    @mock.patch('kojihub.context')
    @mock.patch("koji.pathinfo.work")
    def test_prep_build(self, work, context):
        work.return_value = os.path.dirname(__file__)
        cursor = mock.MagicMock()
        context.cnx.cursor.return_value = cursor
        x = kojihub.CG_Importer()
        x.get_metadata('default.json', 'cg_importer_json')
        x.prep_build()
        assert x.buildinfo
        assert isinstance(x.buildinfo, dict)

    @mock.patch('kojihub.get_build')
    @mock.patch("koji.pathinfo.work")
    def test_prep_build_exists(self, work, get_build):
        work.return_value = os.path.dirname(__file__)
        get_build.return_value = True
        x = kojihub.CG_Importer()
        x.get_metadata('default.json', 'cg_importer_json')
        with self.assertRaises(GenericError):
            x.prep_build()

    @mock.patch('kojihub.get_build')
    @mock.patch('kojihub.new_build')
    @mock.patch('kojihub.context')
    @mock.patch("koji.pathinfo.work")
    def test_get_build(self, work, context, new_build_id, get_build):
        work.return_value = os.path.dirname(__file__)
        cursor = mock.MagicMock()
        context.cnx.cursor.return_value = cursor
        new_build_id.return_value = 42
        get_build.return_value = False
        x = kojihub.CG_Importer()
        x.get_metadata('default.json', 'cg_importer_json')
        x.prep_build()
        x.prepped_outputs = []
        get_build.return_value = {'id': 43, 'package_id': 1,
                                  'package_name': 'testpkg',
                                  'name': 'testpkg', 'version': '1.0.1e',
                                  'release': '42.el7', 'epoch': None,
                                  'nvr': 'testpkg-1.0.1-1.fc24',
                                  'state': 'complete', 'task_id': 1,
                                  'owner_id': 1, 'owner_name': 'jvasallo',
                                  'volume_id': 'id-1212', 'volume_name': 'testvolume',
                                  'creation_event_id': '', 'creation_time': '',
                                  'creation_ts': 424242424242,
                                  'start_time': None, 'start_ts': None,
                                  'completion_time': None, 'completion_ts': None,
                                  'source': 'https://example.com', 'extra': {}
                                 }
        new_build_id.return_value = 43
        x.get_build()
        assert x.buildinfo
        assert isinstance(x.buildinfo, dict)

    @mock.patch("koji.pathinfo.build")
    @mock.patch("koji.pathinfo.work")
    def test_import_metadata(self, work, build):
        work.return_value = os.path.dirname(__file__)
        build.return_value = self.TMP_PATH
        x = kojihub.CG_Importer()
        x.get_metadata('default.json', 'cg_importer_json')
        x.import_metadata()
