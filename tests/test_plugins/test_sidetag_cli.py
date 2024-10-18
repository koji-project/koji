from __future__ import absolute_import
import io
try:
    from unittest import mock
except ImportError:
    import mock
import six
import unittest
import os
import sys

import koji
from . import load_plugin

sidetag = load_plugin.load_plugin('cli', 'sidetag_cli')


def mock_stdout():
    def get_mock():
        if six.PY2:
            return six.StringIO()
        else:
            return io.TextIOWrapper(six.BytesIO())
    return mock.patch('sys.stdout', new_callable=get_mock)


def mock_stderr():
    def get_mock():
        if six.PY2:
            return six.StringIO()
        else:
            return io.TextIOWrapper(six.BytesIO())
    return mock.patch('sys.stderr', new_callable=get_mock)


def get_stdout_value(stdout):
    if six.PY2:
        return stdout.getvalue()
    else:
        # we have to force the TextIOWrapper to stop buffering
        return stdout.detach().getvalue()


class TestSideTagCLI(unittest.TestCase):

    def setUp(self):
        # Show long diffs in error output...
        self.maxDiff = None
        self.options = mock.MagicMock()
        self.options.debug = False
        self.options.quiet = False
        self.session = mock.MagicMock()
        self.session.getAPIVersion.return_value = koji.API_VERSION
        self.activate_session_mock = mock.patch('koji_cli.commands.activate_session').start()
        self.progname = os.path.basename(sys.argv[0]) or 'koji'
        self.parser = mock.MagicMock()

    def tearDown(self):
        mock.patch.stopall()

    def __vm(self, result):
        m = koji.VirtualCall('mcall_method', [], {})
        if isinstance(result, dict) and result.get('faultCode'):
            m._result = result
        else:
            m._result = (result,)
        return m

    @mock_stdout()
    def test_add_sidetag_help(self, stdout):
        args = ['--help']
        self.parser.parse_args.return_value = [self.options, args]
        with self.assertRaises(SystemExit) as ex:
            sidetag.handle_add_sidetag(self.options, self.session, args)
        std_output = get_stdout_value(stdout).decode('utf-8')
        expected_help = """Usage: %s add-sidetag [options] <basetag>
(Specify the --help global option for a list of other help options)

Options:
  -h, --help       show this help message and exit
  -q, --quiet      Do not print tag name
  -w, --wait       Wait until repo is ready.
  --debuginfo      Buildroot repo will contain debuginfos
  --suffix=SUFFIX  Suffix from hub-supported ones
""" % self.progname
        self.assertMultiLineEqual(std_output, expected_help)
        self.assertEqual('0', str(ex.exception))

    @mock_stderr()
    def test_add_sidetags_without_args(self, stderr):
        args = []
        # Run it and check immediate output
        self.parser.parse_args.return_value = [self.options, args]
        self.parser.error.side_effect = Exception()
        with self.assertRaises(SystemExit) as ex:
            sidetag.handle_add_sidetag(self.options, self.session, args)
        std_err = get_stdout_value(stderr).decode('utf-8')
        expected_err = """Usage: %s add-sidetag [options] <basetag>
(Specify the --help global option for a list of other help options)

%s: error: Only argument is basetag
""" % (self.progname, self.progname)
        self.assertEqual(std_err, expected_err)
        self.assertEqual('2', str(ex.exception))
        # Finally, assert that things were called as we expected.
        self.session.createSideTag.assert_not_called()

    @mock_stdout()
    def test_add_sidetag_valid(self, stdout):
        args = ['--debuginfo', '--suffix', 'test-suffix', 'sidetag']
        self.session.createSideTag.return_value = {'name': 'sidetag'}
        sidetag.handle_add_sidetag(self.options, self.session, args)
        std_output = get_stdout_value(stdout).decode('utf-8')
        self.assertEqual(std_output, 'sidetag\n')
        self.session.createSideTag.assert_called_once_with(
            'sidetag', debuginfo=True, suffix='test-suffix')

    @mock_stderr()
    def test_add_sidetags_policy_error(self, stderr):
        args = ['--debuginfo', '--suffix', 'test-suffix', 'sidetag']
        self.session.createSideTag.side_effect = koji.ActionNotAllowed("Policy violation")
        # Run it and check immediate output
        with self.assertRaises(SystemExit) as ex:
            sidetag.handle_add_sidetag(self.options, self.session, args)
        std_err = get_stdout_value(stderr).decode('utf-8')
        expected_err = """Usage: %s add-sidetag [options] <basetag>
(Specify the --help global option for a list of other help options)

%s: error: Policy violation
""" % (self.progname, self.progname)
        self.assertEqual(std_err, expected_err)
        self.assertEqual('2', str(ex.exception))
        self.session.createSideTag.assert_called_once_with(
            'sidetag', debuginfo=True, suffix='test-suffix')

    @mock_stderr()
    def test_add_sidetags_old_hub_error(self, stderr):
        args = ['--debuginfo', '--suffix', 'test-suffix', 'sidetag']
        self.session.createSideTag.side_effect = koji.ParameterError('suffix')
        # Run it and check immediate output
        with self.assertRaises(SystemExit) as ex:
            sidetag.handle_add_sidetag(self.options, self.session, args)
        std_err = get_stdout_value(stderr).decode('utf-8')
        expected_err = """Usage: %s add-sidetag [options] <basetag>
(Specify the --help global option for a list of other help options)

%s: error: Hub is older and doesn't support --suffix, please run it without it
""" % (self.progname, self.progname)
        self.assertEqual(std_err, expected_err)
        self.assertEqual('2', str(ex.exception))
        self.session.createSideTag.assert_called_once_with(
            'sidetag', debuginfo=True, suffix='test-suffix')

    @mock_stdout()
    def test_edit_sidetag_help(self, stdout):
        with self.assertRaises(SystemExit) as ex:
            sidetag.handle_edit_sidetag(self.options, self.session, ['--help'])
        std_output = get_stdout_value(stdout).decode('utf-8')
        expected_help = """Usage: %s edit-sidetag [options] <sidetag>
(Specify the --help global option for a list of other help options)

Options:
  -h, --help            show this help message and exit
  --debuginfo           Generate debuginfo repository
  --no-debuginfo        
  --rpm-macro=key=value
                        Set tag-specific rpm macros
  --remove-rpm-macro=key
                        Remove rpm macros
""" % self.progname
        self.assertMultiLineEqual(std_output, expected_help)
        self.assertEqual('0', str(ex.exception))

    @mock_stderr()
    def test_edit_sidetags_with_more_args(self, stderr):
        args = []
        # Run it and check immediate output
        with self.assertRaises(SystemExit) as ex:
            sidetag.handle_edit_sidetag(self.options, self.session, args)
        std_err = get_stdout_value(stderr).decode('utf-8')
        expected_err = """Usage: %s edit-sidetag [options] <sidetag>
(Specify the --help global option for a list of other help options)

%s: error: Only argument is sidetag
""" % (self.progname, self.progname)
        self.assertEqual(std_err, expected_err)
        self.assertEqual('2', str(ex.exception))
        # Finally, assert that things were called as we expected.
        self.session.editSideTag.assert_not_called()

    @mock_stderr()
    def test_edit_sidetags_without_option(self, stderr):
        args = ['arg']
        # Run it and check immediate output
        with self.assertRaises(SystemExit) as ex:
            sidetag.handle_edit_sidetag(self.options, self.session, [args])
        std_err = get_stdout_value(stderr).decode('utf-8')
        expected_err = """Usage: %s edit-sidetag [options] <sidetag>
(Specify the --help global option for a list of other help options)

%s: error: At least one option needs to be specified
""" % (self.progname, self.progname)
        self.assertEqual(std_err, expected_err)
        self.assertEqual('2', str(ex.exception))
        # Finally, assert that things were called as we expected.
        self.session.editSideTag.assert_not_called()

    @mock_stdout()
    def test_edit_sidetags_valid(self, stdout):
        args = ['--debuginfo', '--rpm-macro', 'macroname1=macrovalue1',
                '--rpm-macro', 'macroname2=macrovalue2', '--remove-rpm-macro', 'macroname3',
                'sidetag']
        self.session.editSideTag.return_value = None
        sidetag.handle_edit_sidetag(self.options, self.session, args)
        std_output = get_stdout_value(stdout).decode('utf-8')
        self.assertEqual(std_output, '')
        self.session.editSideTag.assert_called_once_with(
            'sidetag', debuginfo=True, remove_rpm_macros=['macroname3'],
            rpm_macros={'macroname1': 'macrovalue1', 'macroname2': 'macrovalue2'})

    @mock_stdout()
    def test_list_sidetags_help(self, stdout):
        with self.assertRaises(SystemExit) as ex:
            sidetag.handle_list_sidetags(self.options, self.session, ['--help'])
        std_output = get_stdout_value(stdout).decode('utf-8')
        expected_help = """Usage: %s list-sidetags [options]
(Specify the --help global option for a list of other help options)

Options:
  -h, --help         show this help message and exit
  --basetag=BASETAG  Filter on basetag
  --user=USER        Filter on user
  --mine             Filter on user
""" % self.progname
        self.assertMultiLineEqual(std_output, expected_help)
        self.assertEqual('0', str(ex.exception))

    @mock_stderr()
    def test_list_sidetags_with_args(self, stderr):
        args = ['arg']
        # Run it and check immediate output
        with self.assertRaises(SystemExit) as ex:
            sidetag.handle_list_sidetags(self.options, self.session, [args])
        std_err = get_stdout_value(stderr).decode('utf-8')
        expected_err = """Usage: %s list-sidetags [options]
(Specify the --help global option for a list of other help options)

%s: error: This command takes no arguments
""" % (self.progname, self.progname)
        self.assertEqual(std_err, expected_err)
        self.assertEqual('2', str(ex.exception))
        # Finally, assert that things were called as we expected.
        self.session.getLoggedInUser.assert_not_called()
        self.session.listSideTags.assert_not_called()

    @mock_stderr()
    def test_list_sidetags_mine_and_user_option(self, stderr):
        args = ['--mine', '--user', 'testuser']
        self.parser.parse_args.return_value = [self.options, args]
        # Run it and check immediate output
        with self.assertRaises(SystemExit) as ex:
            sidetag.handle_list_sidetags(self.options, self.session, args)
        std_err = get_stdout_value(stderr).decode('utf-8')
        expected_err = """Usage: %s list-sidetags [options]
(Specify the --help global option for a list of other help options)

%s: error: Specify only one from --user --mine
""" % (self.progname, self.progname)
        self.assertEqual(std_err, expected_err)
        self.assertEqual('2', str(ex.exception))
        # Finally, assert that things were called as we expected.
        self.session.getLoggedInUser.assert_not_called()
        self.session.listSideTags.assert_not_called()

    @mock_stdout()
    def test_list_sidetags_mine(self, stdout):
        expected = """test-tag-sidetag_template-21
test-tag-sidetag_template-24
test-tag-sidetag_template-27
"""
        self.session.getLoggedInUser.return_value = {'name': 'testuser'}
        self.session.listSideTags.return_value = [{'id': 21,
                                                   'name': 'test-tag-sidetag_template-21',
                                                   'user_id': '1',
                                                   'user_name': 'testuser'},
                                                  {'id': 24,
                                                   'name': 'test-tag-sidetag_template-24',
                                                   'user_id': '1',
                                                   'user_name': 'testuser'},
                                                  {'id': 27,
                                                   'name': 'test-tag-sidetag_template-27',
                                                   'user_id': '1',
                                                   'user_name': 'testuser'}]
        sidetag.handle_list_sidetags(self.options, self.session, ['--mine'])
        std_output = get_stdout_value(stdout).decode('utf-8')
        self.assertMultiLineEqual(std_output, expected)
        self.session.getLoggedInUser.assert_called_once_with()
        self.session.listSideTags.assert_called_once_with(basetag=None, user='testuser')

    @mock_stdout()
    def test_list_sidetags_user(self, stdout):
        expected = """test-tag-sidetag_template-21
test-tag-sidetag_template-24
test-tag-sidetag_template-27
"""
        self.session.getLoggedInUser.return_value = {'name': 'testuser'}
        self.session.listSideTags.return_value = [{'id': 21,
                                                   'name': 'test-tag-sidetag_template-21',
                                                   'user_id': '1',
                                                   'user_name': 'testuser'},
                                                  {'id': 24,
                                                   'name': 'test-tag-sidetag_template-24',
                                                   'user_id': '1',
                                                   'user_name': 'testuser'},
                                                  {'id': 27,
                                                   'name': 'test-tag-sidetag_template-27',
                                                   'user_id': '1',
                                                   'user_name': 'testuser'}]
        sidetag.handle_list_sidetags(self.options, self.session, ['--user', 'testuser'])
        std_output = get_stdout_value(stdout).decode('utf-8')
        self.assertMultiLineEqual(std_output, expected)
        self.session.getLoggedInUser.assert_not_called()
        self.session.listSideTags.assert_called_once_with(basetag=None, user='testuser')

    @mock_stdout()
    def test_remove_sidetag_help(self, stdout):
        with self.assertRaises(SystemExit) as ex:
            sidetag.handle_remove_sidetag(self.options, self.session, ['--help'])
        std_output = get_stdout_value(stdout).decode('utf-8')
        expected_help = """Usage: %s remove-sidetag [options] <sidetag> ...
(Specify the --help global option for a list of other help options)

Options:
  -h, --help  show this help message and exit
""" % self.progname
        self.assertMultiLineEqual(std_output, expected_help)
        self.assertEqual('0', str(ex.exception))

    @mock_stderr()
    def test_remove_sidetag_without_args(self, stderr):
        args = []
        # Run it and check immediate output
        with self.assertRaises(SystemExit) as ex:
            sidetag.handle_remove_sidetag(self.options, self.session, args)
        std_err = get_stdout_value(stderr).decode('utf-8')
        expected_err = """Usage: %s remove-sidetag [options] <sidetag> ...
(Specify the --help global option for a list of other help options)

%s: error: Sidetag argument is required
""" % (self.progname, self.progname)
        self.assertEqual(std_err, expected_err)
        self.assertEqual('2', str(ex.exception))
        # Finally, assert that things were called as we expected.
        self.session.removeSideTag.assert_not_called()

    @mock_stdout()
    def test_remove_sidetag_valid(self, stdout):
        mcall = self.session.multicall.return_value.__enter__.return_value
        mcall.removeSideTag.return_value = self.__vm([None, None])
        sidetag.handle_remove_sidetag(self.options, self.session, ['sidetag', 'sidetag2'])
        std_output = get_stdout_value(stdout).decode('utf-8')
        self.assertMultiLineEqual(std_output, '')
