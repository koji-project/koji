import mock

import koji
import kojihub
from .utils import DBQueryTestCase


class TestGetBuild(DBQueryTestCase):

    def setUp(self):
        super(TestGetBuild, self).setUp()
        self.find_build_id = mock.patch('kojihub.kojihub.find_build_id').start()

    def test_non_exist_build_string(self):
        build = 'build-1-23'
        self.find_build_id.side_effect = koji.GenericError('No such build: %s' % build)
        with self.assertRaises(koji.GenericError) as cm:
            kojihub.get_build(build, strict=True)
        self.assertEqual('No such build: %s' % build, str(cm.exception))

    def test_non_exist_build_int(self):
        build = 11
        self.find_build_id.return_value = build
        with self.assertRaises(koji.GenericError) as cm:
            kojihub.get_build(build, strict=True)
        self.assertEqual('No such build: %s' % build, str(cm.exception))

    def test_non_exist_build_dict(self):
        build = {
            'name': 'test_name',
            'version': 'test_version',
            'release': 'test_release',
        }
        self.find_build_id.side_effect = koji.GenericError('No such build: %s' % build['name'])
        with self.assertRaises(koji.GenericError) as cm:
            kojihub.get_build(build, strict=True)
        self.assertEqual('No such build: %s' % build['name'], str(cm.exception))
