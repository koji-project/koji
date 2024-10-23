from __future__ import absolute_import

try:
    from unittest import mock
except ImportError:
    import mock
from six.moves import StringIO

import koji
from koji_cli.commands import handle_version
from . import utils


class TestVersion(utils.CliTestCase):
    def setUp(self):
        self.options = mock.MagicMock()
        self.options.debug = False
        self.session = mock.MagicMock()
        self.session.getAPIVersion.return_value = koji.API_VERSION

    @mock.patch('sys.stdout', new_callable=StringIO)
    def test_version_valid(self, stdout):
        expected = """Client: %s
Hub:    %s
""" % (koji.__version__, koji.__version__)
        self.session.getKojiVersion.return_value = koji.__version__
        rv = handle_version(self.options, self.session, [])
        self.assertEqual(rv, None)
        self.assert_console_message(stdout, expected)
        self.session.getKojiVersion.assert_called_once_with()

    @mock.patch('sys.stdout', new_callable=StringIO)
    def test_version_invalid(self, stdout):
        expected = """Client: %s
Hub:    Can't determine (older than 1.23)
""" % koji.__version__
        self.session.getKojiVersion.side_effect = koji.GenericError()
        rv = handle_version(self.options, self.session, [])
        self.assertEqual(rv, None)
        self.assert_console_message(stdout, expected)
        self.session.getKojiVersion.assert_called_once_with()
