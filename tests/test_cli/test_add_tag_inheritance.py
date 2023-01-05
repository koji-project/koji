from __future__ import absolute_import

import mock
from six.moves import StringIO

import koji
from koji_cli.commands import handle_add_tag_inheritance
from . import utils


class TestAddTagInheritance(utils.CliTestCase):
    def setUp(self):
        self.options = mock.MagicMock()
        self.options.debug = False
        self.session = mock.MagicMock()
        self.session.getAPIVersion.return_value = koji.API_VERSION
        self.activate_session_mock = mock.patch('koji_cli.commands.activate_session').start()
        self.error_format = """Usage: %s add-tag-inheritance [options] <tag> <parent-tag>
(Specify the --help global option for a list of other help options)

%s: error: {message}
""" % (self.progname, self.progname)
        self.tag_inheritance = {'child_id': 1,
                                'intransitive': False,
                                'maxdepth': None,
                                'name': 'parent-test-tag',
                                'noconfig': False,
                                'parent_id': 2,
                                'pkg_filter': '',
                                'priority': 10}
        self.tag_1 = {'arches': 'x86_64',
                      'extra': {},
                      'id': 1,
                      'locked': False,
                      'maven_include_all': False,
                      'maven_support': False,
                      'name': 'test-tag',
                      'perm': None,
                      'perm_id': None}
        self.tag_2 = {'arches': 'x86_64',
                      'extra': {},
                      'id': 2,
                      'locked': False,
                      'maven_include_all': False,
                      'maven_support': False,
                      'name': 'parent-test-tag',
                      'perm': None,
                      'perm_id': None}
        self.tag_3 = {'arches': 'x86_64',
                      'extra': {},
                      'id': 3,
                      'locked': False,
                      'maven_include_all': False,
                      'maven_support': False,
                      'name': 'parent-test-tag-3',
                      'perm': None,
                      'perm_id': None}

    def test_add_tag_inheritance_without_option(self):
        arguments = []
        expected = self.format_error_message(
            "This command takes exactly two arguments: a tag name or ID and that tag's new "
            "parent name or ID")
        self.assert_system_exit(
            handle_add_tag_inheritance,
            self.options, self.session, arguments,
            stdout='',
            stderr=expected,
            exit_code=2,
            activate_session=None)
        self.activate_session_mock.assert_not_called()

    def test_add_tag_inheritance_non_exist_tag(self):
        tag = 'test-tag'
        parent_tag = 'parent-test-tag'
        arguments = [tag, parent_tag]
        self.session.getTag.return_value = None

        self.assert_system_exit(
            handle_add_tag_inheritance,
            self.options, self.session, arguments,
            stdout='',
            stderr=self.format_error_message("No such tag: %s" % tag),
            exit_code=2,
            activate_session=None)
        self.activate_session_mock.assert_called_once_with(self.session, self.options)

    def test_add_tag_inheritance_non_exist_parent_tag(self):
        tag = 'test-tag'
        parent_tag = 'parent-test-tag'
        arguments = [tag, parent_tag]
        self.session.getTag.side_effect = [self.tag_1, None]
        self.assert_system_exit(
            handle_add_tag_inheritance,
            self.options, self.session, arguments,
            stdout='',
            stderr=self.format_error_message("No such tag: %s" % parent_tag),
            exit_code=2,
            activate_session=None)
        self.activate_session_mock.assert_called_once_with(self.session, self.options)

    def test_add_tag_inheritance_same_parents_without_force(self):
        tag = 'test-tag'
        parent_tag = 'parent-test-tag'
        arguments = ['--priority=10', tag, parent_tag]
        self.session.getInheritanceData.return_value = [self.tag_inheritance, self.tag_inheritance]
        self.session.getTag.side_effect = [self.tag_1, self.tag_2]
        expected_error = "Error: You are attempting to add %s as %s's parent even though it " \
                         "already is %s's parent.\nPlease use --force if this is what you " \
                         "really want to do.\n" % (parent_tag, tag, tag)
        self.assert_system_exit(
            handle_add_tag_inheritance,
            self.options, self.session, arguments,
            stdout='',
            stderr=expected_error,
            exit_code=1,
            activate_session=None)
        self.activate_session_mock.assert_called_once_with(self.session, self.options)

    def test_add_tag_inheritance_same_priority_without_force(self):
        tag = 'test-tag'
        parent_tag = 'parent-test-tag-3'
        arguments = ['--priority=10', tag, parent_tag]
        self.session.getInheritanceData.return_value = [self.tag_inheritance, self.tag_inheritance]
        self.session.getTag.side_effect = [self.tag_1, self.tag_3]
        expected_error = "Error: There is already an active inheritance with that priority " \
                         "on %s, please specify a different priority with --priority.\n" % tag
        self.assert_system_exit(
            handle_add_tag_inheritance,
            self.options, self.session, arguments,
            stdout='',
            stderr=expected_error,
            exit_code=1,
            activate_session=None)
        self.activate_session_mock.assert_called_once_with(self.session, self.options)

    @mock.patch('sys.stderr', new_callable=StringIO)
    @mock.patch('sys.stdout', new_callable=StringIO)
    def test_add_tag_inheritance_valid(self, stdout, stderr):
        tag = 'test-tag'
        parent_tag = 'parent-test-tag-3'
        self.session.getInheritanceData.return_value = [self.tag_inheritance, self.tag_inheritance]
        self.session.getTag.side_effect = [self.tag_1, self.tag_3]
        handle_add_tag_inheritance(self.options, self.session, ['--priority=5', tag, parent_tag])
        self.assert_console_message(stdout, '')
        self.assert_console_message(stderr, '')
        self.activate_session_mock.assert_called_once_with(self.session, self.options)

    @mock.patch('sys.stderr', new_callable=StringIO)
    @mock.patch('sys.stdout', new_callable=StringIO)
    def test_add_tag_inheritance_valid_with_maxdepth(self, stdout, stderr):
        tag = 'test-tag'
        parent_tag = 'parent-test-tag-3'
        self.session.getInheritanceData.return_value = [self.tag_inheritance, self.tag_inheritance]
        self.session.getTag.side_effect = [self.tag_1, self.tag_3]
        handle_add_tag_inheritance(self.options, self.session,
                                   ['--maxdepth=10', '--priority=5', tag, parent_tag])
        self.assert_console_message(stdout, '')
        self.assert_console_message(stderr, '')
        self.activate_session_mock.assert_called_once_with(self.session, self.options)

    def test_add_tag_inheritance_help(self):
        self.assert_help(
            handle_add_tag_inheritance,
            """Usage: %s add-tag-inheritance [options] <tag> <parent-tag>
(Specify the --help global option for a list of other help options)

Options:
  -h, --help            show this help message and exit
  --priority=PRIORITY   Specify priority
  --maxdepth=MAXDEPTH   Specify max depth
  --intransitive        Set intransitive
  --noconfig            Set to packages only
  --pkg-filter=PKG_FILTER
                        Specify the package filter
  --force               Force adding a parent to a tag that already has that
                        parent tag
""" % self.progname)
