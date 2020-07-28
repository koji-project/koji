from __future__ import absolute_import
import mock
import os
import six
import sys

from koji_cli.commands import handle_edit_tag
from . import utils

progname = os.path.basename(sys.argv[0]) or 'koji'


class TestEditTag(utils.CliTestCase):
    # Show long diffs in error output...
    maxDiff = None

    @mock.patch('sys.stdout', new_callable=six.StringIO)
    @mock.patch('koji_cli.commands.activate_session')
    def test_handle_edit_tag(self, activate_session_mock, stdout):
        tag = 'tag'
        arches = 'arch1 arch2'
        perm = 'perm'
        locked = True
        rename = 'tag2'
        maven_support = True
        maven_include_all = True
        extra = {'extraA': 'A', 'extraB': True}
        remove_extra = ['extraC', 'extraD']
        args = [tag]
        args.append('--arches=' + arches)
        args.append('--perm=' + perm)
        args.append('--lock')
        args.append('--rename=' + rename)
        args.append('--maven-support')
        args.append('--include-all')
        for k, x in six.iteritems(extra):
            args.append('-x')
            args.append(k + '=' + str(x))
        for r in remove_extra:
            args.append('-r')
            args.append(r)
        opts = {'arches': arches,
                'perm': perm,
                'locked': locked,
                'name': rename,
                'maven_support': maven_support,
                'maven_include_all': maven_include_all,
                'extra': extra,
                'remove_extra': remove_extra}
        options = mock.MagicMock()

        # Mock out the xmlrpc server
        session = mock.MagicMock()

        # Run it and check immediate output
        # args: tag --arches='arch1 arch2' --perm --lock
        # --rename=tag2 --maven-support --include-all
        # -x extraA=A -x extraB=True -r extraC -r extraD
        # expected: success
        rv = handle_edit_tag(options, session, args)
        actual = stdout.getvalue()
        expected = ''
        self.assertMultiLineEqual(actual, expected)
        # Finally, assert that things were called as we expected.
        activate_session_mock.assert_called_once_with(session, options)
        session.editTag2.assert_called_once_with(tag, **opts)
        self.assertEqual(rv, None)

        stdout.seek(0)
        stdout.truncate()
        session.reset_mock()
        activate_session_mock.reset_mock()
        args = [tag]
        args.append('--no-perm')
        args.append('--unlock')
        args.append('--no-maven-support')
        args.append('--no-include-all')
        opts = {'perm': None,
                'locked': not locked,
                'maven_support': not maven_support,
                'maven_include_all': not maven_include_all}
        # Run it and check immediate output
        # args: tag --no-perm --unlock --no-maven-support --no-include-all
        # expected: success
        rv = handle_edit_tag(options, session, args)
        actual = stdout.getvalue()
        expected = ''
        self.assertMultiLineEqual(actual, expected)
        # Finally, assert that things were called as we expected.
        activate_session_mock.assert_called_once_with(session, options)
        session.editTag2.assert_called_once_with(tag, **opts)
        self.assertEqual(rv, None)

    @mock.patch('sys.stdout', new_callable=six.StringIO)
    @mock.patch('sys.stderr', new_callable=six.StringIO)
    @mock.patch('koji_cli.commands.activate_session')
    def test_handle_edit_tag_help(self, activate_session_mock, stderr, stdout):
        args = ['--help']
        options = mock.MagicMock()

        # Mock out the xmlrpc server
        session = mock.MagicMock()

        # Run it and check immediate output
        # args: --help
        # expected: failed, help info shows
        with self.assertRaises(SystemExit) as ex:
            handle_edit_tag(options, session, args)
        self.assertExitCode(ex, 0)
        actual_stdout = stdout.getvalue()
        actual_stderr = stderr.getvalue()
        expected_stdout = """Usage: %s edit-tag [options] <name>
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
                        Set tag extra option
  -r key, --remove-extra=key
                        Remove tag extra option
""" % progname
        expected_stderr = ''
        self.assertMultiLineEqual(actual_stdout, expected_stdout)
        self.assertMultiLineEqual(actual_stderr, expected_stderr)
        # Finally, assert that things were called as we expected.
        activate_session_mock.assert_not_called()
        session.editTag2.assert_not_called()

    @mock.patch('sys.stdout', new_callable=six.StringIO)
    @mock.patch('sys.stderr', new_callable=six.StringIO)
    @mock.patch('koji_cli.commands.activate_session')
    def test_handle_edit_tag_no_arg(self, activate_session_mock, stderr, stdout):
        args = []
        options = mock.MagicMock()

        # Mock out the xmlrpc server
        session = mock.MagicMock()

        # Run it and check immediate output
        # args: --help
        # expected: failed, help info shows
        with self.assertRaises(SystemExit) as ex:
            handle_edit_tag(options, session, args)
        self.assertExitCode(ex, 2)
        actual_stdout = stdout.getvalue()
        actual_stderr = stderr.getvalue()
        expected_stdout = ''
        expected_stderr = """Usage: %(progname)s edit-tag [options] <name>
(Specify the --help global option for a list of other help options)

%(progname)s: error: Please specify a name for the tag
""" % {'progname': progname}
        self.assertMultiLineEqual(actual_stdout, expected_stdout)
        self.assertMultiLineEqual(actual_stderr, expected_stderr)
        # Finally, assert that things were called as we expected.
        activate_session_mock.assert_not_called()
        session.editTag2.assert_not_called()
