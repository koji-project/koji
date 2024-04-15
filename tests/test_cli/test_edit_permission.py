from __future__ import absolute_import
import mock
import koji
import six

from koji_cli.commands import handle_edit_permission
from . import utils


class TestEditPermission(utils.CliTestCase):

    def setUp(self):
        # Show long diffs in error output...
        self.maxDiff = None
        self.options = mock.MagicMock()
        self.options.quiet = True
        self.options.debug = False
        self.session = mock.MagicMock()
        self.session.getAPIVersion.return_value = koji.API_VERSION
        self.activate_session_mock = mock.patch('koji_cli.commands.activate_session').start()
        self.error_format = """Usage: %s edit-permission <permission> <description>
(Specify the --help global option for a list of other help options)

%s: error: {message}
""" % (self.progname, self.progname)
        self.perm = 'test-perm'
        self.description = 'test-description'

    def tearDown(self):
        mock.patch.stopall()

    def test_handle_edit_permission_argument_error(self):
        expected = self.format_error_message("Please specify a permission and a description")
        for args in [[], [self.perm]]:
            self.assert_system_exit(
                handle_edit_permission,
                self.options,
                self.session,
                args,
                stderr=expected,
                activate_session=None)
        self.activate_session_mock.assert_not_called()
        self.session.editPermission.assert_not_called()

    @mock.patch('sys.stdout', new_callable=six.StringIO)
    def test_handle_edit_permission_with_new_and_description(self, stdout):
        handle_edit_permission(self.options, self.session, [self.perm, self.description])
        actual = stdout.getvalue()
        expected = ''
        self.assertMultiLineEqual(actual, expected)
        self.session.editPermission.assert_called_once_with(self.perm, self.description)
        self.activate_session_mock.assert_called_once_with(self.session, self.options)

    def test_edit_permission_help(self):
        self.assert_help(
            handle_edit_permission,
            """Usage: %s edit-permission <permission> <description>
(Specify the --help global option for a list of other help options)

Options:
  -h, --help  show this help message and exit
""" % self.progname)
