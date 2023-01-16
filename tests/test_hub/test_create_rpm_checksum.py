import unittest
import mock
import six

import kojihub

QP = kojihub.QueryProcessor


def mock_open():
    """Return the right patch decorator for open"""
    if six.PY2:
        return mock.patch('__builtin__.open')
    else:
        return mock.patch('builtins.open')


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
        src = 'test-src'
        dst = 'test-dst'
        rpm_id = 123
        chsum_list = {'md5': 'chsum-1', 'sha256': 'chsum-2'}
        sigkey = 'test-sigkey'
        self.query_execute.return_value = [{'checksum_type': 'md5'}, {'checksum_type': 'sha256'}]
        result = kojihub.create_rpm_checksum(src, dst, rpm_id, sigkey, chsum_list)
        self.assertIsNone(result)

        self.assertEqual(len(self.queries), 1)
        query = self.queries[0]
        self.assertEqual(query.tables, ['rpm_checksum'])
        self.assertEqual(query.joins, None)
        self.assertEqual(query.clauses,
                         ["checksum_type IN %(checksum_types)s", "sigkey=%(sigkey)s"])
