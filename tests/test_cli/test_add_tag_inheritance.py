from __future__ import absolute_import

import mock

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

    def test_add_tag_inheritance_without_option(self):
        arguments = []
        expected = self.format_error_message(
            "This command takes exctly two argument: a tag name or ID and that tag's new "
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
        side_effect_result = [{'arches': 'x86_64',
                               'extra': {},
                               'id': 1,
                               'locked': False,
                               'maven_include_all': False,
                               'maven_support': False,
                               'name': 'test-tag',
                               'perm': None,
                               'perm_id': None},
                              None]
        tag = 'test-tag'
        parent_tag = 'parent-test-tag'
        arguments = [tag, parent_tag]
        self.session.getTag.side_effect = side_effect_result
        self.assert_system_exit(
            handle_add_tag_inheritance,
            self.options, self.session, arguments,
            stdout='',
            stderr=self.format_error_message("No such tag: %s" % parent_tag),
            exit_code=2,
            activate_session=None)
        self.activate_session_mock.assert_called_once_with(self.session, self.options)
