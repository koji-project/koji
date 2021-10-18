from __future__ import absolute_import

import copy

import mock
from six.moves import StringIO

import koji
from koji_cli.commands import handle_edit_target
from . import utils


class TestEditTarget(utils.CliTestCase):
    def setUp(self):
        self.options = mock.MagicMock()
        self.options.debug = False
        self.session = mock.MagicMock()
        self.session.getAPIVersion.return_value = koji.API_VERSION
        self.build_target_info = {'build_tag': 444,
                                  'build_tag_name': 'test-tag',
                                  'dest_tag': 445,
                                  'dest_tag_name': 'dest-test-tag',
                                  'id': 1,
                                  'name': 'test-target'}
        self.dest_tag_info = {'arches': 'x86_64',
                              'extra': {},
                              'id': 1,
                              'name': 'new-dest-tag'}
        self.build_tag_info = {'arches': 'x86_64',
                               'extra': {},
                               'id': 1,
                               'name': 'new-build-tag'}

    @mock.patch('sys.stderr', new_callable=StringIO)
    def test_edit_target_without_option(self, stderr):
        expected = "Usage: %s edit-target [options] <name>\n" \
                   "(Specify the --help global option for a list of other help options)\n\n" \
                   "%s: error: Please specify a build target\n" % (self.progname, self.progname)
        with self.assertRaises(SystemExit) as ex:
            handle_edit_target(self.options, self.session, [])
        self.assertExitCode(ex, 2)
        self.assert_console_message(stderr, expected)

    def test_edit_target_non_exist_target(self):
        target = 'test-target'
        expected = "No such build target: %s" % target
        self.session.getBuildTarget.return_value = None
        with self.assertRaises(koji.GenericError) as cm:
            handle_edit_target(self.options, self.session, [target])
        self.assertEqual(expected, str(cm.exception))
        self.session.getTag.assert_not_called()
        self.session.editBuildTarget.assert_not_called()

    @mock.patch('sys.stderr', new_callable=StringIO)
    def test_edit_target_non_exist_dest_tag(self, stderr):
        target = 'test-target'
        dest_tag = 'test-dest-tag'
        expected = "No such destination tag: %s\n" % dest_tag
        self.session.getTag.return_value = None
        with self.assertRaises(SystemExit) as ex:
            handle_edit_target(self.options, self.session, ['--dest-tag', dest_tag, target])
        self.assertExitCode(ex, 1)
        self.assert_console_message(stderr, expected)
        self.session.editBuildTarget.assert_not_called()

    @mock.patch('sys.stderr', new_callable=StringIO)
    def test_edit_target_without_perms(self, stderr):
        side_effect_result = [False, False]

        target = 'test-target'
        self.session.hasPerm.side_effect = side_effect_result
        with self.assertRaises(SystemExit) as ex:
            handle_edit_target(self.options, self.session, [target])
        self.assertExitCode(ex, 2)
        expected_msg = """Usage: %s edit-target [options] <name>
(Specify the --help global option for a list of other help options)

%s: error: This action requires target or admin privileges
""" % (self.progname, self.progname)
        self.assert_console_message(stderr, expected_msg)
        self.session.editBuildTarget.assert_not_called()
        self.session.getBuildTarget.assert_not_called()

    @mock.patch('sys.stdout', new_callable=StringIO)
    def test_edit_target_new_name(self, stdout):
        target = 'test-target'
        new_target_name = 'new-test-target'
        self.session.getBuildTarget.return_value = self.build_target_info
        rv = handle_edit_target(self.options, self.session, ['--rename', new_target_name, target])
        self.assertEqual(rv, None)
        expected_msg = ''
        self.assert_console_message(stdout, expected_msg)
        self.session.getTag.assert_not_called()
        self.session.getBuildTarget.assert_called_once_with(target)
        self.session.editBuildTarget.assert_called_once_with(
            self.build_target_info['orig_name'], new_target_name,
            self.build_target_info['build_tag_name'], self.build_target_info['dest_tag_name'])

    @mock.patch('sys.stdout', new_callable=StringIO)
    def test_edit_target_dest_tag(self, stdout):
        target = 'test-target'
        new_dest_tag = 'new-dest-tag'
        self.session.getBuildTarget.return_value = self.build_target_info
        self.session.getTag.return_value = self.dest_tag_info
        rv = handle_edit_target(self.options, self.session, ['--dest-tag', new_dest_tag, target])
        self.assertEqual(rv, None)
        expected_msg = ''
        self.assert_console_message(stdout, expected_msg)
        self.session.getTag.assert_called_once_with(new_dest_tag)
        self.session.getBuildTarget.assert_called_once_with(target)
        self.session.editBuildTarget.assert_called_once_with(
            self.build_target_info['orig_name'], self.build_target_info['name'],
            self.build_target_info['build_tag_name'], self.build_target_info['dest_tag_name'])

    @mock.patch('sys.stderr', new_callable=StringIO)
    def test_edit_target_non_exist_build_tag(self, stderr):
        target = 'test-target'
        new_build_tag = 'new-build-tag'
        self.session.getBuildTarget.return_value = self.build_target_info
        self.session.getTag.return_value = None
        with self.assertRaises(SystemExit) as ex:
            handle_edit_target(self.options, self.session, ['--build-tag', new_build_tag, target])
        self.assertExitCode(ex, 1)
        expected_msg = "No such tag: %s\n" % new_build_tag
        self.assert_console_message(stderr, expected_msg)
        self.session.getTag.assert_called_once_with(new_build_tag)
        self.session.getBuildTarget.assert_called_once_with(target)
        self.session.editBuildTarget.assert_not_called()

    @mock.patch('sys.stderr', new_callable=StringIO)
    def test_edit_target_tag_arch_none(self, stderr):
        target = 'test-target'
        new_build_tag = 'new-build-tag'
        build_tag_info = copy.deepcopy(self.build_tag_info)
        build_tag_info['arches'] = ''
        self.session.getBuildTarget.return_value = self.build_target_info
        self.session.getTag.return_value = build_tag_info
        with self.assertRaises(SystemExit) as ex:
            handle_edit_target(self.options, self.session, ['--build-tag', new_build_tag, target])
        self.assertExitCode(ex, 1)
        expected_msg = "Build tag has no arches: %s\n" % new_build_tag
        self.assert_console_message(stderr, expected_msg)
        self.session.getTag.assert_called_once_with(new_build_tag)
        self.session.getBuildTarget.assert_called_once_with(target)
        self.session.editBuildTarget.assert_not_called()

    @mock.patch('sys.stdout', new_callable=StringIO)
    def test_edit_target_build_tag_valid(self, stdout):
        target = 'test-target'
        new_build_tag = 'new-build-tag'
        self.session.getBuildTarget.return_value = self.build_target_info
        self.session.getTag.return_value = self.build_tag_info
        rv = handle_edit_target(self.options, self.session, ['--build-tag', new_build_tag, target])
        self.assertEqual(rv, None)
        expected_msg = ''
        self.assert_console_message(stdout, expected_msg)
        self.session.getTag.assert_called_once_with(new_build_tag)
        self.session.getBuildTarget.assert_called_once_with(target)
        self.session.editBuildTarget.assert_called_once_with(
            self.build_target_info['orig_name'], self.build_target_info['name'],
            self.build_target_info['build_tag_name'], self.build_target_info['dest_tag_name'])
