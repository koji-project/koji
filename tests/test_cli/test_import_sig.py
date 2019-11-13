from __future__ import absolute_import
import copy
import hashlib
import mock
import random
import six
from six.moves import range
try:
    import unittest2 as unittest
except ImportError:
    import unittest

from mock import call
from koji.util import base64encode
from koji_cli.commands import handle_import_sig
from . import utils

import os


class TestImportSIG(utils.CliTestCase):

    # Show long diffs in error output...
    maxDiff = None

    def md5sum(self, message):
        md5 = hashlib.md5()
        md5.update(message.encode('utf-8'))
        return md5.hexdigest()

    def mock_os_path_exists(self, filepath):
        if filepath in self.custom_os_path_exists:
            return self.custom_os_path_exists[filepath]
        return self.os_path_exists(filepath)

    def setUp(self):
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
            },
            {
                'sourcepackage': 1,
                'name': 'less',
                'version': '487',
                'release': '3.fc26',
                'arch': 'x86_64',
                'siggpg': None,
                'sigpgp': None,
            },
            {
                'sourcepackage': 1,
                'name': 'sed',
                'version': '4.4',
                'release': '1.fc26',
                'arch': 'x86_64',
                'siggpg': None,
                'sigpgp': None,
            }
        ]

        self.error_format = """Usage: %s import-sig [options] <package> [<package> ...]
(Specify the --help global option for a list of other help options)

%s: error: {message}
""" % (self.progname, self.progname)

    @mock.patch('sys.stdout', new_callable=six.StringIO)
    @mock.patch('koji.rip_rpm_sighdr')
    @mock.patch('koji.get_sigpacket_key_id')
    @mock.patch('koji.get_header_fields')
    @mock.patch('koji_cli.commands.activate_session')
    def test_handle_import_sig(
            self,
            activate_session_mock,
            get_header_fields_mock,
            get_sigpacket_key_id_mock,
            rip_rpm_sighdr_mock,
            stdout):
        """Test handle_import_sig function"""
        arguments = ['/path/to/bash', '/path/to/less', '/path/to/sed']
        options = mock.MagicMock()
        session = mock.MagicMock()
        expected = ''
        fake_sigkey = '00112233445566778899aAbBcCdDeEfF'

        #
        # we just need to change original os.path.exists behavior, if the input
        # is matched return the value we expected.
        self.custom_os_path_exists = dict((f, True) for f in arguments)

        # setup and start os.path.exists patch
        os_path_exists_patch = mock.patch('os.path.exists',
                                          new=self.mock_os_path_exists)
        os_path_exists_patch.start()

        # Case 1, Unsigned pkg test (without ----with-unsigned)
        # result: import skipped
        for pkgfile in arguments:
            expected += "Skipping unsigned package: %s" % pkgfile + "\n"

        get_header_fields_mock.side_effect = copy.deepcopy(self.rpm_headers)

        # Run
        handle_import_sig(options, session, arguments)

        self.assert_console_message(stdout, expected)
        activate_session_mock.assert_called_once()
        rip_rpm_sighdr_mock.assert_not_called()
        session.getRPM.assert_not_called()

        # Case 2, No RPM in system
        # result: import skipped
        expected = ''
        for data in self.rpm_headers:
            data['siggpg'] = fake_sigkey
            data['sigpgp'] = fake_sigkey
            tmp = data.copy()
            tmp['arch'] = 'src' if tmp['sourcepackage'] else tmp['arch']
            expected += "No such rpm in system: %(name)s-%(version)s-%(release)s.%(arch)s" % \
                        tmp + "\n"

        get_header_fields_mock.side_effect = copy.deepcopy(self.rpm_headers)
        get_sigpacket_key_id_mock.return_value = fake_sigkey
        session.getRPM.return_value = {}

        # Run
        handle_import_sig(options, session, arguments)

        self.assert_console_message(stdout, expected)
        rip_rpm_sighdr_mock.assert_not_called()
        session.queryRPMSigs.assert_not_called()

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
        session.getRPM.side_effect = rinfo

        # Run
        handle_import_sig(options, session, arguments)

        self.assert_console_message(stdout, expected)
        rip_rpm_sighdr_mock.assert_not_called()
        session.queryRPMSigs.assert_not_called()

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
                expected += "Warning: signature mismatch: %s" % pkg + "\n"
                expected += "  The system already has a signature for this rpm with key %s" % fake_sigkey + "\n"
                expected += "  The two signature headers are not the same" + "\n"

        rinfo = copy.deepcopy(self.rpm_headers)
        for i, data in enumerate(rinfo):
            data['external_repo_id'] = 0
            data['id'] = i + 1

        get_header_fields_mock.side_effect = copy.deepcopy(rinfo)
        session.getRPM.side_effect = rinfo
        rip_rpm_sighdr_mock.side_effect = sighdr
        session.queryRPMSigs.side_effect = sigRpm

        # Run
        handle_import_sig(options, session, arguments)

        self.assert_console_message(stdout, expected)

        # Case 5, --test options test
        # result: everything works fine and addRPMSig/writeSignedRPM should
        #         not be called.
        expected = ''
        for pkg in arguments:
            expected += "Importing signature [key %s] from %s..." % (fake_sigkey, pkg) + "\n"
            expected += "Writing signed copy" + "\n"

        get_header_fields_mock.side_effect = copy.deepcopy(rinfo)
        session.getRPM.side_effect = rinfo
        rip_rpm_sighdr_mock.side_effect = sighdr
        session.queryRPMSigs.side_effect = None
        session.queryRPMSigs.return_value = []

        # Run
        handle_import_sig(options, session, arguments + ['--test'])

        self.assert_console_message(stdout, expected)
        session.addRPMSig.assert_not_called()
        session.writeSignedRPM.assert_not_called()

        # Case 6, normal import
        # result: addRPMSig/writeSignedRPM should be called
        get_header_fields_mock.side_effect = copy.deepcopy(rinfo)
        session.getRPM.side_effect = rinfo
        rip_rpm_sighdr_mock.side_effect = sighdr

        add_sig_calls, write_sig_calls = [], []
        for i in range(0, 3):
            add_sig_calls.append(call(rinfo[i]['id'], base64encode(sighdr[i])))
            write_sig_calls.append(call(rinfo[i]['id'], fake_sigkey))

        # Run
        handle_import_sig(options, session, arguments)

        self.assert_console_message(stdout, expected)
        session.addRPMSig.assert_has_calls(add_sig_calls)
        session.writeSignedRPM.assert_has_calls(write_sig_calls)

        # restore os.path.exists patch
        os_path_exists_patch.stop()

    def test_handle_import_sig_argument_test(self):
        """Test handle_import_sig function without arguments"""
        options = mock.MagicMock()
        session = mock.MagicMock()

        # Case 1. empty argument
        expected = self.format_error_message(
            "At least one package must be specified")

        self.assert_system_exit(
            handle_import_sig,
            options,
            session,
            [],
            stderr=expected,
            activate_session=None)

        # Case 2. File not exists test
        arguments = ['/bin/ls', '/tmp', '/path/to/file1', '/path/to/file2']
        expected = self.format_error_message(
            "No such file: %s" % arguments[2])
        self.assert_system_exit(
            handle_import_sig,
            options,
            session,
            arguments,
            stderr=expected,
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
  --write          Also write the signed copies
  --test           Test mode -- don't actually import
""" % self.progname)


if __name__ == '__main__':
    unittest.main()
