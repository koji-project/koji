from __future__ import absolute_import

import mock
from six.moves import StringIO

import koji
from koji_cli.commands import handle_remove_target
from . import utils


class TestRemoveTarget(utils.CliTestCase):
    def setUp(self):
        self.options = mock.MagicMock()
        self.options.debug = False
        self.session = mock.MagicMock()
        self.session.getAPIVersion.return_value = koji.API_VERSION

    @mock.patch('sys.stderr', new_callable=StringIO)
    def test_remove_target_without_option(self, stderr):
        expected = "Usage: %s remove-target [options] <name>\n" \
                   "(Specify the --help global option for a list of other help options)\n\n" \
                   "%s: error: Please specify a build target to " \
                   "remove\n" % (self.progname, self.progname)
        with self.assertRaises(SystemExit) as ex:
            handle_remove_target(self.options, self.session, [])
        self.assertExitCode(ex, 2)
        self.assert_console_message(stderr, expected)

    @mock.patch('sys.stderr', new_callable=StringIO)
    def test_remove_target_non_exist_target(self, stderr):
        target = 'test-target'
        expected = "No such build target: %s\n" % target
        self.session.getBuildTarget.return_value = None
        with self.assertRaises(SystemExit) as ex:
            handle_remove_target(self.options, self.session, [target])
        self.assertExitCode(ex, 1)
        self.assert_console_message(stderr, expected)

    def test_remove_target_valid(self):
        build_target = {'build_tag': 2,
                        'build_tag_name': 'test-tag',
                        'dest_tag': 1,
                        'dest_tag_name': 'test-dest-tag',
                        'id': 1,
                        'name': 'test-target'}

        self.session.getBuildTarget.return_value = build_target
        self.session.deleteBuildTarget.return_value = None
        rv = handle_remove_target(self.options, self.session, [build_target['name']])
        self.assertEqual(rv, None)
        self.session.deleteBuildTarget.assert_called_once_with(build_target['id'])
        self.session.getBuildTarget.assert_called_with(build_target['name'])

    def test_remove_target_help(self):
        self.assert_help(
            handle_remove_target,
            """Usage: %s remove-target [options] <name>
(Specify the --help global option for a list of other help options)

Options:
  -h, --help  show this help message and exit
""" % self.progname)
