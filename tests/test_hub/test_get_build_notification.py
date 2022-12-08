import mock
import unittest
import koji
import kojihub


class TestGetBuildNotification(unittest.TestCase):

    def setUp(self):
        self.QueryProcessor = mock.patch('kojihub.kojihub.QueryProcessor').start()
        self.query = self.QueryProcessor.return_value
        self.exports = kojihub.RootExports()

    def tearDown(self):
        mock.patch.stopall()

    def test_empty_result_with_strict(self):
        notif_id = 1
        self.query.executeOne.return_value = None
        with self.assertRaises(koji.GenericError) as cm:
            self.exports.getBuildNotification(notif_id, strict=True)
        self.assertEqual(f"No notification with ID {notif_id} found", str(cm.exception))
