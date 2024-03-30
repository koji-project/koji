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
        self.activate_session_mock = mock.patch('koji_cli.commands.activate_session').start()
        self.error_format = """Usage: %s add-channel [options] <channel_name>
(Specify the --help global option for a list of other help options)

%s: error: {message}
""" % (self.progname, self.progname)

    def tearDown(self):
        mock.patch.stopall()

    @mock.patch('sys.stdout', new_callable=six.StringIO)
    def test_handle_add_channel(self, stdout):
        self.session.addChannel.return_value = self.channel_id
        rv = handle_add_channel(self.options, self.session,
                                ['--description', self.description, self.channel_name])
        actual = stdout.getvalue()
        expected = '%s added: id %s\n' % (self.channel_name, self.channel_id)
        self.assertMultiLineEqual(actual, expected)
        self.activate_session_mock.assert_called_once_with(self.session, self.options)
        self.session.addChannel.assert_called_once_with(self.channel_name,
                                                        description=self.description)
        self.assertNotEqual(rv, 1)

    def test_handle_add_channel_exist(self):
        expected_api = 'channel %s already exists (id=%s)' % (self.channel_name, self.channel_id)
        expected = 'channel %s already exists\n' % self.channel_name

        self.session.addChannel.side_effect = koji.GenericError(expected_api)
        arguments = ['--description', self.description, self.channel_name]
        self.assert_system_exit(
            handle_add_channel,
            self.options, self.session, arguments,
            stdout='',
            stderr=expected,
            exit_code=1,
            activate_session=None)
        self.activate_session_mock.assert_called_once_with(self.session, self.options)
        self.session.addChannel.assert_called_once_with(self.channel_name,
                                                        description=self.description)

    def test_handle_add_channel_older_hub(self):
        expected_api = 'Invalid method: addChannel'
        expected = 'addChannel is available on hub from Koji 1.26 version, your version ' \
                   'is 1.25.1\n'
        self.session.hub_version_str = '1.25.1'

        self.session.addChannel.side_effect = koji.GenericError(expected_api)
        arguments = ['--description', self.description, self.channel_name]
        self.assert_system_exit(
            handle_add_channel,
            self.options, self.session, arguments,
            stdout='',
            stderr=expected,
            exit_code=1,
            activate_session=None)
        self.activate_session_mock.assert_called_once_with(self.session, self.options)
        self.session.addChannel.assert_called_once_with(self.channel_name,
                                                        description=self.description)

    def test_handle_add_channel_without_args(self):
        arguments = []
        self.assert_system_exit(
            handle_add_channel,
            self.options, self.session, arguments,
            stdout='',
            stderr=self.format_error_message('Please specify one channel name'),
            exit_code=2,
            activate_session=None)
        self.activate_session_mock.assert_not_called()

    def test_handle_add_channel_more_args(self):
        channel_2 = 'channel-2'
        arguments = [self.channel_name, channel_2]
        self.assert_system_exit(
            handle_add_channel,
            self.options, self.session, arguments,
            stdout='',
            stderr=self.format_error_message('Please specify one channel name'),
            exit_code=2,
            activate_session=None)
        self.activate_session_mock.assert_not_called()

    def test_handle_add_channel_other_error_msg(self):
        expected = 'Other error message.'

        self.session.addChannel.side_effect = koji.GenericError(expected)
        arguments = ['--description', self.description, self.channel_name]
        self.assert_system_exit(
            handle_add_channel,
            self.options, self.session, arguments,
            stdout='',
            stderr=expected + '\n',
            exit_code=1,
            activate_session=None)
        self.activate_session_mock.assert_called_once_with(self.session, self.options)
        self.session.addChannel.assert_called_once_with(self.channel_name,
                                                        description=self.description)

    def test_handle_add_channel_help(self):
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
