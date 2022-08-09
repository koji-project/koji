from __future__ import absolute_import

import mock

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
        self.error_format = """Usage: %s remove-sig [options] <rpm-id/n-v-r.a/rpminfo>
(Specify the --help global option for a list of other help options)

%s: error: {message}
""" % (self.progname, self.progname)

    def test_remove_sig_help(self):
        self.assert_help(
            handle_remove_sig,
            """Usage: %s remove-sig [options] <rpm-id/n-v-r.a/rpminfo>
(Specify the --help global option for a list of other help options)

Only use this method in extreme situations, because it goes against Koji's
design of immutable, auditable data.

Options:
  -h, --help       show this help message and exit
  --sigkey=SIGKEY  Specify signature key
  --all            Remove all signed copies for specified RPM
""" % self.progname)

    def test_remove_sig_without_option(self):
        arguments = []
        self.assert_system_exit(
            handle_remove_sig,
            self.options, self.session, arguments,
            stdout='',
            stderr=self.format_error_message("Please specify an RPM"),
            exit_code=2,
            activate_session=None)
        self.session.deleteRPMSig.assert_not_called()

    def test_remove_sig_non_exist_rpm(self):
        rpm = '1234'
        expected = "No such rpm in system: %s\n" % rpm
        self.session.deleteRPMSig.side_effect = koji.GenericError('No such rpm: DATA')

        self.assert_system_exit(
            handle_remove_sig,
            self.options,
            self.session,
            [rpm, '--all'],
            stderr=expected,
            exit_code=1,
            activate_session=None)
        self.session.deleteRPMSig.assert_called_with('1234', sigkey=None, all_sigs=True)

    def test_remove_sig_valid(self):
        rpm = '1'
        self.session.deleteRPMSig.return_value = None
        handle_remove_sig(self.options, self.session, [rpm, '--sigkey', 'testkey'])
        self.session.deleteRPMSig.assert_called_with('1', sigkey='testkey', all_sigs=False)

    def test_remove_sig_without_all_and_sigkey(self):
        rpm = '1234'
        expected = "Either --sigkey or --all options must be given\n"

        self.assert_system_exit(
            handle_remove_sig,
            self.options,
            self.session,
            [rpm],
            stderr=expected,
            exit_code=1,
            activate_session=None)

    def test_remove_sig_with_all_and_sigkey(self):
        rpm = '1234'
        expected = "Conflicting options specified\n"

        self.assert_system_exit(
            handle_remove_sig,
            self.options,
            self.session,
            [rpm, '--all', '--sigkey', 'testkey'],
            stderr=expected,
            exit_code=1,
            activate_session=None)

    def test_remove_sig_signature_removal_failed(self):
        rpm = '1234'
        nvra = 'test-1.23-1.arch'
        error_msg = "%s has no matching signatures to delete" % nvra
        expected = "Signature removal failed: %s\n" % error_msg
        self.session.deleteRPMSig.side_effect = koji.GenericError(error_msg)

        self.assert_system_exit(
            handle_remove_sig,
            self.options,
            self.session,
            [rpm, '--all'],
            stderr=expected,
            exit_code=1,
            activate_session=None)
        self.session.deleteRPMSig.assert_called_with('1234', sigkey=None, all_sigs=True)
