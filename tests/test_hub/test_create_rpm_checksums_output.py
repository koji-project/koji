import unittest

import kojihub


class TestCreateRPMChecksumsOutput(unittest.TestCase):
    def setUp(self):
        self.maxDiff = None
        self.exports = kojihub.RootExports()

    def test_cacheonly_all_exists(self):
        expected_result = {'sigkey1': {'md5': 'checksum-md5', 'sha256': 'checksum-sha256'},
                           'sigkey2': {'md5': 'checksum-md5', 'sha256': 'checksum-sha256'}}
        query_result = [{'checksum': 'checksum-md5', 'checksum_type': 0, 'sigkey': 'sigkey1'},
                        {'checksum': 'checksum-sha256', 'checksum_type': 2, 'sigkey': 'sigkey1'},
                        {'checksum': 'checksum-md5', 'checksum_type': 0, 'sigkey': 'sigkey2'},
                        {'checksum': 'checksum-sha256', 'checksum_type': 2, 'sigkey': 'sigkey2'}]
        checksum_types = {'sigkey1': {'md5', 'sha256'},
                          'sigkey2': {'md5', 'sha256'}
                          }

        result = kojihub.create_rpm_checksums_output(query_result, checksum_types)
        self.assertEqual(expected_result, result)

    def test_cacheonly_some_exists(self):
        expected_result = {'sigkey1': {'md5': 'checksum-md5', 'sha256': None},
                           'sigkey2': {'md5': None, 'sha256': 'checksum-sha256'}}
        query_result = [{'checksum': 'checksum-md5', 'checksum_type': 0, 'sigkey': 'sigkey1'},
                        {'checksum': 'checksum-sha256', 'checksum_type': 2, 'sigkey': 'sigkey2'}]
        checksum_types = {'sigkey1': {'md5', 'sha256'},
                          'sigkey2': {'md5', 'sha256'}
                          }
        result = kojihub.create_rpm_checksums_output(query_result, checksum_types)
        self.assertEqual(expected_result, result)
