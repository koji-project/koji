from unittest import mock
import os
import shutil
import tempfile
import unittest

import koji
import kojihub
from koji import GenericError

IP = kojihub.InsertProcessor
UP = kojihub.UpdateProcessor


class TestCGImporter(unittest.TestCase):

    DATADIR = os.path.join(os.path.dirname(__file__), 'data', 'cg_importer')

    def setUp(self):
        self.tempdir = tempfile.mkdtemp()
        self.pathinfo = koji.PathInfo(self.tempdir)
        mock.patch('koji.pathinfo', new=self.pathinfo).start()
        self.context_db = mock.patch('kojihub.db.context').start()
        self.context = mock.patch('kojihub.kojihub.context').start()
        self.get_build = mock.patch('kojihub.kojihub.get_build').start()
        self.get_user = mock.patch('kojihub.kojihub.get_user').start()
        self.userinfo = {'id': 123}
        self.rmtree = mock.patch('koji.util.rmtree').start()
        self.lexists = mock.patch('os.path.lexists').start()
        self.new_build = mock.patch('kojihub.kojihub.new_build').start()
        self.buildinfo = {
            'id': 43,
            'package_id': 1,
            'package_name': 'testpkg',
            'name': 'testpkg',
            'version': '1.0.1e',
            'release': '42.el7',
            'epoch': None,
            'nvr': 'testpkg-1.0.1-1.fc24',
            'state': koji.BUILD_STATES['COMPLETE'],
            'task_id': 1,
            'owner_id': 1,
            'owner_name': 'jvasallo',
            'volume_id': 'id-1212',
            'volume_name':'testvolume',
            'creation_event_id': '',
            'creation_time': '',
            'creation_ts': 424242424242,
            'start_time': None,
            'start_ts': None,
            'completion_time': None,
            'completion_ts': None,
            'source': 'https://example.com',
            'extra': {},
        }
        upload_dir = os.path.join(self.pathinfo.work(), 'cg_importer_json')
        os.makedirs(upload_dir)
        shutil.copy("%s/default.json" % self.DATADIR, upload_dir)


    def tearDown(self):
        mock.patch.stopall()
        shutil.rmtree(self.tempdir)

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
        metadata = 42
        with self.assertRaises(GenericError) as ex:
            x.get_metadata(metadata, '')
        self.assertEqual(f"Invalid type for value '{metadata}': {type(metadata)}, "
                         f"expected type <class 'str'>", str(ex.exception))

    def test_get_metadata_is_none(self):
        x = kojihub.CG_Importer()
        with self.assertRaises(GenericError) as ex:
            x.get_metadata(None, '')
        self.assertEqual('No such file: metadata.json', str(ex.exception))

    def test_get_metadata_missing_json_file(self):
        x = kojihub.CG_Importer()
        with self.assertRaises(GenericError):
            x.get_metadata('missing.json', 'cg_importer_json')

    def test_get_metadata_is_json_file(self):
        x = kojihub.CG_Importer()
        x.get_metadata('default.json', 'cg_importer_json')
        assert x.raw_metadata
        assert isinstance(x.raw_metadata, str)

    def test_assert_cg_access(self):
        cursor = mock.MagicMock()
        self.context.session.user_id = 42
        self.context_db.cnx.cursor.return_value = cursor
        cursor.fetchall.return_value = [(1, 'foo'), (2, 'bar')]
        x = kojihub.CG_Importer()
        x.get_metadata('default.json', 'cg_importer_json')
        x.assert_cg_access()
        assert x.cg
        assert isinstance(x.cg, int)

    def test_prep_build(self):
        cursor = mock.MagicMock()
        self.context_db.cnx.cursor.return_value = cursor
        cursor.fetchall.return_value = [(1, 'foo'), (2, 'bar')]
        self.get_user.return_value = self.userinfo
        self.get_build.return_value = {}
        x = kojihub.CG_Importer()
        x.get_metadata('default.json', 'cg_importer_json')
        x.assert_cg_access()
        x.prep_build()
        assert x.buildinfo
        assert isinstance(x.buildinfo, dict)

    def test_check_build_dir(self):
        # path = '/random_path/random_dir'

        x = kojihub.CG_Importer()
        x.log_warning = mock.MagicMock()
        x.buildinfo = self.buildinfo
        build_dir = "%s/vol/testvolume/packages/testpkg/1.0.1e/42.el7" % self.tempdir

        # directory exists
        self.lexists.return_value = True
        with self.assertRaises(koji.GenericError):
            x.check_build_dir(delete=False)
        self.rmtree.assert_not_called()
        x.log_warning.assert_not_called()

        # directory exists + delete
        self.lexists.return_value = True
        x.check_build_dir(delete=True)
        self.rmtree.assert_called_once_with(build_dir)
        x.log_warning.assert_called_once_with("Deleting build directory: %s" % build_dir)
        x.log_warning.reset_mock()

        # directory doesn't exist
        self.rmtree.reset_mock()
        self.lexists.return_value = False
        x.check_build_dir()
        self.rmtree.assert_not_called()
        x.log_warning.assert_not_called()

    def test_prep_build_exists(self):
        self.get_build.return_value = self.buildinfo
        x = kojihub.CG_Importer()
        x.get_metadata('default.json', 'cg_importer_json')
        with self.assertRaises(GenericError):
            x.prep_build()

    def test_get_build(self):
        cursor = mock.MagicMock()
        cursor.fetchall.return_value = [(1, 'foo'), (2, 'bar')]
        self.context_db.cnx.cursor.return_value = cursor
        self.new_build.return_value = 42
        self.get_build.return_value = False
        self.get_user.return_value = self.userinfo
        x = kojihub.CG_Importer()
        x.get_metadata('default.json', 'cg_importer_json')
        x.assert_cg_access()
        x.prep_build()
        x.prepped_outputs = []
        self.get_build.return_value = self.buildinfo
        self.new_build.return_value = 43
        x.get_build()
        assert x.buildinfo
        assert isinstance(x.buildinfo, dict)

    def test_import_metadata(self):
        x = kojihub.CG_Importer()
        x.buildinfo = self.buildinfo
        x.get_metadata('default.json', 'cg_importer_json')
        x.import_metadata()

    @mock.patch("kojihub.kojihub.CG_Importer.get_metadata")
    def test_do_import_no_such_metadata(self, get_metadata):
        x = kojihub.CG_Importer()
        metadata = {'metadata_version': 99,
                    'build': {
                        'name': 'f32-build-n2j8',
                        'version': '1.1',
                        'release': '1',
                        'epoch': 0,
                        'owner': 'kojiadmin'}
                    }
        get_metadata.return_value = metadata
        with self.assertRaises(koji.GenericError) as ex:
            x.do_import(metadata, '/test/dir')
        self.assertEqual(f"No such metadata version: {metadata['metadata_version']}",
                         str(ex.exception))

    def test_match_componemt_wrong_component(self):
        x = kojihub.CG_Importer()
        components = [{'type': 'type'}]
        with self.assertRaises(koji.GenericError) as ex:
            x.match_components(components)
        self.assertEqual(f"No such component type: {components[0]['type']}", str(ex.exception))


class TestMatchKojiFile(unittest.TestCase):

    def setUp(self):
        self.importer = kojihub.CG_Importer()
        self.archive1 = {
            'id': 99,
            'build_id': 42,
            'checksum': 'e1f95555eae04b8e1ebdc5555c5555f0',
            'checksum_type': 0,
            'filename': 'foo-bar-3.0.jar',
            'size': 42710,
        }
        self.build1 = {
            'id': 79218,
            'nvr': 'foo-3.0-1',
        }
        self.comp1 = {
            'type': 'kojifile',
            'archive_id': self.archive1['id'],
            'nvr': self.build1['nvr'],
            'filename': self.archive1['filename'],
        }
        self.get_archive = mock.patch('kojihub.kojihub.get_archive').start()
        self.get_build = mock.patch('kojihub.kojihub.get_build').start()

    def tearDown(self):
        mock.patch.stopall()

    def test_match_kojifile_basic(self):
        comp = self.comp1
        self.get_archive.return_value = self.archive1
        self.get_build.return_value = self.build1
        match = self.importer.match_kojifile(comp)
        self.assertEqual(match, self.archive1)
        self.get_build.assert_called_once()

    def test_match_kojifile_missing_fields(self):
        self.get_archive.return_value = self.archive1
        self.get_build.return_value = self.build1
        # nvr missing
        comp = self.comp1.copy()
        del comp['nvr']
        with self.assertRaises(koji.GenericError):
            self.importer.match_kojifile(comp)
        # filename missing
        comp = self.comp1.copy()
        del comp['filename']
        with self.assertRaises(koji.GenericError):
            self.importer.match_kojifile(comp)

    def test_match_kojifile_mismatch(self):
        comp = self.comp1
        comp['filesize'] = 1
        self.get_archive.return_value = self.archive1
        self.get_build.return_value = self.build1
        with self.assertRaises(koji.GenericError):
            self.importer.match_kojifile(comp)


class TestCGReservation(unittest.TestCase):
    def getInsert(self, *args, **kwargs):
        insert = IP(*args, **kwargs)
        insert.execute = mock.MagicMock()
        self.inserts.append(insert)
        return insert

    def getUpdate(self, *args, **kwargs):
        update = UP(*args, **kwargs)
        update.execute = mock.MagicMock()
        self.updates.append(update)
        return update

    def setUp(self):
        self.InsertProcessor = mock.patch('kojihub.kojihub.InsertProcessor',
                                          side_effect=self.getInsert).start()
        self.UpdateProcessor = mock.patch('kojihub.kojihub.UpdateProcessor',
                                          side_effect=self.getUpdate).start()
        self.inserts = []
        self.updates = []

        self.context_db = mock.patch('kojihub.db.context').start()
        self.context_db.session.user_id = 123456
        self.mock_cursor = mock.MagicMock()
        self.context_db.cnx.cursor.return_value = self.mock_cursor
        self.context = mock.patch('kojihub.kojihub.context').start()
        self.get_build = mock.patch('kojihub.kojihub.get_build').start()
        self.get_user = mock.patch('kojihub.kojihub.get_user').start()
        self.userinfo = {'id': 123456, 'name': 'username'}
        self.new_build = mock.patch('kojihub.kojihub.new_build').start()
        self.lookup_name = mock.patch('kojihub.kojihub.lookup_name').start()
        self.assert_cg = mock.patch('kojihub.kojihub.assert_cg').start()
        self.get_reservation_token = mock.patch('kojihub.kojihub.get_reservation_token').start()
        self.run_callbacks = mock.patch('koji.plugin.run_callbacks').start()

    def tearDown(self):
        mock.patch.stopall()

    def test_init_build_ok(self):
        self.assert_cg.return_value = True
        self.lookup_name.return_value = {'id': 21, 'name': 'cg_name'}
        self.get_reservation_token.return_value = None
        self.get_user.return_value = self.userinfo
        self.new_build.return_value = 654
        cg = 'content_generator_name'
        self.mock_cursor.fetchone.side_effect = [
            [333],  # get pkg_id
            [1234],  # get nextval pkg_id
        ]
        self.mock_cursor.fetchall.side_effect = [
            [[]],
        ]

        data = {
            'name': 'pkg_name',
            'version': 'pkg_version',
            'release': 'pkg_release',
            'extra': {},
        }

        kojihub.cg_init_build(cg, data)

        self.lookup_name.assert_called_once_with('content_generator', cg, strict=True)
        self.assert_cg.assert_called_once_with(cg)
        self.assertEqual(1, len(self.inserts))
        insert = self.inserts[0]
        self.assertEqual(insert.table, 'build_reservations')
        self.assertEqual(insert.data['build_id'], 654)
        self.assertTrue('token' in insert.data)
        self.assertEqual(insert.rawdata, {'created': 'NOW()'})

    def test_uninit_build_ok(self):
        self.assert_cg.return_value = True
        build_id = 1122
        cg_id = 888
        cg = 'content_generator_name'
        self.get_build.side_effect = [
            {
                'id': build_id,
                'state': koji.BUILD_STATES['BUILDING'],
                'cg_id': cg_id,
            },
            {
                'id': build_id,
                'state': koji.BUILD_STATES['FAILED'],
                'cg_id': cg_id,
            },
        ]

        token = 'random_token'
        self.get_reservation_token.return_value = {'build_id': build_id, 'token': token}
        self.lookup_name.return_value = {'name': cg, 'id': cg_id}

        kojihub.cg_refund_build(cg, build_id, token)

        self.assert_cg.assert_called_once_with(cg)
        self.get_build.assert_has_calls([
            mock.call(build_id, strict=True),
            mock.call(build_id, strict=True),
        ])
        self.get_reservation_token.assert_called_once_with(build_id)
        self.lookup_name.assert_called_once_with('content_generator', cg, strict=True)

        self.assertEqual(len(self.updates), 1)
        update = self.updates[0]
        self.assertEqual(update.table, 'build')
        self.assertEqual(update.values['id'], build_id)
        self.assertEqual(update.data['state'], koji.BUILD_STATES['FAILED'])
        self.assertEqual(update.rawdata, {'completion_time': 'NOW()'})

        self.run_callbacks.assert_has_calls([
            mock.call('preBuildStateChange', attribute='state',
                      old=koji.BUILD_STATES['BUILDING'],
                      new=koji.BUILD_STATES['FAILED'],
                      info={
                          'state': koji.BUILD_STATES['BUILDING'],
                          'cg_id': cg_id,
                          'id': build_id}
                      ),
            mock.call('postBuildStateChange', attribute='state',
                      old=koji.BUILD_STATES['BUILDING'],
                      new=koji.BUILD_STATES['FAILED'],
                      info={
                          'state': koji.BUILD_STATES['FAILED'],
                          'cg_id': cg_id,
                          'id': build_id}
                      ),
        ])
