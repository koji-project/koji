from __future__ import absolute_import
import mock
import six
try:
    import unittest2 as unittest
except ImportError:
    import unittest

from koji_cli.commands import handle_move_build
from . import utils


class TestMoveBuild(utils.CliTestCase):

    # Show long diffs in error output...
    maxDiff = None

    def setUp(self):
        self.session = mock.MagicMock()
        self.options = mock.MagicMock()

        self.error_format = """Usage: %s move-build [options] <tag1> <tag2> <pkg> [<pkg> ...]
(Specify the --help global option for a list of other help options)

%s: error: {message}
""" % (self.progname, self.progname)

        self.activate_session = mock.patch('koji_cli.commands.activate_session').start()
        self.running_in_bg = mock.patch('koji_cli.commands._running_in_bg').start()
        self.running_in_bg.return_value = False
        self.watch_tasks = mock.patch('koji_cli.commands.watch_tasks').start()
        self.watch_tasks.return_value = True

    def tearDown(self):
        mock.patch.stopall()

    def test_handle_move_build(self):
        """Test handle_move_build function"""
        pkgs = ['pkg_a-1.0-1fc26', 'pkg_b-2.0-1fc26', 'pkg_c-2.2-2fc26']
        arguments = ['tag-a', 'tag-b'] + pkgs
        tasks = [202, 303]

        self.options.quiet = False
        self.options.force = False
        self.options.poll_interval = 100

        self.session.getBuild.side_effect = [
            {'id': 11, 'name': 'pkg_a', 'version': '1.0', 'release': '1fc26'},
            {'id': 22, 'name': 'pkg_b', 'version': '2.0', 'release': '1fc26'},
            {},             # assume pkg_c-2.2-2fc26 is invalid
        ]
        self.session.moveBuild.side_effect = tasks

        expected = 'Invalid build %s, skipping.' % 'pkg_c-2.2-2fc26' + "\n"
        for i, t in enumerate(tasks):
            expected += "Created task %d, moving %s" % (t, pkgs[i]) + "\n"

        with mock.patch('sys.stdout', new_callable=six.StringIO) as stdout:
            rv = handle_move_build(self.options, self.session, arguments)

        # sanity checks
        self.assertEqual(rv, True)
        self.assert_console_message(stdout, expected)
        self.activate_session.assert_called_with(self.session, self.options)
        self.session.logout.assert_called_once()
        self.watch_tasks.assert_called_with(
            self.session,
            tasks,
            quiet=self.options.quiet,
            poll_interval=self.options.poll_interval)

    def test_handle_move_build_nowait(self):
        """Test handle_move_build function with --nowait option"""
        pkgs = ['pkg_a-1.0-1fc26']
        arguments = ['tag-a', 'tag-b', '--nowait'] + pkgs
        task_id = 999

        self.session.getBuild.side_effect = [
            {'id': 11, 'name': 'pkg_a', 'version': '1.0', 'release': '1fc26'},
        ]
        self.session.moveBuild.side_effect = [task_id]

        expected = "Created task %d, moving %s" % (task_id, pkgs[0]) + "\n"

        with mock.patch('sys.stdout', new_callable=six.StringIO) as stdout:
            rv = handle_move_build(self.options, self.session, arguments)

        # sanity checks
        self.assertEqual(rv, None)
        self.assert_console_message(stdout, expected)
        self.activate_session.assert_called_with(self.session, self.options)
        self.session.logout.assert_not_called()
        self.watch_tasks.assert_not_called()

    def test_handle_move_build_with_all_option(self):
        """Test handle_move_build function with --all option"""
        pkgs = ['pkg_a-1.0-1fc26', 'pkg_b-2.0-1fc26', 'pkg_c-2.2-2fc26']
        arguments = ['tag-a', 'tag-b', '--all', '--nowait'] + pkgs

        self.session.getPackage.side_effect = [
            {'id': 44, 'name': 'pkg_a', 'version': '1.0', 'release': '1fc26'},
            {'id': 55, 'name': 'pkg_b', 'version': '2.0', 'release': '1fc26'},
            {},             # assume pkg_c-2.2-2fc26 is invalid
        ]
        self.session.moveAllBuilds.side_effect = [
            [500, 501, 502], [601, 602, 603]
        ]

        expected = 'Invalid package name %s, skipping.' % 'pkg_c-2.2-2fc26' + "\n"
        with mock.patch('sys.stdout', new_callable=six.StringIO) as stdout:
            rv = handle_move_build(self.options, self.session, arguments)

        self.assertEqual(rv, None)
        self.assert_console_message(stdout, expected)
        self.session.moveAllBuilds.assert_has_calls(
            [mock.call(arguments[0], arguments[1], p, None) for p in pkgs[:-1]]
        )

    def test_handle_move_build_argument_error(self):
        """Test handle_move_build function with wrong argument"""

        # Case 1. without --all option
        expected = self.format_error_message(
            "This command takes at least three arguments: two tags and one or more package n-v-r's")
        for arg in [[], ['tag1'], ['tag1', 'tag2']]:
            self.assert_system_exit(
                handle_move_build,
                self.options,
                self.session,
                arg,
                stderr=expected,
                activate_session=None)

        # Case 2. with --all option
        expected = self.format_error_message(
            "This command, with --all, takes at least three arguments: two tags and one or more package names")
        for arg in [['--all', 'tag1'], ['--all', 'tag1', 'tag2']]:
            self.assert_system_exit(
                handle_move_build,
                self.options,
                self.session,
                arg,
                stderr=expected,
                activate_session=None)

    def test_handle_move_build_help(self):
        """Test handle_move_build help message"""
        self.assert_help(
            handle_move_build,
            """Usage: %s move-build [options] <tag1> <tag2> <pkg> [<pkg> ...]
(Specify the --help global option for a list of other help options)

Options:
  -h, --help  show this help message and exit
  --force     force operation
  --nowait    do not wait on tasks
  --all       move all instances of a package, <pkg>'s are package names
""" % self.progname)


if __name__ == '__main__':
    unittest.main()
