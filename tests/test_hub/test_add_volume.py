import unittest

import mock

import koji
import kojihub


class TestAddVolume(unittest.TestCase):

    def setUp(self):
        self.verify_name_internal = mock.patch('kojihub.kojihub.verify_name_internal').start()
        self.context = mock.patch('kojihub.kojihub.context').start()
        # It seems MagicMock will not automatically handle attributes that
        # start with "assert"
        self.context.session.assertPerm = mock.MagicMock()
        self.context.session.assertLogin = mock.MagicMock()

    def test_add_volume_wrong_format(self):
        volume_name = 'volume-name+'

        # name is longer as expected
        self.verify_name_internal.side_effect = koji.GenericError
        with self.assertRaises(koji.GenericError):
            kojihub.add_volume(volume_name)

        # not except regex rules
        self.verify_name_internal.side_effect = koji.GenericError
        with self.assertRaises(koji.GenericError):
            kojihub.add_volume(volume_name)
