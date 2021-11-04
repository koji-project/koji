from __future__ import absolute_import
import mock
import unittest

from koji_cli.commands import handle_add_tag
from . import utils


class TestAddTag(utils.CliTestCase):

    def setUp(self):
        self.maxDiff = None
        self.options = mock.MagicMock()
        self.options.quiet = True
        self.options.debug = False
        self.session = mock.MagicMock()
        self.activate_session_mock = mock.patch('koji_cli.commands.activate_session').start()
        self.error_format = """Usage: %s add-tag [options] <name>
(Specify the --help global option for a list of other help options)

%s: error: {message}
""" % (self.progname, self.progname)

    def test_handle_add_tag(self):
        """Test handle_add_tag function"""
        # Case 1. no argument error
        self.assert_system_exit(
            handle_add_tag,
            self.options, self.session, [],
            stderr=self.format_error_message("Please specify a name for the tag"),
            exit_code=2,
            activate_session=None)
        self.activate_session_mock.assert_not_called()
        self.activate_session_mock.reset_mock()

        # Case 2. not admin account
        self.session.hasPerm.return_value = None
        self.assert_system_exit(
            handle_add_tag,
            self.options, self.session, ['test-tag'],
            stdout='',
            stderr=self.format_error_message("This action requires tag or admin privileges"),
            exit_code=2,
        )
        self.activate_session_mock.assert_not_called()
        self.activate_session_mock.reset_mock()

        # Case 3. options test
        arguments = ['test-tag',
                     '--parent', 'parent',
                     '--arch', 'x86_64',
                     '--maven-support', '--include-all']
        # extra fields,
        arguments += ['--extra', 'mock.package_manager=dnf',
                      '--extra', 'mock.new_chroot=0']

        opts = {
            'parent': 'parent',
            'arches': 'x86_64',
            'maven_support': True,
            'maven_include_all': True,
            'extra':
            {
                'mock.package_manager': 'dnf',
                'mock.new_chroot': 0,
            }
        }

        self.session.hasPerm.return_value = True
        handle_add_tag(self.options, self.session, arguments)
        self.session.createTag.assert_called_with('test-tag', **opts)
        self.activate_session_mock.assert_called_once_with(self.session, self.options)

    def test_handle_add_tag_help(self):
        self.assert_help(
            handle_add_tag,
            """Usage: %s add-tag [options] <name>
(Specify the --help global option for a list of other help options)

Options:
  -h, --help            show this help message and exit
  --parent=PARENT       Set a parent tag with priority 0
  --arches=ARCHES       Specify arches
  --maven-support       Enable creation of Maven repos for this tag
  --include-all         Include all packages in this tag when generating Maven
                        repos
  -x key=value, --extra=key=value
                        Set tag extra option
""" % self.progname)


if __name__ == '__main__':
    unittest.main()
