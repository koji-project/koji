import unittest
from unittest import mock

import kojihub

QP = kojihub.QueryProcessor


class TestCreateRPMChecksum(unittest.TestCase):
    def setUp(self):
        self.maxDiff = None
        self.QueryProcessor = mock.patch('kojihub.kojihub.QueryProcessor',
                                         side_effect=self.getQuery).start()
        self.queries = []
        self.query_execute = mock.MagicMock()

    def tearDown(self):
        mock.patch.stopall()

    def getQuery(self, *args, **kwargs):
        query = QP(*args, **kwargs)
        query.execute = self.query_execute
        self.queries.append(query)
        return query

    def test_checksum_exists(self):
        rpm_id = 123
        chsum_dict = {'md5': 'chsum-1', 'sha256': 'chsum-2'}
        sigkey = 'test-sigkey'
        self.query_execute.return_value = [{'checksum_type': 'md5'}, {'checksum_type': 'sha256'}]
        result = kojihub.create_rpm_checksum(rpm_id, sigkey, chsum_dict)
        self.assertIsNone(result)

        self.assertEqual(len(self.queries), 1)
        query = self.queries[0]
        self.assertEqual(query.tables, ['rpm_checksum'])
        self.assertEqual(query.joins, None)
        self.assertEqual(set(query.clauses), {"checksum_type IN %(checksum_types)s",
                                              "sigkey=%(sigkey)s", "rpm_id = %(rpm_id)d"})
