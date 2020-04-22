from __future__ import absolute_import
import mock
import six
try:
    import unittest2 as unittest
except ImportError:
    import unittest

from koji_cli.commands import handle_add_volume
from . import utils


class TestAddVolume(utils.CliTestCase):

    # Show long diffs in error output...
    maxDiff = None

    def setUp(self):
        self.error_format = """Usage: %s add-volume <volume-name>
(Specify the --help global option for a list of other help options)

%s: error: {message}
""" % (self.progname, self.progname)

    @mock.patch('sys.stderr', new_callable=six.StringIO)
    @mock.patch('sys.stdout', new_callable=six.StringIO)
    @mock.patch('koji_cli.commands.activate_session')
    def test_handle_add_volume(
            self,
            activate_session_mock,
            stdout,
            stderr):
        """Test handle_add_volume function"""
        session = mock.MagicMock()
        options = mock.MagicMock()
        vol_name = 'vol-test-01'
        vol_info = {'id': 1, 'name': vol_name}

        # Case 1. argument error
        expected = self.format_error_message(
            "Command requires exactly one volume-name.")
        for arg in [[], ['test-1', 'test-2']]:
            self.assert_system_exit(
                handle_add_volume,
                options,
                session,
                arg,
                stderr=expected,
                activate_session=None)

        # Case 2. volume already exists
        expected = "Volume %s already exists" % vol_name + "\n"
        session.getVolume.return_value = vol_info
        with self.assertRaises(SystemExit) as ex:
            handle_add_volume(options, session, [vol_name])
        self.assertExitCode(ex, 1)
        self.assert_console_message(stderr, expected)
        session.getVolume.assert_called_with(vol_name)
        activate_session_mock.assert_not_called()

        # Case 3. Add volume
        expected = "Added volume %(name)s with id %(id)i" % vol_info + "\n"
        session.getVolume.return_value = {}
        session.addVolume.return_value = vol_info
        handle_add_volume(options, session, [vol_name])
        self.assert_console_message(stdout, expected)
        session.addVolume(vol_name)
        activate_session_mock.assert_called_with(session, options)

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
