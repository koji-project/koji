from __future__ import absolute_import
import koji
import locale
try:
    from unittest import mock
except ImportError:
    import mock
import os
import time
from six.moves import StringIO

from koji_cli.commands import handle_promote_build
from . import utils


class TestPromoteBuild(utils.CliTestCase):
    def setUp(self):
        self.maxDiff = None
        self.options = mock.MagicMock()
        self.session = mock.MagicMock()
        self.buildinfo = {'id': 1,
                          'name': 'foo-bar',
                          'nvr': 'foo-bar-1.1-11',
                          'package_id': 2,
                          'package_name': 'test-rpm',
                          'release': '11#draft_1',
                          'version': '1.1',
                          'draft': True}
        self.target_binfo = self.buildinfo.copy()
        self.target_binfo['relesae'] = '11'
        self.target_binfo['draft'] = False
        self.error_format = """Usage: %s promote-build [options] <draft-build>
(Specify the --help global option for a list of other help options)

%s: error: {message}
""" % (self.progname, self.progname)

    @mock.patch('sys.stdout', new_callable=StringIO)
    @mock.patch('koji_cli.commands.activate_session')
    def test_handle_promote_build_valid(self, activate_session, stdout):
        build_nvr = 'foo-bar-1.1-11'
        self.session.getBuild.return_value = self.buildinfo
        self.session.promoteBuild.return_value = self.target_binfo
        expected_output = "foo-bar-1.1-11 has been promoted to foo-bar-1.1-11\n"                 
        handle_promote_build(self.options, self.session, [build_nvr])
        self.assert_console_message(stdout, expected_output)
        activate_session.assert_called_once_with(self.session, self.options)
        self.session.getBuild.assert_called_once_with(build_nvr)
        self.session.promoteBuild.assert_called_once_with(self.buildinfo['id'], force=False)

    def test_handle_promote_build_non_exist_build(self):
        build_nvr = 'foo-bar-1.1-11'
        self.session.getBuild.return_value = None
        expected = "No such build: %s\n" % build_nvr
        self.assert_system_exit(
            handle_promote_build,
            self.options, self.session, [build_nvr],
            stdout='',
            stderr=expected,
            exit_code=1)

    def test_handle_promote_build_not_draft(self):
        build_nvr = 'foo-bar-1.1-11'
        self.session.getBuild.return_value = self.target_binfo
        expected = "Not a draft build: %s\n" % build_nvr
        self.assert_system_exit(
            handle_promote_build,
            self.options, self.session, [build_nvr],
            stdout='',
            stderr=expected,
            exit_code=1)
    
    def test_promote_build_force_not_admin(self):
        arguments = ['--force', 'build']
        self.session.hasPerm.return_value = False
        self.assert_system_exit(
            handle_promote_build,
            self.options, self.session, arguments,
            stdout='',
            stderr=self.format_error_message("--force requires admin privilege"),
            exit_code=2)
        self.session.getBuild.assert_not_called()
        self.session.promoteBuild.assert_not_called()

    def test_promote_build_without_option(self):
        arguments = []
        self.assert_system_exit(
            handle_promote_build,
            self.options, self.session, arguments,
            stdout='',
            stderr=self.format_error_message("Please specify a draft build"),
            exit_code=2,
            activate_session=None)
        self.session.getBuild.assert_not_called()
        self.session.promoteBuild.assert_not_called()

    def test_promote_build_help(self):
        self.assert_help(
            handle_promote_build,
            """Usage: %s promote-build [options] <draft-build>
(Specify the --help global option for a list of other help options)

Options:
  -h, --help   show this help message and exit
  -f, --force  force operation
""" % self.progname)
