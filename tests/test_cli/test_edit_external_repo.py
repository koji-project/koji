# coding=utf-8
from __future__ import absolute_import
import mock
import six
try:
    import unittest2 as unittest
except ImportError:
    import unittest

import koji
from koji_cli.commands import handle_edit_external_repo
from . import utils


class TestEditExternalRepo(utils.CliTestCase):

    # Show long diffs in error output...
    maxDiff = None

    def setUp(self):
        self.options = mock.MagicMock()
        self.session = mock.MagicMock()
        self.error_format = """Usage: %s edit-external-repo [options] <name>
(Specify the --help global option for a list of other help options)

%s: error: {message}
""" % (self.progname, self.progname)

    @mock.patch('sys.stdout', new_callable=six.StringIO)
    @mock.patch('sys.stderr', new_callable=six.StringIO)
    @mock.patch('koji_cli.commands.activate_session')
    def test_handle_edit_external_repo_error(
            self,
            activate_session_mock,
            stderr,
            stdout):
        """Test handle_edit_external_repo function"""
        # [(expected, args),...]
        items = [
            ("Incorrect number of arguments", []),
            ("Incorrect number of arguments", ['arg1', 'arg2']),
            ("No changes specified", ['ext_repo']),
            ("At least, one of priority and merge mode should be specified",
             ['ext_repo', '-t', 'tag']),
            ("If priority is specified, --tag must be specified as well",
             ['ext_repo', '-p', '0']),
            ("If mode is specified, --tag must be specified as well",
             ['ext_repo', '-m', 'koji'])

        ]
        for expected, cmd_args in items:
            self.assert_system_exit(
                handle_edit_external_repo,
                self.options,
                self.session,
                cmd_args,
                stderr=self.format_error_message(expected),
                activate_session=None)

        # edit ext-repo only
        handle_edit_external_repo(self.options, self.session,
                                  ['ext_repo','--name', 'newname', '--url', 'https://newurl'])
        self.assert_console_message(stdout, "")
        self.assert_console_message(stderr, "")
        self.session.editExternalRepo.assert_called_once_with('ext_repo',
                                                              name='newname', url='https://newurl')
        self.session.editTagExternalRepo.assert_not_called()

        # edit tag-repo only
        self.session.reset_mock()
        handle_edit_external_repo(self.options, self.session,
                                  ['ext_repo','-t', 'tag', '-p', '0', '-m', 'koji'])
        self.assert_console_message(stdout, "")
        self.assert_console_message(stderr, "")
        self.session.editExternalRepo.assert_not_called()
        self.session.editTagExternalRepo.assert_called_once_with(repo_info='ext_repo',
                                                                 tag_info='tag',
                                                                 priority=0,
                                                                 merge_mode='koji')

    def test_handle_edit_external_repo_help(self):
        self.assert_help(
            handle_edit_external_repo,
            """Usage: %s edit-external-repo [options] <name>
(Specify the --help global option for a list of other help options)

Options:
  -h, --help            show this help message and exit
  --url=URL             Change the url
  --name=NAME           Change the name
  -t TAG, --tag=TAG     Edit the repo properties for the tag.
  -p PRIORITY, --priority=PRIORITY
                        Edit the priority of the repo for the tag specified by
                        --tag.
  -m MODE, --mode=MODE  Edit the merge mode of the repo for the tag specified
                        by --tag. Options: %s.
""" % (self.progname, ', '.join(koji.REPO_MERGE_MODES)))


if __name__ == '__main__':
    unittest.main()
