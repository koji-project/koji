from __future__ import absolute_import
import mock
import six
import koji

from koji_cli.commands import handle_edit_tag
from . import utils


class TestEditTag(utils.CliTestCase):

    def setUp(self):
        self.options = mock.MagicMock()
        self.options.debug = False
        self.session = mock.MagicMock()
        self.session.getAPIVersion.return_value = koji.API_VERSION
        self.activate_session_mock = mock.patch('koji_cli.commands.activate_session').start()
        self.error_format = """Usage: %s edit-tag [options] <name>
(Specify the --help global option for a list of other help options)

%s: error: {message}
""" % (self.progname, self.progname)
        self.tag = 'tag'
        self.arches = 'arch1 arch2'
        self.perm = 'perm'
        self.locked = True
        self.rename = 'tag2'
        self.maven_support = True
        self.maven_include_all = True
        self.extra = {'extraA': 'A', 'extraB': True}
        self.remove_extra = ['extraC', 'extraD']

    def tearDown(self):
        mock.patch.stopall()

    @mock.patch('sys.stdout', new_callable=six.StringIO)
    def test_handle_edit_tag_1(self, stdout):
        args = [self.tag]
        args.append('--arches=' + self.arches)
        args.append('--perm=' + self.perm)
        args.append('--lock')
        args.append('--rename=' + self.rename)
        args.append('--maven-support')
        args.append('--include-all')
        for k, x in six.iteritems(self.extra):
            args.append('-x')
            args.append(k + '=' + str(x))
        for r in self.remove_extra:
            args.append('-r')
            args.append(r)
        opts = {'arches': self.arches,
                'perm': self.perm,
                'locked': self.locked,
                'name': self.rename,
                'maven_support': self.maven_support,
                'maven_include_all': self.maven_include_all,
                'extra': self.extra,
                'block_extra': [],
                'remove_extra': self.remove_extra}

        # Run it and check immediate output
        # args: tag --arches='arch1 arch2' --perm --lock
        # --rename=tag2 --maven-support --include-all
        # -x extraA=A -x extraB=True -r extraC -r extraD
        # expected: success
        rv = handle_edit_tag(self.options, self.session, args)
        actual = stdout.getvalue()
        expected = ''
        self.assertMultiLineEqual(actual, expected)
        # Finally, assert that things were called as we expected.
        self.activate_session_mock.assert_called_once_with(self.session, self.options)
        self.session.editTag2.assert_called_once_with(self.tag, **opts)
        self.assertEqual(rv, None)

    @mock.patch('sys.stdout', new_callable=six.StringIO)
    def test_handle_edit_tag_2(self, stdout):
        args = [self.tag]
        args.append('--no-perm')
        args.append('--unlock')
        args.append('--no-maven-support')
        args.append('--no-include-all')
        opts = {'perm': None,
                'locked': not self.locked,
                'maven_support': not self.maven_support,
                'block_extra': [],
                'remove_extra': [],
                'maven_include_all': not self.maven_include_all}
        # Run it and check immediate output
        # args: tag --no-perm --unlock --no-maven-support --no-include-all
        # expected: success
        rv = handle_edit_tag(self.options, self.session, args)
        actual = stdout.getvalue()
        expected = ''
        self.assertMultiLineEqual(actual, expected)
        # Finally, assert that things were called as we expected.
        self.activate_session_mock.assert_called_once_with(self.session, self.options)
        self.session.editTag2.assert_called_once_with(self.tag, **opts)
        self.assertEqual(rv, None)

    def test_handle_edit_tag_help(self):
        # Run it and check immediate output
        # args: --help
        # expected: failed, help info shows
        self.assert_help(
            handle_edit_tag,
            """Usage: %s edit-tag [options] <name>
(Specify the --help global option for a list of other help options)

Options:
  -h, --help            show this help message and exit
  --arches=ARCHES       Specify arches
  --perm=PERM           Specify permission requirement
  --no-perm             Remove permission requirement
  --lock                Lock the tag
  --unlock              Unlock the tag
  --rename=RENAME       Rename the tag
  --maven-support       Enable creation of Maven repos for this tag
  --no-maven-support    Disable creation of Maven repos for this tag
  --include-all         Include all packages in this tag when generating Maven
                        repos
  --no-include-all      Do not include all packages in this tag when
                        generating Maven repos
  -x key=value, --extra=key=value
                        Set tag extra option. JSON-encoded or simple value
  -r key, --remove-extra=key
                        Remove tag extra option
  -b key, --block-extra=key
                        Block inherited tag extra option
""" % self.progname)

        # Finally, assert that things were called as we expected.
        self.activate_session_mock.assert_not_called()
        self.session.editTag2.assert_not_called()

    def test_handle_edit_tag_no_arg(self):
        # Run it and check immediate output
        # args: --help
        # expected: failed, help info shows
        expected = self.format_error_message("Please specify a name for the tag")
        self.assert_system_exit(
            handle_edit_tag,
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
        self.session.editTag2.assert_not_called()

    def test_handle_edit_tag_duplicate_extra(self):
        args = [self.tag]
        for k, x in six.iteritems(self.extra):
            args.append('-x')
            args.append(k + '=' + str(x))
        # duplicate item in dict extra
        args.append('-x')
        args.append('extraA=duplicateA')

        # Run it and check immediate output
        # args: tag -x extraA=A -x extraB=True -x extraA=duplicateA
        # expected: failed
        expected = self.format_error_message("Duplicate extra key: extraA")
        self.assert_system_exit(
            handle_edit_tag,
            self.options,
            self.session,
            args,
            stdout='',
            stderr=expected,
            activate_session=None,
            exit_code=2
        )
        # Finally, assert that things were called as we expected.
        self.activate_session_mock.assert_called_once_with(self.session, self.options)
        self.session.editTag2.assert_not_called()
