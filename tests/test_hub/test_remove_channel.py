import unittest

import mock

import koji
import kojihub

UP = kojihub.UpdateProcessor


class TestRemoveChannel(unittest.TestCase):
    def getUpdate(self, *args, **kwargs):
        update = UP(*args, **kwargs)
        update.execute = mock.MagicMock()
        self.updates.append(update)
        return update

    def setUp(self):
        self.UpdateProcessor = mock.patch('kojihub.UpdateProcessor',
                                          side_effect=self.getUpdate).start()
        self.updates = []
        self.context = mock.patch('kojihub.context').start()
        self.context.session.assertPerm = mock.MagicMock()
        self.exports = kojihub.RootExports()
        self.channel_name = 'test-channel'

    def tearDown(self):
        mock.patch.stopall()

    @mock.patch('kojihub.get_channel_id')
    def test_non_exist_channel(self, get_channel_id):
        get_channel_id.side_effect = koji.GenericError('No such channel: %s' % self.channel_name)

        with self.assertRaises(koji.GenericError):
            kojihub.remove_channel(self.channel_name)

        get_channel_id.assert_called_once_with(self.channel_name, strict=True)
        self.assertEqual(len(self.updates), 0)
