from __future__ import absolute_import
import mock
import six
try:
    import unittest2 as unittest
except ImportError:
    import unittest

from koji_cli.commands import handle_list_volumes
from . import utils


class TestListVolumes(utils.CliTestCase):

    # Show long diffs in error output...
    maxDiff = None

    @mock.patch('sys.stdout', new_callable=six.StringIO)
    @mock.patch('koji_cli.commands.activate_session')
    def test_handle_list_volumes(
            self,
            activate_session_mock,
            stdout):
        """Test handle_list_volumes function"""
        session = mock.MagicMock()
        options = mock.MagicMock()
        vol_info = [
            {'id': 1, 'name': 'DEFAULT'},
            {'id': 2, 'name': 'TEST-1'},
            {'id': 3, 'name': 'TEST-2'},
        ]

        expected = "\n".join([v['name'] for v in vol_info]) + "\n"
        session.listVolumes.return_value = vol_info
        handle_list_volumes(options, session, [])
        self.assert_console_message(stdout, expected)

    def test_handle_list_volumes_help(self):
        self.assert_help(
            handle_list_volumes,
            """Usage: %s list-volumes
(Specify the --help global option for a list of other help options)

Options:
  -h, --help  show this help message and exit
""" % self.progname)


if __name__ == '__main__':
    unittest.main()
