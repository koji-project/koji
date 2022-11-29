import unittest
import mock
import six

import koji
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
        self.get_rpm = mock.patch('kojihub.kojihub.get_rpm').start()
        self.get_build = mock.patch('kojihub.kojihub.get_build').start()
        self. rpm_info = {'id': 123, 'name': 'test-rpm', 'external_repo_id': 0, 'version': '11',
                          'release': '222', 'arch': 'noarch', 'build_id': 222}
        self.rpm_id = 123
        self.sigkey = 'test-sigkey'
        self.query_execute = mock.MagicMock()
        self.single_value = mock.MagicMock()
        self.path_signed = mock.patch('koji.pathinfo.signed').start()
        self.path_build = mock.patch('koji.pathinfo.build').start()
        self.context = mock.patch('kojihub.kojihub.context').start()
        self.context.session.assertPerm = mock.MagicMock()
        self.context.opts = {'RPMDefaultChecksums': 'md5 sha256'}

    def tearDown(self):
        mock.patch.stopall()

    def getQuery(self, *args, **kwargs):
        query = QP(*args, **kwargs)
        query.execute = self.query_execute
        query.singleValue = self.single_value
        self.queries.append(query)
        return query

    def test_checksum_type_not_string(self):
        checksum_types = 'type-1 type-2'
        with self.assertRaises(koji.GenericError) as ex:
            kojihub.create_rpm_checksum(self.rpm_id, self.sigkey, checksum_types=checksum_types)
        self.assertEqual(f'Invalid type of checksum_types: {type(checksum_types)}',
                         str(ex.exception))

    def test_checksum_type_bad_type(self):
        checksum_types = ['md5', 'type-1']
        with self.assertRaises(koji.GenericError) as ex:
            kojihub.create_rpm_checksum(self.rpm_id, self.sigkey, checksum_types=checksum_types)
        self.assertEqual("Checksum_type type-1 isn't supported", str(ex.exception))

    def test_external_rpm(self):
        ext_rpm_info = {'id': 123, 'name': 'test-rpm', 'external_repo_id': 125,
                        'external_repo_name': 'test-ext-rpm', 'version': '11',
                        'release': '222', 'arch': 'noarch'}
        self.get_rpm.return_value = ext_rpm_info
        nvra = "%(name)s-%(version)s-%(release)s.%(arch)s" % ext_rpm_info
        with self.assertRaises(koji.GenericError) as ex:
            kojihub.create_rpm_checksum(self.rpm_id, self.sigkey)
        self.assertEqual(f'Not an internal rpm: {nvra} (from test-ext-rpm)', str(ex.exception))

    def test_not_sigkey_related_to_rpm(self):
        self.get_rpm.return_value = self.rpm_info
        checksum_types = ['md5', 'sha256']
        nvra = "%(name)s-%(version)s-%(release)s.%(arch)s" % self.rpm_info
        expected_err = f'There is no rpm {nvra} signed with {self.sigkey}'
        self.single_value.return_value = None
        with self.assertRaises(koji.GenericError) as ex:
            kojihub.create_rpm_checksum(self.rpm_id, self.sigkey, checksum_types=checksum_types)
        self.assertEqual(expected_err % self.rpm_info, str(ex.exception))

        self.assertEqual(len(self.queries), 1)
        query = self.queries[0]
        self.assertEqual(query.tables, ['rpmsigs'])
        self.assertEqual(query.joins, None)
        self.assertEqual(query.clauses, ['rpm_id=%(rpm_id)i', 'sigkey=%(sigkey)s'])

    def test_checksum_exists(self):
        self.get_rpm.return_value = self.rpm_info
        self.single_value.return_value = 'test-sighash'
        self.query_execute.return_value = [{'checksum_type': 'md5'}, {'checksum_type': 'sha256'}]
        result = kojihub.create_rpm_checksum(self.rpm_id, self.sigkey)
        self.assertIsNone(result)

        self.assertEqual(len(self.queries), 2)
        query = self.queries[0]
        self.assertEqual(query.tables, ['rpmsigs'])
        self.assertEqual(query.joins, None)
        self.assertEqual(query.clauses, ['rpm_id=%(rpm_id)i', 'sigkey=%(sigkey)s'])

        query = self.queries[1]
        self.assertEqual(query.tables, ['rpm_checksum'])
        self.assertEqual(query.joins, None)
        self.assertEqual(query.clauses,
                         ["checksum_type IN %(checksum_types)s", "sigkey=%(sigkey)s"])

    @mock_open()
    def test_cannot_open_file(self, m_open):
        self.get_rpm.return_value = self.rpm_info
        self.get_build.return_value = {'build_id': 222}
        self.single_value.return_value = 'test-sighash'
        self.query_execute.return_value = [{'checksum_type': 'md5'}]
        self.path_build.return_value = 'fakebuildpath'
        self.path_signed.return_value = 'fakesignedpath'
        m_open.side_effect = IOError()

        with self.assertRaises(koji.GenericError) as ex:
            kojihub.create_rpm_checksum(self.rpm_id, self.sigkey)
        self.assertEqual("RPM path fakebuildpath/fakesignedpath cannot be open.",
                         str(ex.exception))

        self.assertEqual(len(self.queries), 2)
        query = self.queries[0]
        self.assertEqual(query.tables, ['rpmsigs'])
        self.assertEqual(query.joins, None)
        self.assertEqual(query.clauses, ['rpm_id=%(rpm_id)i', 'sigkey=%(sigkey)s'])

        query = self.queries[1]
        self.assertEqual(query.tables, ['rpm_checksum'])
        self.assertEqual(query.joins, None)
        self.assertEqual(query.clauses,
                         ["checksum_type IN %(checksum_types)s", "sigkey=%(sigkey)s"])
