from __future__ import absolute_import
import mock
try:
    import unittest2 as unittest
except ImportError:
    import unittest
from six.moves import StringIO

import koji

from koji_cli.commands import anon_handle_list_channels

class TestListChannels(unittest.TestCase):
    def setUp(self):
        self.options = mock.MagicMock()
        self.options.quiet = True
        self.session = mock.MagicMock()
        self.session.getAPIVersion.return_value = koji.API_VERSION
        self.args = []

    @mock.patch('sys.stdout', new_callable=StringIO)
    @mock.patch('koji_cli.commands.ensure_connection')
    def test_list_channels(self, ensure_connection_mock, stdout):
        self.session.listChannels.return_value = [
            {'id': 1, 'name': 'default'},
            {'id': 2, 'name': 'test'},
        ]
        self.session.multiCall.return_value = [
            [[
                {'enabled': True, 'ready': True, 'capacity': 2.0, 'task_load': 1.34},
                {'enabled': True, 'ready': False, 'capacity': 2.0, 'task_load': 0.0},
                {'enabled': True, 'ready': False, 'capacity': 2.0, 'task_load': 0.0},
            ]],
            [[
                {'enabled': True, 'ready': True, 'capacity': 2.0, 'task_load': 1.34},
                {'enabled': False, 'ready': True, 'capacity': 2.0, 'task_load': 0.34},
                {'enabled': True, 'ready': False, 'capacity': 2.0, 'task_load': 0.0},
            ]],
        ]

        anon_handle_list_channels(self.options, self.session, self.args)

        actual = stdout.getvalue()
        print(actual)
        expected = """\
default              3      1      0      1      6     22%
test                 2      2      1      1      6     28%
"""
        self.assertMultiLineEqual(actual, expected)
        ensure_connection_mock.assert_called_once_with(self.session)
