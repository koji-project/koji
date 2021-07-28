from __future__ import absolute_import

import mock
from six.moves import StringIO

import koji
from koji_cli.commands import handle_remove_sig
from . import utils


class TestRemoveSig(utils.CliTestCase):
    maxDiff = None

    def setUp(self):
        self.options = mock.MagicMock()
        self.options.debug = False
        self.session = mock.MagicMock()
        self.session.getAPIVersion.return_value = koji.API_VERSION

    def test_delete_sig_help(self):
        self.assert_help(
            handle_remove_sig,
            """Usage: %s remove-sig [options] <rpm-id/n-v-r.a/rpminfo>
(Specify the --help global option for a list of other help options)

Options:
  -h, --help       show this help message and exit
  --sigkey=SIGKEY  Specify signature key
  --all            Remove all signed copies for specified RPM
""" % self.progname)

    @mock.patch('sys.stderr', new_callable=StringIO)
    def test_delete_sig_without_option(self, stderr):
        expected = "Usage: %s remove-sig [options] <rpm-id/n-v-r.a/rpminfo>\n" \
                   "(Specify the --help global option for a list of other help options)\n\n" \
                   "%s: error: Please specify an RPM\n" % (self.progname, self.progname)
        with self.assertRaises(SystemExit) as ex:
            handle_remove_sig(self.options, self.session, [])
        self.assertExitCode(ex, 2)
        self.assert_console_message(stderr, expected)

    @mock.patch('sys.stdout', new_callable=StringIO)
    def test_delete_sig_non_exist_rpm(self, stdout):
        rpm = '1234'
        expected = "No such rpm in system: %s\n" % rpm
        self.session.getRPM.return_value = None

        self.assert_system_exit(
            handle_remove_sig,
            self.options,
            self.session,
            [rpm, '--all'],
            stderr=self.format_error_message(expected),
            exit_code=1,
            activate_session=None)
        self.session.getRPM.assert_called_with('1234')
        self.session.deleteRPMSig.assert_not_called()

    def test_delete_sig_valid(self):
        rpm = '1'
        rpminfo = {'arch': 'src',
                   'build_id': 10,
                   'buildroot_id': None,
                   'buildtime': 1618361584,
                   'epoch': None,
                   'external_repo_id': 0,
                   'external_repo_name': 'INTERNAL',
                   'extra': None,
                   'id': 1,
                   'metadata_only': False,
                   'name': 'koji',
                   'payloadhash': 'c2b13f978c45e274c856e0a4599842a4',
                   'release': '1.fc34',
                   'size': 1178794,
                   'version': '1.24.1'}
        self.session.getRPM.return_value = rpminfo
        self.session.deleteRPMSig.return_value = None
        handle_remove_sig(self.options, self.session, [rpm, '--sigkey', 'testkey'])
        self.session.getRPM.assert_called_with('1')
        self.session.deleteRPMSig.assert_called_with('1', sigkey='testkey', all_sigs=False)
