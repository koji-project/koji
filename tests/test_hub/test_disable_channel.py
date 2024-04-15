import unittest

import mock

import koji
import kojihub

UP = kojihub.UpdateProcessor


class TestDisableChannel(unittest.TestCase):

    def getUpdate(self, *args, **kwargs):
        update = UP(*args, **kwargs)
        update.execute = mock.MagicMock()
        self.updates.append(update)
        return update

    def setUp(self):
        self.exports = kojihub.RootExports()
        self.get_channel = mock.patch('kojihub.kojihub.get_channel').start()
        self.UpdateProcessor = mock.patch('kojihub.kojihub.UpdateProcessor',
                                          side_effect=self.getUpdate).start()
        self.updates = []
        self.channelname = 'test-channel'

    def tearDown(self):
        mock.patch.stopall()

    def test_non_exist_channel(self):
        self.get_channel.return_value = None
        with self.assertRaises(koji.GenericError) as cm:
            self.exports.disableChannel(self.channelname)
        self.assertEqual(f"No such channel: {self.channelname}", str(cm.exception))

    def test_wrong_type_channel(self):
        comment = ['test-comment']
        with self.assertRaises(koji.GenericError) as cm:
            self.exports.disableChannel(self.channelname, comment=comment)
        self.assertEqual(f"Invalid type for value '{comment}': {type(comment)}, "
                         f"expected type <class 'str'>", str(cm.exception))

    def test_valid(self):
        self.get_channel.return_value = {'comment': None, 'description': None,
                                         'enabled': True, 'id': 1, 'name': 'test-channel'}
        self.exports.disableChannel(self.channelname, comment='test-comment')
        self.assertEqual(len(self.updates), 1)
        update = self.updates[0]
        self.assertEqual(update.table, 'channels')
        self.assertEqual(update.data, {'comment': 'test-comment', 'enabled': False})
        self.assertEqual(update.values, {'comment': None, 'description': None, 'enabled': True,
                                         'id': 1, 'name': 'test-channel'})
        self.assertEqual(update.clauses, ['id = %(id)i'])
