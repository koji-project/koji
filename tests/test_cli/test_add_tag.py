from __future__ import absolute_import
import mock
import six
try:
    import unittest2 as unittest
except ImportError:
    import unittest

from koji_cli.commands import handle_add_tag
from . import utils


class TestAddTag(utils.CliTestCase):

    # Show long diffs in error output...
    maxDiff = None

    def setUp(self):
        self.error_format = """Usage: %s add-tag [options] <name>
(Specify the --help global option for a list of other help options)

%s: error: {message}
""" % (self.progname, self.progname)

    @mock.patch('sys.stdout', new_callable=six.StringIO)
    @mock.patch('koji_cli.commands.activate_session')
    def test_handle_add_tag(
            self,
            activate_session_mock,
            stdout):
        """Test handle_add_tag function"""
        session = mock.MagicMock()
        options = mock.MagicMock()

        # Case 1. no argument error
        expected = self.format_error_message(
            "Please specify a name for the tag")
        self.assert_system_exit(
            handle_add_tag,
            options,
            session,
            [],
            stderr=expected,
            activate_session=None)

        # Case 2. not admin account
        session.hasPerm.return_value = None
        self.assert_system_exit(
            handle_add_tag,
            options, session, ['test-tag'],
            stdout='',
            stderr=self.format_error_message("This action requires tag or admin privileges"),
        )

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

        session.hasPerm.return_value = True
        handle_add_tag(options, session, arguments)
        session.createTag.assert_called_with('test-tag', **opts)

    def test_handle_add_tag_help(self):
        self.assert_help(
            handle_add_tag,
            """Usage: %s add-tag [options] <name>
(Specify the --help global option for a list of other help options)

Options:
  -h, --help            show this help message and exit
  --parent=PARENT       Specify parent
  --arches=ARCHES       Specify arches
  --maven-support       Enable creation of Maven repos for this tag
  --include-all         Include all packages in this tag when generating Maven
                        repos
  -x key=value, --extra=key=value
                        Set tag extra option
""" % self.progname)


if __name__ == '__main__':
    unittest.main()
