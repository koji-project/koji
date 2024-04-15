from __future__ import absolute_import
import mock
import six
import unittest
import koji

from mock import call

from koji_cli.commands import handle_edit_host
from . import utils


class TestEditHost(utils.CliTestCase):
    def setUp(self):
        self.options = mock.MagicMock()
        self.options.debug = False
        self.session = mock.MagicMock()
        self.session.getAPIVersion.return_value = koji.API_VERSION
        self.activate_session_mock = mock.patch('koji_cli.commands.activate_session').start()
        self.error_format = """Usage: %s edit-host <hostname> [<hostname> ...] [options]
(Specify the --help global option for a list of other help options)

%s: error: {message}
""" % (self.progname, self.progname)
        self.host = 'host'
        self.arches = 'arch1 arch2'
        self.capacity = 0.22
        self.description = 'description'
        self.comment = 'comment'

    def tearDown(self):
        mock.patch.stopall()

    @mock.patch('sys.stdout', new_callable=six.StringIO)
    def test_handle_edit_host(self, stdout):
        host_info = mock.ANY
        args = [self.host]
        args.append('--arches=' + self.arches)
        args.append('--capacity=' + str(self.capacity))
        args.append('--description=' + self.description)
        args.append('--comment=' + self.comment)
        kwargs = {'arches': self.arches,
                  'capacity': self.capacity,
                  'description': self.description,
                  'comment': self.comment}

        self.session.multiCall.side_effect = [[[host_info]], [[True]]]
        # Run it and check immediate output
        # args: host, --arches='arch1 arch2', --capacity=0.22,
        # --description=description, --comment=comment
        # expected: success
        rv = handle_edit_host(self.options, self.session, args)
        actual = stdout.getvalue()
        expected = 'Edited host\n'
        self.assertMultiLineEqual(actual, expected)
        # Finally, assert that things were called as we expected.
        self.activate_session_mock.assert_called_once_with(self.session, self.options)
        self.session.getHost.assert_called_once_with(self.host)
        self.session.editHost.assert_called_once_with(self.host, **kwargs)
        self.assertEqual(self.session.multiCall.call_count, 2)
        self.assertNotEqual(rv, 1)

    @mock.patch('sys.stdout', new_callable=six.StringIO)
    def test_handle_edit_host_failed(self, stdout):
        host_info = mock.ANY
        args = [self.host]
        args.append('--arches=' + self.arches)
        args.append('--capacity=' + str(self.capacity))
        args.append('--description=' + self.description)
        args.append('--comment=' + self.comment)
        kwargs = {'arches': self.arches,
                  'capacity': self.capacity,
                  'description': self.description,
                  'comment': self.comment}

        self.session.multiCall.side_effect = [[[host_info]], [[False]]]
        # Run it and check immediate output
        # args: host, --arches='arch1 arch2', --capacity=0.22,
        # --description=description, --comment=comment
        # expected: failed - session.editHost == False
        rv = handle_edit_host(self.options, self.session, args)
        actual = stdout.getvalue()
        expected = 'No changes made to host\n'
        self.assertMultiLineEqual(actual, expected)
        # Finally, assert that things were called as we expected.
        self.activate_session_mock.assert_called_once_with(self.session, self.options)
        self.session.getHost.assert_called_once_with(self.host)
        self.session.editHost.assert_called_once_with(self.host, **kwargs)
        self.assertEqual(self.session.multiCall.call_count, 2)
        self.assertNotEqual(rv, 1)

    @mock.patch('sys.stdout', new_callable=six.StringIO)
    def test_handle_edit_multi_host(self, stdout):
        hosts = ['host1', 'host2']
        host_infos = [mock.ANY, mock.ANY]
        args = hosts
        args.append('--arches=' + self.arches)
        args.append('--capacity=' + str(self.capacity))
        args.append('--description=' + self.description)
        args.append('--comment=' + self.comment)
        kwargs = {'arches': self.arches,
                  'capacity': self.capacity,
                  'description': self.description,
                  'comment': self.comment}

        self.session.multiCall.side_effect = [[[info]
                                               for info in host_infos], [[True], [True]]]
        # Run it and check immediate output
        # args: host1, host2, --arches='arch1 arch2', --capacity=0.22,
        # --description=description, --comment=comment
        # expected: success
        rv = handle_edit_host(self.options, self.session, args)
        actual = stdout.getvalue()
        expected = 'Edited host1\nEdited host2\n'
        self.assertMultiLineEqual(actual, expected)
        # Finally, assert that things were called as we expected.
        self.activate_session_mock.assert_called_once_with(self.session, self.options)
        self.session.getHost.assert_has_calls([call(hosts[0]), call(hosts[1])])
        self.session.editHost.assert_has_calls(
            [call(hosts[0], **kwargs), call(hosts[1], **kwargs)])
        self.assertEqual(self.session.mock_calls,
                         [call.getHost(hosts[0]),
                          call.getHost(hosts[1]),
                             call.multiCall(strict=True),
                             call.editHost(hosts[0],
                                           **kwargs),
                             call.editHost(hosts[1],
                                           **kwargs),
                             call.multiCall(strict=True)])
        self.assertNotEqual(rv, 1)

    def test_handle_edit_host_no_arg(self):
        # Run it and check immediate output
        # args: _empty_
        # expected: failed - should specify host
        expected = self.format_error_message("Please specify a hostname")
        self.assert_system_exit(
            handle_edit_host,
            self.options,
            self.session,
            [],
            stdout='',
            stderr=expected,
            activate_session=None,
            exit_code=2
        )

        # Finally, assert that things were called as we expected.
        self.activate_session_mock.assert_not_called()
        self.session.getHost.assert_not_called()
        self.session.editHost.assert_not_called()
        self.session.multiCall.assert_not_called()

    def test_handle_edit_host_no_host(self):
        host_info = None
        args = [self.host]
        args.append('--arches=' + self.arches)
        args.append('--capacity=' + str(self.capacity))
        args.append('--description=' + self.description)
        args.append('--comment=' + self.comment)

        self.session.multiCall.return_value = [[host_info]]
        # Run it and check immediate output
        # args: host, --arches='arch1 arch2', --capacity=0.22,
        # --description=description, --comment=comment
        # expected: failed -- getHost() == None
        expected = """No such host: %s
No changes made, please correct the command line
""" % self.host
        self.assert_system_exit(
            handle_edit_host,
            self.options,
            self.session,
            args,
            stdout='',
            stderr=expected,
            activate_session=None,
            exit_code=1
        )
        # Finally, assert that things were called as we expected.
        self.activate_session_mock.assert_called_once_with(self.session, self.options)
        self.session.getHost.assert_called_once_with(self.host)
        self.session.editHost.assert_not_called()
        self.assertEqual(self.session.multiCall.call_count, 1)

    def test_handle_edit_host_help(self):
        self.assert_help(
            handle_edit_host,
            """Usage: %s edit-host <hostname> [<hostname> ...] [options]
(Specify the --help global option for a list of other help options)

Options:
  -h, --help           show this help message and exit
  --arches=ARCHES      Space or comma-separated list of supported
                       architectures
  --capacity=CAPACITY  Capacity of this host
  --description=DESC   Description of this host
  --comment=COMMENT    A brief comment about this host
""" % self.progname)


if __name__ == '__main__':
    unittest.main()
