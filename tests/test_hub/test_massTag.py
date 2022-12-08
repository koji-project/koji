import mock
import unittest
import koji
import kojihub


class TestDeleteEventId(unittest.TestCase):
    @mock.patch('kojihub.kojihub.context')
    def test_delete_event_id(self, context):
        kojihub.context.event_id = 123
        kojihub._delete_event_id()
        self.assertFalse(hasattr(context, 'event_id'))

    @mock.patch('kojihub.kojihub.context')
    def test_delete_event_id_none(self, context):
        kojihub._delete_event_id()
        self.assertFalse(hasattr(context, 'event_id'))


class TestMassTag(unittest.TestCase):
    def setUp(self):
        self.get_tag = mock.patch('kojihub.kojihub.get_tag').start()
        self.get_build = mock.patch('kojihub.kojihub.get_build').start()
        self.get_user = mock.patch('kojihub.kojihub.get_user').start()
        self._direct_tag_build = mock.patch('kojihub.kojihub._direct_tag_build').start()
        self._delete_event_id = mock.patch('kojihub.kojihub._delete_event_id').start()
        self.context = mock.patch('kojihub.kojihub.context').start()
        self.context.session.assertPerm = mock.MagicMock()
        self.hub = kojihub.RootExports()

    def tearDown(self):
        mock.patch.stopall()

    def test_no_permission(self):
        self.context.session.assertPerm.side_effect = koji.ActionNotAllowed
        with self.assertRaises(koji.ActionNotAllowed):
            self.hub.massTag('tag', ['n-v-r1'])
        self.context.session.assertPerm.assert_called_once_with('tag')

    def test_non_existent_tag(self):
        self.hub.massTag('non-existent-tag', ['n-v-r-1', 'n-v-r-2'])

    def test_non_existent_build(self):
        self.hub.massTag('tag', ['non-existent-nvr'])

    def test_correct_tagging_mixed_build_id_nvr(self):
        self.hub.massTag('tag', ['n-v-r1', 123])

    def test_correct_tagging_tag_id(self):
        self.hub.massTag(1234, ['n-v-r1', 123])

    def test_correct_tagging_tag_dict(self):
        self.hub.massTag({'id': 1234, 'name': 'tag'}, ['n-v-r1', 123])
