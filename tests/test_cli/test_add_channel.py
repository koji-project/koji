from __future__ import absolute_import

import unittest

import mock
import six

import koji
from koji_cli.commands import handle_add_channel
from . import utils


class TestAddChannel(utils.CliTestCase):

    def setUp(self):
        self.maxDiff = None
        self.channel_name = 'test-channel'
        self.description = 'test-description'
        self.channel_id = 1
        self.options = mock.MagicMock()
        self.session = mock.MagicMock()

    @mock.patch('sys.stdout', new_callable=six.StringIO)
    @mock.patch('koji_cli.commands.activate_session')
    def test_handle_add_channel(self, activate_session_mock, stdout):
        self.session.addChannel.return_value = self.channel_id
        rv = handle_add_channel(self.options, self.session,
                                ['--description', self.description, self.channel_name])
        actual = stdout.getvalue()
        expected = '%s added: id %s\n' % (self.channel_name, self.channel_id)
        self.assertMultiLineEqual(actual, expected)
        activate_session_mock.assert_called_once_with(self.session, self.options)
        self.session.addChannel.assert_called_once_with(self.channel_name,
                                                        description=self.description)
        self.assertNotEqual(rv, 1)

    @mock.patch('sys.stderr', new_callable=six.StringIO)
    @mock.patch('koji_cli.commands.activate_session')
    def test_handle_add_channel_exist(self, activate_session_mock, stderr):
        expected = 'channel %(name)s already exists (id=%(id)i)'

        self.session.addChannel.side_effect = koji.GenericError(expected)
        with self.assertRaises(koji.GenericError) as ex:
            handle_add_channel(self.options, self.session,
                               ['--description', self.description, self.channel_name])
        self.assertEqual(str(ex.exception), expected)
        activate_session_mock.assert_called_once_with(self.session, self.options)
        self.session.addChannel.assert_called_once_with(self.channel_name,
                                                        description=self.description)

    @mock.patch('sys.stderr', new_callable=six.StringIO)
    @mock.patch('koji_cli.commands.activate_session')
    def test_handle_add_channel_without_args(self, activate_session_mock, stderr):
        with self.assertRaises(SystemExit) as ex:
            handle_add_channel(self.options, self.session, [])
        self.assertExitCode(ex, 2)
        actual = stderr.getvalue()
        expected_stderr = """Usage: %s add-channel [options] <channel_name>
(Specify the --help global option for a list of other help options)

%s: error: Please specify one channel name
""" % (self.progname, self.progname)
        self.assertMultiLineEqual(actual, expected_stderr)
        activate_session_mock.assert_not_called()

    @mock.patch('sys.stderr', new_callable=six.StringIO)
    @mock.patch('koji_cli.commands.activate_session')
    def test_handle_add_channel_more_args(self, activate_session_mock, stderr):
        channel_2 = 'channel-2'
        with self.assertRaises(SystemExit) as ex:
            handle_add_channel(self.options, self.session, [self.channel_name, channel_2])
        self.assertExitCode(ex, 2)
        actual = stderr.getvalue()
        expected_stderr = """Usage: %s add-channel [options] <channel_name>
(Specify the --help global option for a list of other help options)

%s: error: Please specify one channel name
""" % (self.progname, self.progname)
        self.assertMultiLineEqual(actual, expected_stderr)
        activate_session_mock.assert_not_called()

    def test_handle_add_host_help(self):
        self.assert_help(
            handle_add_channel,
            """Usage: %s add-channel [options] <channel_name>
(Specify the --help global option for a list of other help options)

Options:
  -h, --help            show this help message and exit
  --description=DESCRIPTION
                        Description of channel
""" % self.progname)


if __name__ == '__main__':
    unittest.main()
