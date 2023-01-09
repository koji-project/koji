from __future__ import absolute_import

import mock

from koji_cli.commands import anon_handle_list_external_repos
from . import utils


class TestListExternalRepo(utils.CliTestCase):

    def setUp(self):
        self.maxDiff = None
        self.options = mock.MagicMock()
        self.session = mock.MagicMock()
        self.ensure_connection_mock = mock.patch('koji_cli.commands.ensure_connection').start()
        self.error_format = """Usage: %s list-external-repos [options]
(Specify the --help global option for a list of other help options)

%s: error: {message}
""" % (self.progname, self.progname)

    def test_list_external_repos_with_args(self):
        arguments = ['arg']
        self.assert_system_exit(
            anon_handle_list_external_repos,
            self.options, self.session, arguments,
            stdout='',
            stderr=self.format_error_message('This command takes no arguments'),
            exit_code=2,
            activate_session=None)
        self.ensure_connection_mock.assert_not_called()

    def test_list_external_repos_help(self):
        self.assert_help(
            anon_handle_list_external_repos,
            """Usage: %s list-external-repos [options]
(Specify the --help global option for a list of other help options)

Options:
  -h, --help      show this help message and exit
  --url=URL       Select by url
  --name=NAME     Select by name
  --id=ID         Select by id
  --tag=TAG       Select by tag
  --used          List which tags use the repo(s)
  --inherit       Follow tag inheritance when selecting by tag
  --event=EVENT#  Query at event
  --ts=TIMESTAMP  Query at last event before timestamp
  --repo=REPO#    Query at event corresponding to (nonexternal) repo
  --quiet         Do not display the column headers
""" % self.progname)
        self.ensure_connection_mock.assert_not_called()
