import unittest
import mock

import koji
import kojihub

QP = kojihub.QueryProcessor


class TestGetRpmChecksums(unittest.TestCase):
    def setUp(self):
        self.maxDiff = None
        self.exports = kojihub.RootExports()
        self.create_rpm_checksum_output = mock.patch(
            'kojihub.kojihub.create_rpm_checksums_output').start()
        self.write_signed_rpm = mock.patch('kojihub.kojihub.write_signed_rpm').start()
        self.get_rpm = mock.patch('kojihub.kojihub.get_rpm').start()
        self.QueryProcessor = mock.patch('kojihub.kojihub.QueryProcessor',
                                         side_effect=self.getQuery).start()
        self.queries = []
        self.query_execute = mock.MagicMock()
        self.rpm_info = {'id': 123, 'name': 'test-name', 'version': '1.1', 'release': '123',
                         'arch': 'arch'}
        self.nvra = "%(name)s-%(version)s-%(release)s.%(arch)s" % self.rpm_info

    def tearDown(self):
        mock.patch.stopall()

    def getQuery(self, *args, **kwargs):
        query = QP(*args, **kwargs)
        query.execute = self.query_execute
        self.queries.append(query)
        return query

    def test_rpm_id_not_str(self):
        rpm_id = ['123']
        with self.assertRaises(koji.GenericError) as ex:
            self.exports.getRPMChecksums(rpm_id)
        self.assertEqual('rpm_id must be an integer', str(ex.exception))

    def test_checksum_types_not_list(self):
        rpm_id = 123
        self.get_rpm.return_value = self.rpm_info
        checksum_types = 'type'
        with self.assertRaises(koji.GenericError) as ex:
            self.exports.getRPMChecksums(rpm_id, checksum_types=checksum_types)
        self.assertEqual('checksum_type must be a list', str(ex.exception))

    def test_checksum_types_wrong_type(self):
        rpm_id = 123
        checksum_types = ['md5', 'type']
        with self.assertRaises(koji.GenericError) as ex:
            self.exports.getRPMChecksums(rpm_id, checksum_types=checksum_types)
        self.assertEqual("Checksum_type type isn't supported", str(ex.exception))

    def test_all_checksum_exists(self):
        rpm_id = 123
        self.get_rpm.return_value = self.rpm_info
        checksum_types = ['md5', 'sha256']
        expected_result = {'sigkey1': {'md5': 'checksum-md5', 'sha256': 'checksum-sha256'}}
        self.query_execute.side_effect = [
            [{'sigkey': 'sigkey-1'}],
            [{'checksum': 'checksum-md5', 'checksum_type': 0, 'sigkey': 'test-sigkey'},
             {'checksum': 'checksum-sha256', 'checksum_type': 2, 'sigkey': 'test-sigkey'}]]
        self.create_rpm_checksum_output.return_value = expected_result
        result = self.exports.getRPMChecksums(rpm_id, checksum_types=checksum_types)
        self.assertEqual(len(self.queries), 2)
        query = self.queries[0]
        self.assertEqual(query.tables, ['rpmsigs'])
        self.assertEqual(query.joins, None)
        self.assertEqual(query.clauses, ['rpm_id=%(rpm_id)i'])

        query = self.queries[1]
        self.assertEqual(query.tables, ['rpm_checksum'])
        self.assertEqual(query.joins, None)
        self.assertEqual(query.clauses,
                         ['checksum_type IN %(checksum_type)s', 'rpm_id=%(rpm_id)i'])
        self.assertEqual(expected_result, result)

    def test_missing_checksum_not_sigkey_without_strict(self):
        rpm_id = 123
        self.get_rpm.return_value = self.rpm_info
        checksum_types = ['md5']
        self.query_execute.side_effect = [[], []]
        result = self.exports.getRPMChecksums(rpm_id, checksum_types=checksum_types)
        self.assertEqual({}, result)

        self.assertEqual(len(self.queries), 2)
        query = self.queries[0]
        self.assertEqual(query.tables, ['rpmsigs'])
        self.assertEqual(query.joins, None)
        self.assertEqual(query.clauses, ['rpm_id=%(rpm_id)i'])

        query = self.queries[1]
        self.assertEqual(query.tables, ['rpm_checksum'])
        self.assertEqual(query.joins, None)
        self.assertEqual(query.clauses,
                         ['checksum_type IN %(checksum_type)s', 'rpm_id=%(rpm_id)i'])
        self.write_signed_rpm.assert_not_called()
        self.create_rpm_checksum_output.assert_not_called()

    def test_missing_checksum_not_sigkey_with_strict(self):
        rpm_id = 123
        self.get_rpm.return_value = self.rpm_info
        checksum_types = ['md5']
        self.query_execute.side_effect = [[], []]
        with self.assertRaises(koji.GenericError) as ex:
            self.exports.getRPMChecksums(rpm_id, checksum_types=checksum_types, strict=True)
        self.assertEqual(f"Rpm {self.nvra} doesn't have cached checksums or signed copies.",
                         str(ex.exception))

        self.assertEqual(len(self.queries), 2)
        query = self.queries[0]
        self.assertEqual(query.tables, ['rpmsigs'])
        self.assertEqual(query.joins, None)
        self.assertEqual(query.clauses, ['rpm_id=%(rpm_id)i'])

        query = self.queries[1]
        self.assertEqual(query.tables, ['rpm_checksum'])
        self.assertEqual(query.joins, None)
        self.assertEqual(query.clauses,
                         ['checksum_type IN %(checksum_type)s', 'rpm_id=%(rpm_id)i'])
        self.write_signed_rpm.assert_not_called()
        self.create_rpm_checksum_output.assert_not_called()

    def test_missing_valid_checksum_generated(self):
        rpm_id = 123
        checksum_types = ['md5']
        self.get_rpm.return_value = self.rpm_info
        expected_result = {}
        self.query_execute.side_effect = [
            [{'sigkey': 'sigkey-1'}],
            [],
            [{'checksum': 'checksum-md5', 'checksum_type': 0}]]
        result = self.exports.getRPMChecksums(rpm_id, checksum_types=checksum_types)
        self.assertEqual(expected_result, result)

        self.assertEqual(len(self.queries), 2)
        query = self.queries[0]
        self.assertEqual(query.tables, ['rpmsigs'])
        self.assertEqual(query.joins, None)
        self.assertEqual(query.clauses, ['rpm_id=%(rpm_id)i'])

        query = self.queries[1]
        self.assertEqual(query.tables, ['rpm_checksum'])
        self.assertEqual(query.joins, None)
        self.assertEqual(query.clauses,
                         ['checksum_type IN %(checksum_type)s', 'rpm_id=%(rpm_id)i'])
        self.write_signed_rpm.assert_not_called()
        self.create_rpm_checksum_output.assert_not_called()

    def test_missing_valid_checksum_generated_with_strict(self):
        rpm_id = 123
        checksum_types = ['md5']
        self.get_rpm.return_value = self.rpm_info
        self.query_execute.side_effect = [
            [{'sigkey': 'sigkey-1'}],
            [],
            [{'checksum': 'checksum-md5', 'checksum_type': 0}]]
        with self.assertRaises(koji.GenericError) as ex:
            self.exports.getRPMChecksums(rpm_id, checksum_types=checksum_types, strict=True)
        self.assertEqual(f"Rpm {self.nvra} doesn't have cached checksums or signed copies.",
                         str(ex.exception))

        self.assertEqual(len(self.queries), 2)
        query = self.queries[0]
        self.assertEqual(query.tables, ['rpmsigs'])
        self.assertEqual(query.joins, None)
        self.assertEqual(query.clauses, ['rpm_id=%(rpm_id)i'])

        query = self.queries[1]
        self.assertEqual(query.tables, ['rpm_checksum'])
        self.assertEqual(query.joins, None)
        self.assertEqual(query.clauses,
                         ['checksum_type IN %(checksum_type)s', 'rpm_id=%(rpm_id)i'])

        self.write_signed_rpm.assert_not_called()
        self.create_rpm_checksum_output.assert_not_called()

    def test_missing_valid_more_checksum_generated_and_exists(self):
        rpm_id = 123
        self.get_rpm.return_value = self.rpm_info
        checksum_types = ['md5', 'sha256']
        expected_result = {'sigkey1': {'md5': 'checksum-md5', 'sha256': 'checksum-sha256'}}
        self.query_execute.side_effect = [
            [{'sigkey': 'sigkey-1'}],
            [{'checksum': 'checksum-md5', 'checksum_type': 0, 'sigkey': 'test-sigkey'}],
            [{'checksum': 'checksum-md5', 'checksum_type': 0, 'sigkey': 'test-sigkey'},
             {'checksum': 'checksum-sha256', 'checksum_type': 2, 'sigkey': 'test-sigkey'}]]
        self.write_signed_rpm.return_value = None
        self.create_rpm_checksum_output.return_value = expected_result
        result = self.exports.getRPMChecksums(rpm_id, checksum_types=checksum_types)
        self.assertEqual(expected_result, result)

        self.assertEqual(len(self.queries), 2)
        query = self.queries[0]
        self.assertEqual(query.tables, ['rpmsigs'])
        self.assertEqual(query.joins, None)
        self.assertEqual(query.clauses, ['rpm_id=%(rpm_id)i'])

        query = self.queries[1]
        self.assertEqual(query.tables, ['rpm_checksum'])
        self.assertEqual(query.joins, None)
        self.assertEqual(query.clauses,
                         ['checksum_type IN %(checksum_type)s', 'rpm_id=%(rpm_id)i'])

    def test_missing_valid_more_checksum_generated_and_exists_more_sigkeys(self):
        rpm_id = 123
        self.get_rpm.return_value = self.rpm_info
        checksum_types = ['md5', 'sha256']
        expected_result = {'sigkey1': {'md5': 'checksum-md5', 'sha256': 'checksum-sha256'},
                           'sigkey2': {'md5': 'checksum-md5', 'sha256': 'checksum-sha256'}}
        self.query_execute.side_effect = [
            [{'sigkey': 'sigkey-1'}, {'sigkey': 'sigkey-2'}],
            [{'checksum': 'checksum-md5', 'checksum_type': 0, 'sigkey': 'sigkey-1'},
             {'checksum': 'checksum-sha256', 'checksum_type': 2, 'sigkey': 'sigkey-2'}],
            [{'checksum': 'checksum-md5', 'checksum_type': 0, 'sigkey': 'sigkey-1'},
             {'checksum': 'checksum-sha256', 'checksum_type': 2, 'sigkey': 'sigkey-1'},
             {'checksum': 'checksum-md5', 'checksum_type': 0, 'sigkey': 'sigkey-2'},
             {'checksum': 'checksum-sha256', 'checksum_type': 2, 'sigkey': 'sigkey-2'}]]
        self.write_signed_rpm.return_value = None
        self.create_rpm_checksum_output.return_value = expected_result
        result = self.exports.getRPMChecksums(rpm_id, checksum_types=checksum_types)
        self.assertEqual(expected_result, result)

        self.assertEqual(len(self.queries), 2)
        query = self.queries[0]
        self.assertEqual(query.tables, ['rpmsigs'])
        self.assertEqual(query.joins, None)
        self.assertEqual(query.clauses, ['rpm_id=%(rpm_id)i'])

        query = self.queries[1]
        self.assertEqual(query.tables, ['rpm_checksum'])
        self.assertEqual(query.joins, None)
        self.assertEqual(query.clauses,
                         ['checksum_type IN %(checksum_type)s', 'rpm_id=%(rpm_id)i'])
