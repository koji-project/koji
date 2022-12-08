import base64
import mock
import os
import unittest

import koji
import kojihub

IP = kojihub.InsertProcessor
QP = kojihub.QueryProcessor


class TestAddRPMSig(unittest.TestCase):
    def getInsert(self, *args, **kwargs):
        insert = IP(*args, **kwargs)
        insert.execute = mock.MagicMock()
        self.inserts.append(insert)
        return insert

    def getQuery(self, *args, **kwargs):
        query = QP(*args, **kwargs)
        query.execute = self.query_execute
        self.queries.append(query)
        return query

    def setUp(self):
        self.InsertProcessor = mock.patch('kojihub.kojihub.InsertProcessor',
                                          side_effect=self.getInsert).start()
        self.inserts = []
        self.QueryProcessor = mock.patch('kojihub.kojihub.QueryProcessor',
                                         side_effect=self.getQuery).start()
        self.queries = []
        self.query_execute = mock.MagicMock()
        self.context = mock.patch('kojihub.kojihub.context').start()
        # It seems MagicMock will not automatically handle attributes that
        # start with "assert"
        self.context.session.assertLogin = mock.MagicMock()
        self.context.session.assertPerm = mock.MagicMock()
        self.context.opts = {'HostPrincipalFormat': '-%s-'}
        self.exports = kojihub.RootExports()
        self.data_path = os.path.abspath("tests/test_hub/data/rpms")

    def tearDown(self):
        mock.patch.stopall()

    @mock.patch('koji.plugin.run_callbacks')
    @mock.patch('kojihub.kojihub.get_rpm')
    @mock.patch('kojihub.kojihub.get_build')
    @mock.patch('os.path.isdir')
    @mock.patch('koji.ensuredir')
    @mock.patch('kojihub.kojihub.open')
    def test_add_rpm_sig_header_signed(
            self,
            open,
            ensuredir,
            isdir,
            get_build,
            get_rpm,
            run_callbacks):
        """Test addRPMSig with header-only signed RPM"""
        self.query_execute.side_effect = [[]]
        isdir.side_effect = [True]
        get_rpm.side_effect = [{
            'id': 1,
            'name': 'testpkg',
            'version': '1.0.0',
            'release': '1',
            'arch': 'noarch',
            'epoch': None,
            'payloadhash': '1706d0174aa29a5a3e5c60855a778c35',
            'size': 123,
            'external_repo_id': None,
            'build_id': 1,
        }]
        open.side_effect = [mock.MagicMock()]

        rpm_path = os.path.join(self.data_path, 'header-signed.rpm')
        sighdr = koji.rip_rpm_sighdr(rpm_path)

        self.exports.addRPMSig(1, base64.b64encode(sighdr))
        self.context.session.assertPerm.assert_called_once_with('sign')
        self.assertEqual(len(self.inserts), 1)
        insert = self.inserts[0]
        self.assertEqual(insert.data['rpm_id'], 1)
        self.assertEqual(insert.data['sigkey'], '15f712be')

    def test_scan_sighdr_header_signed(self):
        """Test _scan_sighdr on a header-only signed package"""
        rpm_path = os.path.join(self.data_path, 'header-signed.rpm')
        sighdr = koji.rip_rpm_sighdr(rpm_path)

        sigmd5, sig = kojihub._scan_sighdr(sighdr, rpm_path)
        self.assertEqual(koji.hex_string(sigmd5), '1706d0174aa29a5a3e5c60855a778c35')
        sigkey = koji.get_sigpacket_key_id(sig)
        self.assertEqual(sigkey, '15f712be')
