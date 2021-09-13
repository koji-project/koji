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

Only use this method in extreme situations, because it goes against Koji's
design of immutable, auditable data.

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
        self.session.deleteRPMSig.side_effect = koji.GenericError('No such rpm: DATA')

        self.assert_system_exit(
            handle_remove_sig,
            self.options,
            self.session,
            [rpm, '--all'],
            stderr=self.format_error_message(expected),
            exit_code=1,
            activate_session=None)
        self.session.deleteRPMSig.assert_called_with('1234', sigkey=None, all_sigs=True)

    def test_delete_sig_valid(self):
        rpm = '1'
        self.session.deleteRPMSig.return_value = None
        handle_remove_sig(self.options, self.session, [rpm, '--sigkey', 'testkey'])
        self.session.deleteRPMSig.assert_called_with('1', sigkey='testkey', all_sigs=False)
