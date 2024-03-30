from __future__ import absolute_import
import mock
import six
import unittest
import koji

from koji_cli.commands import handle_add_volume
from . import utils


class TestAddVolume(utils.CliTestCase):

    def setUp(self):
        # Show long diffs in error output...
        self.maxDiff = None
        self.options = mock.MagicMock()
        self.options.debug = False
        self.session = mock.MagicMock()
        self.session.getAPIVersion.return_value = koji.API_VERSION
        self.activate_session_mock = mock.patch('koji_cli.commands.activate_session').start()
        self.error_format = """Usage: %s add-volume <volume-name>
(Specify the --help global option for a list of other help options)

%s: error: {message}
""" % (self.progname, self.progname)

    def tearDown(self):
        mock.patch.stopall()

    @mock.patch('sys.stdout', new_callable=six.StringIO)
    def test_handle_add_volume(self, stdout):
        """Test handle_add_volume function"""
        vol_name = 'vol-test-01'
        vol_info = {'id': 1, 'name': vol_name}

        # Case 1. argument error
        for arg in [[], ['test-1', 'test-2']]:
            self.assert_system_exit(
                handle_add_volume,
                self.options, self.session, arg,
                stdout='',
                stderr=self.format_error_message("Command requires exactly one volume-name."),
                exit_code=2,
                activate_session=None)
        self.activate_session_mock.assert_not_called()
        self.activate_session_mock.reset_mock()

        # Case 2. volume already exists
        self.session.getVolume.return_value = vol_info
        self.assert_system_exit(
            handle_add_volume,
            self.options, self.session, [vol_name],
            stdout='',
            stderr="Volume %s already exists" % vol_name + "\n",
            exit_code=1,
            activate_session=None)
        self.session.getVolume.assert_called_with(vol_name)
        self.activate_session_mock.assert_not_called()
        self.activate_session_mock.reset_mock()

        # Case 3. Add volume
        expected = "Added volume %(name)s with id %(id)i" % vol_info + "\n"
        self.session.getVolume.return_value = {}
        self.session.addVolume.return_value = vol_info
        handle_add_volume(self.options, self.session, [vol_name])
        self.assert_console_message(stdout, expected)
        self.session.addVolume(vol_name)
        self.activate_session_mock.assert_called_with(self.session, self.options)

    def test_handle_add_volume_help(self):
        self.assert_help(
            handle_add_volume,
            """Usage: %s add-volume <volume-name>
(Specify the --help global option for a list of other help options)

Options:
  -h, --help  show this help message and exit
""" % self.progname)


if __name__ == '__main__':
    unittest.main()
