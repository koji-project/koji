import mock
import unittest

import koji
from .loadwebindex import webidx
from koji.server import ServerRedirect


class TestTagDelete(unittest.TestCase):
    def setUp(self):
        self.get_server = mock.patch.object(webidx, "_getServer").start()
        self.assert_login = mock.patch.object(webidx, "_assertLogin").start()
        self.server = mock.MagicMock()
        self.environ = {
            'koji.options': {
                'SiteName': 'test',
                'KojiFilesURL': 'https://server.local/files',
            },
            'koji.currentUser': None
        }
        self.tag_id = '1'

    def tearDown(self):
        mock.patch.stopall()

    def test_tagdelete_exception(self):
        """Test tagdelete function raises exception when tag not exists."""
        self.get_server.return_value = self.server
        self.server.getTag.return_value = None

        with self.assertRaises(koji.GenericError) as cm:
            webidx.tagdelete(self.environ, self.tag_id)
        self.assertEqual(str(cm.exception), f'no tag with ID: {self.tag_id}')

    def test_tagdelete_valid(self):
        """Test taskinfo function valid case."""
        self.server.getTag.return_value = {'id': int(self.tag_id)}
        self.server.deleteTag.return_value = None
        self.get_server.return_value = self.server

        with self.assertRaises(ServerRedirect):
            webidx.tagdelete(self.environ, self.tag_id)
        self.server.deleteTag.assert_called_with(int(self.tag_id))
        self.assertEqual(self.environ['koji.redirect'], 'tags')
