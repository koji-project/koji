import unittest
import mock

import koji
import kojihub

QP = kojihub.QueryProcessor


class TestGetRpmChecksums(unittest.TestCase):
    def setUp(self):
        self.maxDiff = None
        self.exports = kojihub.RootExports()
        self.os_path = mock.patch('os.path.exists').start()
        self.create_rpm_checksum_output = mock.patch(
            'kojihub.kojihub.create_rpm_checksums_output').start()
        self.create_rpm_checksum = mock.patch('kojihub.kojihub.create_rpm_checksum').start()
        self.calculate_chsum = mock.patch('kojihub.kojihub.calculate_chsum').start()
        self.get_rpm = mock.patch('kojihub.kojihub.get_rpm').start()
        self.get_build = mock.patch('kojihub.kojihub.get_build').start()
        self.QueryProcessor = mock.patch('kojihub.kojihub.QueryProcessor',
                                         side_effect=self.getQuery).start()
        self.queries = []
        self.query_execute = mock.MagicMock()
        self.rpm_info = {'id': 123, 'name': 'test-name', 'version': '1.1', 'release': '123',
                         'arch': 'arch', 'build_id': 3}
        self.nvra = "%(name)s-%(version)s-%(release)s.%(arch)s" % self.rpm_info
        self.build_info = {'build_id': 3, 'name': 'test-name', 'version': '1.1', 'release': '123'}

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
        self.get_rpm.assert_not_called()
        self.calculate_chsum.assert_not_called()
        self.create_rpm_checksum.assert_not_called()
        self.create_rpm_checksum_output.assert_not_called()

    def test_checksum_types_not_list(self):
        rpm_id = 123
        self.get_rpm.return_value = self.rpm_info
        checksum_types = 'type'
        with self.assertRaises(koji.GenericError) as ex:
            self.exports.getRPMChecksums(rpm_id, checksum_types=checksum_types)
        self.assertEqual('checksum_type must be a list', str(ex.exception))
        self.get_rpm.assert_called_once_with(rpm_id, strict=True)
        self.calculate_chsum.assert_not_called()
        self.create_rpm_checksum.assert_not_called()
        self.create_rpm_checksum_output.assert_not_called()

    def test_checksum_types_wrong_type(self):
        rpm_id = 123
        checksum_types = ['md5', 'type']
        with self.assertRaises(koji.GenericError) as ex:
            self.exports.getRPMChecksums(rpm_id, checksum_types=checksum_types)
        self.assertEqual("Checksum_type type isn't supported", str(ex.exception))
        self.get_rpm.assert_called_once_with(rpm_id, strict=True)
        self.calculate_chsum.assert_not_called()
        self.create_rpm_checksum.assert_not_called()
        self.create_rpm_checksum_output.assert_not_called()

    def test_all_checksum_exists(self):
        self.os_path.return_value = True
        rpm_id = 123
        self.get_rpm.return_value = self.rpm_info
        checksum_types = ['md5', 'sha256']
        expected_result = {'sigkey-1': {'md5': 'checksum-md5', 'sha256': 'checksum-sha256'}}
        self.query_execute.side_effect = [
            [{'sigkey': 'sigkey-1'}],
            [{'checksum': 'checksum-md5', 'checksum_type': 0, 'sigkey': 'sigkey-1'},
             {'checksum': 'checksum-sha256', 'checksum_type': 2, 'sigkey': 'sigkey-1'}]]
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
        self.get_rpm.assert_called_once_with(rpm_id, strict=True)
        self.calculate_chsum.assert_not_called()
        self.create_rpm_checksum.assert_not_called()
        self.create_rpm_checksum_output.assert_called_once_with(
            [{'checksum': 'checksum-md5', 'checksum_type': 0, 'sigkey': 'sigkey-1'},
             {'checksum': 'checksum-sha256', 'checksum_type': 2, 'sigkey': 'sigkey-1'}],
            {'sigkey-1': {'sha256', 'md5'}}
        )

    def test_missing_checksum_not_sigkey(self):
        rpm_id = 123
        self.get_rpm.return_value = self.rpm_info
        checksum_types = ['md5']
        self.query_execute.side_effect = [[], []]
        result = self.exports.getRPMChecksums(rpm_id, checksum_types=checksum_types)
        self.assertEqual({}, result)

        self.assertEqual(len(self.queries), 1)
        query = self.queries[0]
        self.assertEqual(query.tables, ['rpmsigs'])
        self.assertEqual(query.joins, None)
        self.assertEqual(query.clauses, ['rpm_id=%(rpm_id)i'])

        self.get_rpm.assert_called_once_with(rpm_id, strict=True)
        self.calculate_chsum.assert_not_called()
        self.create_rpm_checksum.assert_not_called()
        self.create_rpm_checksum_output.assert_not_called()

    @mock.patch('kojihub.kojihub.open')
    def test_missing_valid_all_checksum_generated(self, open):
        self.os_path.return_value = True
        rpm_id = 123
        checksum_types = ['md5']
        self.get_rpm.return_value = self.rpm_info
        self.get_build.return_value = self.build_info
        expected_result = {'sigkey-1': {'md5': 'checksum-md5'}}
        calculate_chsum_res = {'sigkey-1': {'md5': 'checksum-md5'}}
        self.query_execute.side_effect = [
            [{'sigkey': 'sigkey-1'}],
            [],
            [{'checksum': 'checksum-md5', 'checksum_type': 0}]]
        self.calculate_chsum.return_value = calculate_chsum_res
        self.create_rpm_checksum.return_value = None
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
        self.get_rpm.assert_called_once_with(rpm_id, strict=True)
        self.assertEqual(self.calculate_chsum.call_count, 1)
        self.create_rpm_checksum.assert_called_once_with(rpm_id, 'sigkey-1', calculate_chsum_res)
        self.create_rpm_checksum_output.assert_called_once_with(
            [{'checksum': 'checksum-md5', 'checksum_type': 0}], {'sigkey-1': {'md5'}}
        )

    @mock.patch('kojihub.kojihub.open')
    def test_missing_valid_more_checksum_generated_and_exists(self, open):
        self.os_path.return_value = True
        rpm_id = 123
        self.get_rpm.return_value = self.rpm_info
        self.get_build.return_value = self.build_info
        checksum_types = ['md5', 'sha256']
        expected_result = {'sigkey-1': {'md5': 'checksum-md5', 'sha256': 'checksum-sha256'}}
        calculate_chsum_res = {'sigkey-1': {'sha256': 'checksum-sha256'}}
        self.query_execute.side_effect = [
            [{'sigkey': 'sigkey-1'}],
            [{'checksum': 'checksum-md5', 'checksum_type': 0, 'sigkey': 'sigkey-1'}],
            [{'checksum': 'checksum-md5', 'checksum_type': 0, 'sigkey': 'sigkey-1'},
             {'checksum': 'checksum-sha256', 'checksum_type': 2, 'sigkey': 'sigkey-1'}]]
        self.calculate_chsum.return_value = calculate_chsum_res
        self.create_rpm_checksum_output.return_value = expected_result
        self.create_rpm_checksum.return_value = None
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

        self.get_rpm.assert_called_once_with(rpm_id, strict=True)
        self.assertEqual(self.calculate_chsum.call_count, 1)
        self.create_rpm_checksum.assert_called_once_with(rpm_id, 'sigkey-1', calculate_chsum_res)
        self.create_rpm_checksum_output.assert_called_once_with(
            [{'checksum': 'checksum-md5', 'checksum_type': 0, 'sigkey': 'sigkey-1'},
             {'checksum': 'checksum-sha256', 'checksum_type': 2, 'sigkey': 'sigkey-1'}],
            {'sigkey-1': {'md5', 'sha256'}}
        )

    @mock.patch('kojihub.kojihub.open')
    def test_missing_valid_more_checksum_generated_and_exists_more_sigkeys(self, open):
        self.os_path.return_value = True
        rpm_id = 123
        self.get_rpm.return_value = self.rpm_info
        self.get_build.return_value = self.build_info
        checksum_types = ['md5', 'sha256']
        expected_result = {'sigkey1': {'md5': 'checksum-md5', 'sha256': 'checksum-sha256'},
                           'sigkey2': {'md5': 'checksum-md5', 'sha256': 'checksum-sha256'}}
        calculate_chsum_res = [
            {'sigkey1': {'md5': 'checksum-md5', 'sha256': 'checksum-sha256'}},
            {'sigkey2': {'md5': 'checksum-md5', 'sha256': 'checksum-sha256'}},
        ]
        self.query_execute.side_effect = [
            [{'sigkey': 'sigkey1'}, {'sigkey': 'sigkey2'}],
            [{'checksum': 'checksum-md5', 'checksum_type': 0, 'sigkey': 'sigkey1'},
             {'checksum': 'checksum-sha256', 'checksum_type': 2, 'sigkey': 'sigkey2'}],
            [{'checksum': 'checksum-md5', 'checksum_type': 0, 'sigkey': 'sigkey1'},
             {'checksum': 'checksum-sha256', 'checksum_type': 2, 'sigkey': 'sigkey1'},
             {'checksum': 'checksum-md5', 'checksum_type': 0, 'sigkey': 'sigkey2'},
             {'checksum': 'checksum-sha256', 'checksum_type': 2, 'sigkey': 'sigkey2'}]]
        self.calculate_chsum.side_effect = calculate_chsum_res
        self.create_rpm_checksum_output.return_value = expected_result
        self.create_rpm_checksum.side_effect = [None, None]
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

        self.get_rpm.assert_called_once_with(rpm_id, strict=True)
        self.assertEqual(self.calculate_chsum.call_count, 2)
        self.create_rpm_checksum.assert_has_calls(
            [mock.call(rpm_id, 'sigkey1', calculate_chsum_res[0]),
             mock.call(rpm_id, 'sigkey2', calculate_chsum_res[1])])
        self.create_rpm_checksum_output.assert_called_once_with(
            [{'checksum': 'checksum-md5', 'checksum_type': 0, 'sigkey': 'sigkey1'},
             {'checksum': 'checksum-sha256', 'checksum_type': 2, 'sigkey': 'sigkey1'},
             {'checksum': 'checksum-md5', 'checksum_type': 0, 'sigkey': 'sigkey2'},
             {'checksum': 'checksum-sha256', 'checksum_type': 2, 'sigkey': 'sigkey2'}],
            {'sigkey1': {'md5', 'sha256'}, 'sigkey2': {'md5', 'sha256'}}
        )
