from __future__ import absolute_import

import mock
from six.moves import StringIO

import koji
from koji_cli.commands import anon_handle_list_builds
from . import utils


class TestListBuilds(utils.CliTestCase):
    def setUp(self):
        self.options = mock.MagicMock()
        self.options.debug = False
        self.session = mock.MagicMock()
        self.session.getAPIVersion.return_value = koji.API_VERSION

    @mock.patch('sys.stderr', new_callable=StringIO)
    def test_list_builds_without_option(self, stderr):
        expected = "Usage: %s list-builds [options]\n" \
                   "(Specify the --help global option for a list of other help options)\n\n" \
                   "%s: error: Filter must be provided for list\n" % (self.progname, self.progname)
        with self.assertRaises(SystemExit) as ex:
            anon_handle_list_builds(self.options, self.session, [])
        self.assertExitCode(ex, 2)
        self.assert_console_message(stderr, expected)

    @mock.patch('sys.stderr', new_callable=StringIO)
    def test_list_builds_non_exist_pkg(self, stderr):
        pkg = 'test-pkg'
        expected = "Usage: %s list-builds [options]\n" \
                   "(Specify the --help global option for a list of other help options)\n\n" \
                   "%s: error: No such package: %s\n" % (self.progname, self.progname, pkg)
        self.session.getPackageID.return_value = None
        with self.assertRaises(SystemExit) as ex:
            anon_handle_list_builds(self.options, self.session,
                                    ['--package', pkg])
        self.assertExitCode(ex, 2)
        self.assert_console_message(stderr, expected)

    @mock.patch('sys.stderr', new_callable=StringIO)
    def test_list_builds_non_exist_owner(self, stderr):
        owner = 'test-owner'
        expected = "Usage: %s list-builds [options]\n" \
                   "(Specify the --help global option for a list of other help options)\n\n" \
                   "%s: error: No such user: %s\n" % (self.progname, self.progname, owner)
        self.session.getUser.return_value = None
        with self.assertRaises(SystemExit) as ex:
            anon_handle_list_builds(self.options, self.session,
                                    ['--owner', owner])
        self.assertExitCode(ex, 2)
        self.assert_console_message(stderr, expected)

    @mock.patch('sys.stderr', new_callable=StringIO)
    def test_list_builds_non_exist_volume(self, stderr):
        volume = 'test-volume'
        expected = "Usage: %s list-builds [options]\n" \
                   "(Specify the --help global option for a list of other help options)\n\n" \
                   "%s: error: No such volume: %s\n" % (self.progname, self.progname, volume)
        self.session.listVolumes.return_value = []
        with self.assertRaises(SystemExit) as ex:
            anon_handle_list_builds(self.options, self.session,
                                    ['--volume', volume])
        self.assertExitCode(ex, 2)
        self.assert_console_message(stderr, expected)

    @mock.patch('sys.stderr', new_callable=StringIO)
    def test_list_builds_invalid_state(self, stderr):
        state = '6'
        expected = "Usage: %s list-builds [options]\n" \
                   "(Specify the --help global option for a list of other help options)\n\n" \
                   "%s: error: Invalid state: %s\n" % (self.progname, self.progname, state)
        self.session.getTag.return_value = None
        with self.assertRaises(SystemExit) as ex:
            anon_handle_list_builds(self.options, self.session,
                                    ['--state', state])
        self.assertExitCode(ex, 2)
        self.assert_console_message(stderr, expected)

    @mock.patch('sys.stderr', new_callable=StringIO)
    def test_list_builds_invalid_state_string(self, stderr):
        state = 'test-state'
        expected = "Usage: %s list-builds [options]\n" \
                   "(Specify the --help global option for a list of other help options)\n\n" \
                   "%s: error: Invalid state: %s\n" % (self.progname, self.progname, state)
        self.session.getTag.return_value = None
        with self.assertRaises(SystemExit) as ex:
            anon_handle_list_builds(self.options, self.session,
                                    ['--state', state])
        self.assertExitCode(ex, 2)
        self.assert_console_message(stderr, expected)

    @mock.patch('sys.stderr', new_callable=StringIO)
    def test_list_builds_non_exist_build(self, stderr):
        build = 222
        expected = "Usage: %s list-builds [options]\n" \
                   "(Specify the --help global option for a list of other help options)\n\n" \
                   "%s: error: No such build: '%s'\n" % (self.progname, self.progname, build)
        self.session.getBuild.return_value = None
        with self.assertRaises(SystemExit) as ex:
            anon_handle_list_builds(self.options, self.session,
                                    ['--build', build])
        self.assertExitCode(ex, 2)
        self.assert_console_message(stderr, expected)
