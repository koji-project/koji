import mock
import unittest
import koji
import kojihub

UP = kojihub.UpdateProcessor


class TestDeleteTag(unittest.TestCase):

    def getUpdate(self, *args, **kwargs):
        update = UP(*args, **kwargs)
        update.execute = mock.MagicMock()
        self.updates.append(update)
        return update

    def setUp(self):
        self.UpdateProcessor = mock.patch('kojihub.UpdateProcessor',
                                          side_effect=self.getUpdate).start()
        self.updates = []
        self.get_tag = mock.patch('kojihub.get_tag').start()
        self.context = mock.patch('kojihub.context').start()
        # It seems MagicMock will not automatically handle attributes that
        # start with "assert"
        self.context.session.assertPerm = mock.MagicMock()
        self.context.session.assertLogin = mock.MagicMock()

    def tearDown(self):
        mock.patch.stopall()

    def test_bad_tag(self):
        self.get_tag.side_effect = koji.GenericError("FOO")
        with self.assertRaises(koji.GenericError):
            kojihub.delete_tag('badtag')
        self.assertEqual(self.updates, [])
        self.context.session.assertPerm.assert_called_with('tag')

    def test_good_tag(self):
        self.get_tag.return_value = {'id': 'TAGID'}
        self.context.event_id = "12345"
        self.context.session.user_id = "42"
        data = {'revoker_id': '42', 'revoke_event': '12345'}
        kojihub.delete_tag('goodtag')
        for u in self.updates:
            # all should be revokes
            self.assertEqual(u.values, {'value': 'TAGID'})
            self.assertEqual(u.rawdata, {'active': 'NULL'})
            self.assertEqual(u.data, data)
        self.context.session.assertPerm.assert_called_with('tag')
