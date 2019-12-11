from __future__ import absolute_import
import mock
import six
try:
    import unittest2 as unittest
except ImportError:
    import unittest

from koji_cli.commands import handle_tag_build
from . import utils


class TestTagBuild(utils.CliTestCase):

    # Show long diffs in error output...
    maxDiff = None

    def setUp(self):
        self.session = mock.MagicMock()
        self.options = mock.MagicMock()

        self.error_format = """Usage: %s tag-build [options] <tag> <pkg> [<pkg> ...]
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

    def test_handle_tag_build(self):
        """Test handle_tag_build function"""
        pkgs = ['pkg_a-1.0-1fc26', 'pkg_b-2.0-1fc26', 'pkg_c-2.2-2fc26']
        arguments = ['tag'] + pkgs
        tasks = [1001, 2002, 3003]

        self.options.quiet = False
        self.options.poll_interval = 100

        self.session.tagBuild.side_effect = tasks
        expected = ''.join(["Created task %d" % t + "\n" for t in tasks])
        with mock.patch('sys.stdout', new_callable=six.StringIO) as stdout:
            rv = handle_tag_build(self.options, self.session, arguments)
        self.assertEqual(rv, True)
        self.assert_console_message(stdout, expected)
        self.activate_session.assert_called_with(self.session, self.options)

        self.session.logout.assert_called_once()
        self.watch_tasks.assert_called_with(
            self.session,
            tasks,
            quiet=self.options.quiet,
            poll_interval=self.options.poll_interval)

    def test_handle_tag_build_quiet_mode(self):
        """Test handle_tag_build function with --nowait option"""
        pkgs = ['pkg_a-1.0-1fc26']
        arguments = ['tag', '--nowait'] + pkgs
        task_id = 4004

        expected = "Created task %d" % task_id + "\n"
        self.session.tagBuild.side_effect = [task_id]
        with mock.patch('sys.stdout', new_callable=six.StringIO) as stdout:
            rv = handle_tag_build(self.options, self.session, arguments)
        self.assertEqual(rv, None)
        self.assert_console_message(stdout, expected)
        self.activate_session.assert_called_with(self.session, self.options)
        self.watch_tasks.assert_not_called()

    def test_handle_tag_build_argument_error(self):
        """Test handle_tag_build function with error argument"""
        expected = self.format_error_message(
            "This command takes at least two arguments: a tag name/ID and one or more package n-v-r's")
        for arg in [[], ['tag']]:
            self.assert_system_exit(
                handle_tag_build,
                self.options,
                self.session,
                arg,
                stderr=expected,
                activate_session=None)

    def test_handle_tag_build_help(self):
        self.assert_help(
            handle_tag_build,
            """Usage: %s tag-build [options] <tag> <pkg> [<pkg> ...]
(Specify the --help global option for a list of other help options)

Options:
  -h, --help  show this help message and exit
  --force     force operation
  --nowait    Do not wait on task
""" % self.progname)


if __name__ == '__main__':
    unittest.main()
