import unittest
import mock

import koji
import kojihub


class TestWriteSignedRPM(unittest.TestCase):
    def setUp(self):
        self.context = mock.patch('kojihub.kojihub.context').start()
        self.get_rpm = mock.patch('kojihub.kojihub.get_rpm').start()

    def tearDown(self):
        mock.patch.stopall()

    def test_write_signed_rpm_not_internal_rpm(self):
        sigkey = 'test-sigkey'
        rpm_id = 1
        rpminfo = {'external_repo_id': 1, 'external_repo_name': 'test-external-repo'}
        self.get_rpm.return_value = rpminfo
        with self.assertRaises(koji.GenericError) as cm:
            kojihub.write_signed_rpm(rpm_id, sigkey)
        self.assertEqual(f"Not an internal rpm: {rpm_id} (from {rpminfo['external_repo_name']})",
                         str(cm.exception))
