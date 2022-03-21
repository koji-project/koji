from __future__ import absolute_import
import copy
import hashlib
import mock
import random
import six
from six.moves import range
import unittest

from mock import call
from koji.util import base64encode
from koji_cli.commands import handle_import_sig
from . import utils

import os


class TestImportSIG(utils.CliTestCase):
    def md5sum(self, message):
        md5 = hashlib.md5()
        md5.update(message.encode('utf-8'))
        return md5.hexdigest()

    def mock_os_path_exists(self, filepath):
        if filepath in self.custom_os_path_exists:
            return self.custom_os_path_exists[filepath]
        return self.os_path_exists(filepath)

    def setUp(self):
        self.maxDiff = None
        self.options = mock.MagicMock()
        self.session = mock.MagicMock()
        self.activate_session_mock = mock.patch('koji_cli.commands.activate_session').start()
        self.custom_os_path_exists = {}
        self.os_path_exists = os.path.exists

        self.rpm_headers = [
            {
                'sourcepackage': 1,
                'name': 'bash',
                'version': '4.4.12',
                'release': '5.fc26',
                'arch': 'x86_64',
                'siggpg': None,
                'sigpgp': None,
                'dsaheader': None,
                'rsaheader': None,
            },
            {
                'sourcepackage': 1,
                'name': 'less',
                'version': '487',
                'release': '3.fc26',
                'arch': 'x86_64',
                'siggpg': None,
                'sigpgp': None,
                'dsaheader': None,
                'rsaheader': None,
            },
            {
                'sourcepackage': 1,
                'name': 'sed',
                'version': '4.4',
                'release': '1.fc26',
                'arch': 'x86_64',
                'siggpg': None,
                'sigpgp': None,
                'dsaheader': None,
                'rsaheader': None,
            }
        ]

        self.error_format = """Usage: %s import-sig [options] <package> [<package> ...]
(Specify the --help global option for a list of other help options)

%s: error: {message}
""" % (self.progname, self.progname)

    @mock.patch('sys.stderr', new_callable=six.StringIO)
    @mock.patch('sys.stdout', new_callable=six.StringIO)
    @mock.patch('koji.rip_rpm_sighdr')
    @mock.patch('koji.get_sigpacket_key_id')
    @mock.patch('koji.get_header_fields')
    def test_handle_import_sig(
            self,
            get_header_fields_mock,
            get_sigpacket_key_id_mock,
            rip_rpm_sighdr_mock,
            stdout, stderr):
        """Test handle_import_sig function"""
        arguments = ['/path/to/bash', '/path/to/less', '/path/to/sed']

        expected = ''
        fake_sigkey = '00112233445566778899aAbBcCdDeEfF'

        #
        # we just need to change original os.path.exists behavior, if the input
        # is matched return the value we expected.
        self.custom_os_path_exists = dict((f, True) for f in arguments)

        # setup and start os.path.exists patch
        os_path_exists_patch = mock.patch('os.path.exists', new=self.mock_os_path_exists)
        os_path_exists_patch.start()

        # Case 1, Unsigned pkg test (without ----with-unsigned)
        # result: import skipped
        for pkgfile in arguments:
            expected += "Skipping unsigned package: %s" % pkgfile + "\n"

        get_header_fields_mock.side_effect = copy.deepcopy(self.rpm_headers)

        # Run
        handle_import_sig(self.options, self.session, arguments)

        self.assert_console_message(stdout, expected)
        self.activate_session_mock.assert_called_once()
        rip_rpm_sighdr_mock.assert_not_called()
        self.session.getRPM.assert_not_called()

        # Case 2, No RPM in system
        # result: import skipped
        expected = ''
        for data in self.rpm_headers:
            data['siggpg'] = fake_sigkey
            data['sigpgp'] = fake_sigkey
            data['dsaheader'] = fake_sigkey
            data['rsaheader'] = fake_sigkey
            tmp = data.copy()
            tmp['arch'] = 'src' if tmp['sourcepackage'] else tmp['arch']
            expected += "No such rpm in system: %(name)s-%(version)s-%(release)s.%(arch)s" % \
                        tmp + "\n"

        get_header_fields_mock.side_effect = copy.deepcopy(self.rpm_headers)
        get_sigpacket_key_id_mock.return_value = fake_sigkey
        self.session.getRPM.return_value = {}

        # Run
        handle_import_sig(self.options, self.session, arguments)

        self.assert_console_message(stdout, expected)
        rip_rpm_sighdr_mock.assert_not_called()
        self.session.queryRPMSigs.assert_not_called()

        # Case 3, Find external repo RPM
        # result: import skipped
        ext_repos = ['ext-repo1.net', 'ext-repo2.net', 'ext-repo3.net']

        expected = ''
        rinfo = copy.deepcopy(self.rpm_headers)
        for data in rinfo:
            rid = random.randint(0, 999) % 3
            data['external_repo_id'] = rid + 1
            data['external_repo_name'] = ext_repos[rid]
            data['arch'] = 'src' if data['sourcepackage'] else data['arch']
            expected += "Skipping external rpm: %(name)s-%(version)s-%(release)s.%(arch)s@%(external_repo_name)s" % data + "\n"

        get_header_fields_mock.side_effect = rinfo
        self.session.getRPM.side_effect = rinfo

        # Run
        handle_import_sig(self.options, self.session, arguments)

        self.assert_console_message(stdout, expected)
        rip_rpm_sighdr_mock.assert_not_called()
        self.session.queryRPMSigs.assert_not_called()

        # Case 4, has previous RPM signature
        # result: import skipped
        #         show match or mismatch message
        expected = ''

        # session.queryRPMSigs return example:
        # [{'sigkey': '64dab85d', 'sighash': '7141c84f059d2f0722ff545051b2981d', 'rpm_id': 1}]
        #
        sighdr, sigRpm = [], []
        for i, pkg in enumerate(arguments):
            signature = 'sighdr-%s' % pkg
            sighdr.append(signature.encode('utf-8'))
            if i < 2:
                sigRpm.append([{'sighash': self.md5sum(signature)}])
                expected += "Signature already imported: %s" % pkg + "\n"
            else:
                sigRpm.append([{'sighash': self.md5sum('wrong-sig-case')}])
                expected_warn = "signature mismatch: %s" % pkg + "\n"
                expected_warn += "  The system already has a signature for this rpm with key %s" \
                                 % fake_sigkey + "\n"
                expected_warn += "  The two signature headers are not the same" + "\n"

        rinfo = copy.deepcopy(self.rpm_headers)
        for i, data in enumerate(rinfo):
            data['external_repo_id'] = 0
            data['id'] = i + 1

        get_header_fields_mock.side_effect = copy.deepcopy(rinfo)
        self.session.getRPM.side_effect = rinfo
        rip_rpm_sighdr_mock.side_effect = sighdr
        self.session.queryRPMSigs.side_effect = sigRpm

        # Run
        handle_import_sig(self.options, self.session, arguments)

        self.assert_console_message(stdout, expected)
        self.assert_console_message(stderr, expected_warn)

        # Case 5, --test options test
        # result: everything works fine and addRPMSig/writeSignedRPM should
        #         not be called.
        expected = ''
        for pkg in arguments:
            expected += "Importing signature [key %s] from %s..." % (fake_sigkey, pkg) + "\n"
            expected += "Writing signed copy" + "\n"

        get_header_fields_mock.side_effect = copy.deepcopy(rinfo)
        self.session.getRPM.side_effect = rinfo
        rip_rpm_sighdr_mock.side_effect = sighdr
        self.session.queryRPMSigs.side_effect = None
        self.session.queryRPMSigs.return_value = []

        # Run
        handle_import_sig(self.options, self.session, arguments + ['--test'])

        self.assert_console_message(stdout, expected)
        self.session.addRPMSig.assert_not_called()
        self.session.writeSignedRPM.assert_not_called()

        # Case 6, normal import
        # result: addRPMSig/writeSignedRPM should be called
        get_header_fields_mock.side_effect = copy.deepcopy(rinfo)
        self.session.getRPM.side_effect = rinfo
        rip_rpm_sighdr_mock.side_effect = sighdr

        add_sig_calls, write_sig_calls = [], []
        for i in range(0, 3):
            add_sig_calls.append(call(rinfo[i]['id'], base64encode(sighdr[i])))
            write_sig_calls.append(call(rinfo[i]['id'], fake_sigkey))

        # Run
        handle_import_sig(self.options, self.session, arguments)

        self.assert_console_message(stdout, expected)
        self.session.addRPMSig.assert_has_calls(add_sig_calls)
        self.session.writeSignedRPM.assert_has_calls(write_sig_calls)

        # restore os.path.exists patch
        os_path_exists_patch.stop()

    @mock.patch('sys.stdout', new_callable=six.StringIO)
    def test_handle_import_sig_sigkey_from_header_signed(self, stdout):
        """Test sigkey computation from header-only signed rpm in handle_import_sig function"""
        data_path = os.path.abspath("tests/test_hub/data/rpms")
        arguments = [os.path.join(data_path, 'header-signed.rpm')]
        sigkey = '15f712be'

        expected = ''

        for pkg in arguments:
            expected += "Importing signature [key %s] from %s..." % (sigkey, pkg) + "\n"
            expected += "Writing signed copy" + "\n"

        self.session.getRPM.side_effect = [
            {
                'sourcepackage': 0,
                'name': 'testpkg',
                'version': '1.0.0',
                'release': '1',
                'arch': 'x86_64',
                'external_repo_id': 0,
                'id': 1,
            }
        ]
        self.session.queryRPMSigs.side_effect = None
        self.session.queryRPMSigs.return_value = []

        # Run
        handle_import_sig(self.options, self.session, arguments + ['--test'])

        self.assert_console_message(stdout, expected)
        self.session.addRPMSig.assert_not_called()
        self.session.writeSignedRPM.assert_not_called()

    def test_handle_import_sig_argument_test(self):
        """Test handle_import_sig function without arguments"""
        # Case 1. empty argument
        self.assert_system_exit(
            handle_import_sig,
            self.options, self.session, [],
            stderr=self.format_error_message("At least one package must be specified"),
            activate_session=None,
            exit_code=2)

        # Case 2. File not exists test
        arguments = ['/bin/ls', '/tmp', '/path/to/file1', '/path/to/file2']
        self.assert_system_exit(
            handle_import_sig,
            self.options, self.session, arguments,
            stderr=self.format_error_message("No such file: %s" % arguments[2]),
            activate_session=None)

    def test_handle_import_sig_help(self):
        """Test handle_import_sig help message"""
        self.assert_help(
            handle_import_sig,
            """Usage: %s import-sig [options] <package> [<package> ...]
(Specify the --help global option for a list of other help options)

Options:
  -h, --help       show this help message and exit
  --with-unsigned  Also import unsigned sig headers
  --test           Test mode -- don't actually import
""" % self.progname)


if __name__ == '__main__':
    unittest.main()
