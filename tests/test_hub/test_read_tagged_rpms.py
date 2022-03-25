import unittest

import mock

import koji
import kojihub


class TestReadTaggedRPMS(unittest.TestCase):

    def setUp(self):
        self.context = mock.patch('kojihub.context').start()
        # It seems MagicMock will not automatically handle attributes that
        # start with "assert"
        self.exports = kojihub.RootExports()
        self.readTaggedBuilds = mock.patch('kojihub.readTaggedBuilds').start()
        self.tag_name = 'test-tag'
        self.build_list = [
            {'build_id': 1, 'create_event': 1172, 'creation_event_id': 1171, 'epoch': None,
             'id': 1, 'name': 'test-pkg', 'nvr': 'test-pkg-2.52-1.fc35', 'owner_id': 1,
             'owner_name': 'kojiuser', 'package_id': 1, 'package_name': 'test-pkg',
             'release': '1.fc35', 'state': 1, 'tag_id': 1, 'tag_name': 'test-tag',
             'task_id': None, 'version': '2.52', 'volume_id': 0, 'volume_name': 'DEFAULT'}]

    def tearDown(self):
        mock.patch.stopall()

    def test_get_tagged_rpms_rpmsigs_arch_type_error(self):
        self.readTaggedBuilds.return_value = self.build_list
        error_message = 'Invalid type for arch option: %s' % type(1245)
        with self.assertRaises(koji.GenericError) as cm:
            kojihub.readTaggedRPMS(self.tag_name, arch=1245)
        self.assertEqual(error_message, str(cm.exception))
