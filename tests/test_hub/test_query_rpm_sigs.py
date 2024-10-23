import unittest

from unittest import mock

import kojihub

QP = kojihub.QueryProcessor


class TestQueryRPMSigs(unittest.TestCase):

    def getQuery(self, *args, **kwargs):
        query = QP(*args, **kwargs)
        query.execute = mock.MagicMock()
        self.queries.append(query)
        return query

    def setUp(self):
        self.QueryProcessor = mock.patch('kojihub.kojihub.QueryProcessor',
                                         side_effect=self.getQuery).start()
        self.queries = []
        self.get_rpm = mock.patch('kojihub.kojihub.get_rpm').start()
        self.rinfo = {'arch': 'x86_64',
                      'build_id': 1,
                      'buildroot_id': None,
                      'buildtime': 1564782768,
                      'epoch': None,
                      'external_repo_id': None,
                      'extra': None,
                      'id': 1234,
                      'metadata_only': False,
                      'name': 'fs_mark',
                      'payloadhash': 'ed0690ab4b0508f2448d99a08e0a004a',
                      'release': '20.el8',
                      'size': 25644,
                      'version': '3.3'}

    def tearDown(self):
        mock.patch.stopall()

    def test_rpm_dict(self):
        rinfo_dict = {
            'arch': 'x86_64',
            'name': 'fs_mark',
            'release': '20.el8',
            'version': '3.3'
        }
        self.get_rpm.return_value = self.rinfo
        kojihub.query_rpm_sigs(rpm_id=rinfo_dict)
        self.get_rpm.assert_called_once_with(rinfo_dict)

    def test_rpm_nvra(self):
        nvra = 'fs_mark-3.3-20.el8.x86_64'
        self.get_rpm.return_value = self.rinfo
        kojihub.query_rpm_sigs(rpm_id=nvra)
        self.get_rpm.assert_called_once_with(nvra)

    def test_rpm_int(self):
        rpm_id = 1234
        kojihub.query_rpm_sigs(rpm_id=rpm_id)
        self.get_rpm.assert_not_called()

    def test_rpm_str_int(self):
        rpm_id = '1234'
        kojihub.query_rpm_sigs(rpm_id=rpm_id)
        self.get_rpm.assert_called_once_with(rpm_id)
