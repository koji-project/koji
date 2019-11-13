from __future__ import absolute_import
import hashlib
import mock
import six
try:
    import unittest2 as unittest
except ImportError:
    import unittest

from mock import call
import koji
from koji_cli.commands import handle_write_signed_rpm
from . import utils

import os

QUERY_RPM_RESULTS = [
    {'sigkey': '64dab85d', 'sighash': '7141c84f059d2f0722ff545051b2981d', 'rpm_id': 1},
    {'sigkey': '64dab85d', 'sighash': '65e5dc6e8690fc7a9a5453029d33f5b6', 'rpm_id': 2},
    {'sigkey': '64dab85d', 'sighash': '522d23faed3fe55866caa9a7e72c2c94', 'rpm_id': 3},
    {'sigkey': '64dab85d', 'sighash': 'e9e7c107379cff28a0732a6304a5741e', 'rpm_id': 4}
]

GET_RPM_RESULTS = [
    {
        'build_id': 1,
        'name': 'bash',
        'extra': None,
        'external_repo_id': 0,
        'buildtime': 1496119944,
        'id': 1,
        'epoch': None,
        'version': '4.4.12',
        'buildroot_id': None,
        'metadata_only': False,
        'release': '5.fc26',
        'arch': 'src',
        'payloadhash': '8a1705e86bef1516565b029c73ab7fdd',
        'external_repo_name': 'INTERNAL',
        'size': 9462614
    }, {
        'build_id': 2,
        'name': 'less',
        'extra': None,
        'external_repo_id': 0,
        'buildtime': 1494946131,
        'id': 2, 'epoch': None,
        'version': '487',
        'buildroot_id': None,
        'metadata_only': False,
        'release': '3.fc26',
        'arch': 'src',
        'payloadhash': '860aa8152af63ab3868af3596764d46e',
        'external_repo_name': 'INTERNAL',
        'size': 358835
    }, {
        'build_id': 3,
        'name': 'sed',
        'extra': None,
        'external_repo_id': 0,
        'buildtime': 1486654285,
        'id': 3,
        'epoch': None,
        'version': '4.4',
        'buildroot_id': None,
        'metadata_only': False,
        'release': '1.fc26',
        'arch': 'src',
        'payloadhash': 'beb5ac98593fa1047941ad771eb88497',
        'external_repo_name': 'INTERNAL',
        'size': 1262814
    }, {
        'build_id': 1,
        'name': 'bash',
        'extra': None,
        'external_repo_id': 0,
        'buildtime': 1496120170,
        'id': 4,
        'epoch': None,
        'version': '4.4.12',
        'buildroot_id': None,
        'metadata_only': False,
        'release': '5.fc26',
        'arch': 'x86_64',
        'payloadhash': '4a15ca94b1ac59d5ef9fc6d50ad73f3e',
        'external_repo_name': 'INTERNAL',
        'size': 1611874
    }
]


class TestWriteSignedRPM(utils.CliTestCase):

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
        self.error_format = """Usage: %s write-signed-rpm [options] <signature-key> <n-v-r> [<n-v-r> ...]
(Specify the --help global option for a list of other help options)

%s: error: {message}
""" % (self.progname, self.progname)

    @mock.patch('sys.stdout', new_callable=six.StringIO)
    @mock.patch('koji_cli.commands.activate_session')
    def test_handle_write_signed_rpm(
            self,
            activate_session_mock,
            stdout):
        """Test handle_write_signed_rpm function"""
        fake_sigkey = '64dab85d'
        arguments = [fake_sigkey]
        options = mock.MagicMock()
        session = mock.MagicMock()

        def get_expect_data(rpm_data):
            expected = ''
            calls = []
            for i, data in enumerate(rpm_data):
                nvra = "%(name)s-%(version)s-%(release)s.%(arch)s" % data
                expected += "[%d/%d] %s" % (i+1, len(rpm_data), nvra) + "\n"
                calls.append(call(data['id'], fake_sigkey))
            return expected, calls

        # Case 1, specifies N-V-R-A or N-V-R format RPM
        # result: write sigkey to specified RPMs
        rpm_data = [GET_RPM_RESULTS[0], GET_RPM_RESULTS[3]]

        session.getRPM.side_effect = [
            rpm_data[0],            # bash-4.4.12-5.fc26.src
            koji.GenericError       # bash-4.4.12-5.fc26
        ]
        session.getBuild.return_value = {
            'package_name': 'bash',
            'id': 1,
            'version': '4.4.12',
            'nvr': 'bash-4.4.12-5.fc26',
            'name': 'bash',
            'release': '5.fc26'
        }
        session.listRPMs.return_value = [rpm_data[1]]   # bash-4.4.12-5.fc26
        args = arguments + ['bash-4.4.12-5.fc26.src', 'bash-4.4.12-5.fc26']
        expect_msg, expect_calls = get_expect_data(rpm_data)

        handle_write_signed_rpm(options, session, args)
        self.assert_console_message(stdout, expect_msg)
        session.writeSignedRPM.assert_has_calls(expect_calls)
        session.queryRPMSigs.assert_not_called()

        # Case 2, with --all option
        # result: write sigkey to all RPMS
        session.queryRPMSigs.return_value = QUERY_RPM_RESULTS
        session.getRPM.side_effect = GET_RPM_RESULTS
        expect_msg, expect_calls = get_expect_data(GET_RPM_RESULTS)

        handle_write_signed_rpm(options, session, arguments + ['--all'])
        self.assert_console_message(stdout, expect_msg)
        session.writeSignedRPM.assert_has_calls(expect_calls)
        session.queryRPMSigs.assert_called_with(sigkey=fake_sigkey)

        session.queryRPMSigs.reset_mock()

        # Case 3, with --buildid option
        # result: write sigkey to specified build id RPM
        rpm_data = [
            GET_RPM_RESULTS[0],     # build_id = 1
            GET_RPM_RESULTS[3]]     # build_id = 1
        session.listRPMs.return_value = rpm_data
        expect_msg, expect_calls = get_expect_data(rpm_data)

        handle_write_signed_rpm(options, session, arguments + ['--buildid', '1'])
        self.assert_console_message(stdout, expect_msg)
        session.listRPMs.assert_called_with(1)
        session.queryRPMSigs.assert_not_called()
        session.writeSignedRPM.assert_has_calls(expect_calls)

        session.listRPM.reset_mock()
        session.writeSignedRPM.reset_mock()

        # Case 4, RPM not exist
        # result: raise koji.GenericError
        session.getRPM.side_effect = koji.GenericError('fake-get-rpm-error')
        session.getBuild.return_value = None

        args = arguments + ['gawk-4.1.4-3.fc26.x86_64']
        with self.assertRaises(koji.GenericError) as cm:
            handle_write_signed_rpm(options, session, args)
        self.assertEqual(
            str(cm.exception),
            'No such rpm or build: %s' % args[1])

        session.listRPM.assert_not_called()
        session.queryRPMSigs.assert_not_called()
        session.writeSignedRPM.assert_not_called()

    def test_handle_write_signed_rpm_argument_test(self):
        """Test handle_write_signed_rpm function without arguments"""
        options = mock.MagicMock()
        session = mock.MagicMock()

        # Case 1. empty argument
        expected = self.format_error_message(
            "A signature key must be specified")

        self.assert_system_exit(
            handle_write_signed_rpm,
            options,
            session,
            [],
            stderr=expected,
            activate_session=None)

        # Case 2. no RPM package is specified
        arguments = ['fake-signature-key']
        expected = self.format_error_message(
            "At least one RPM must be specified")
        self.assert_system_exit(
            handle_write_signed_rpm,
            options,
            session,
            arguments,
            stderr=expected,
            activate_session=None)

    def test_handle_write_signed_rpm_help(self):
        """Test handle_write_signed_rpm help message"""
        self.assert_help(
            handle_write_signed_rpm,
            """Usage: %s write-signed-rpm [options] <signature-key> <n-v-r> [<n-v-r> ...]
(Specify the --help global option for a list of other help options)

Options:
  -h, --help         show this help message and exit
  --all              Write out all RPMs signed with this key
  --buildid=BUILDID  Specify a build id rather than an n-v-r
""" % self.progname)


if __name__ == '__main__':
    unittest.main()
