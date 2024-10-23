from __future__ import absolute_import

try:
    from unittest import mock
except ImportError:
    import mock
import os
import time
from six.moves import StringIO

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
        self.original_timezone = os.environ.get('TZ')
        os.environ['TZ'] = 'UTC'
        time.tzset()
        self.repo_id = 123
        self.repo_url = 'http://path_to_ext_repo.com'
        self.repo_name = 'test-repo'
        self.repo_info = {'id': self.repo_id, 'name': self.repo_name, 'url': self.repo_url}
        self.event = {'id': 1000, 'ts': 1000000.11, 'timestr': 'Mon Jan 12 13:46:40 1970'}
        self.test_tag = 'test-tag'
        self.tag_external_repos = [
            {'external_repo_id': 234, 'external_repo_name': 'text-ext-repo-1', 'priority': 12,
             'tag_name': self.test_tag, 'url': self.repo_url},
            {'external_repo_id': 345, 'external_repo_name': 'text-ext-repo-2', 'priority': 11,
             'tag_name': self.test_tag, 'url': self.repo_url}]

    def tearDown(self):
        if self.original_timezone is None:
            del os.environ['TZ']
        else:
            os.environ['TZ'] = self.original_timezone
        time.tzset()
        mock.patch.stopall()

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

    @mock.patch('koji.util.eventFromOpts', return_value={'id': 1000, 'ts': 1000000.11})
    def test_list_external_repos_tag_with_inherit_and_repo_info(self, event_opts):
        args = ['--event', str(self.event['id']), '--tag', self.test_tag, '--inherit',
                '--id', str(self.repo_id)]
        self.assert_system_exit(
            anon_handle_list_external_repos,
            self.options, self.session, args,
            stdout="Querying at event %(id)i (%(timestr)s)\n" % self.event,
            stderr=self.format_error_message("Can't select by repo when using --inherit"),
            exit_code=2,
            activate_session=None)
        self.ensure_connection_mock.assert_called_once_with(self.session, self.options)

    @mock.patch('sys.stdout', new_callable=StringIO)
    @mock.patch('koji.util.eventFromOpts', return_value={'id': 1000, 'ts': 1000000.11})
    def test_list_external_repos_tag_with_inherit_and_repo_info_none(self, event_opts, stdout):
        args = ['--event', str(self.event['id']), '--tag', self.test_tag, '--inherit']
        external_repo_list = [{'arches': None,
                               'external_repo_id': 201,
                               'external_repo_name': 'ext-repo',
                               'merge_mode': 'koji',
                               'priority': 20,
                               'tag_name': 'test-tag'}]
        self.session.getExternalRepoList.return_value = external_repo_list
        anon_handle_list_external_repos(self.options, self.session, args)
        actual = stdout.getvalue()
        expected = """Querying at event %i (%s)
%s             %i  %s       %s
""" % (self.event['id'], self.event['timestr'], external_repo_list[0]['tag_name'],
       external_repo_list[0]['priority'], external_repo_list[0]['merge_mode'],
       external_repo_list[0]['external_repo_name'])
        self.assertMultiLineEqual(actual, expected)
        self.session.getTagExternalRepos.assert_not_called()
        self.session.getExternalRepoList.assert_called_once_with(
            event=self.event['id'], tag_info=self.test_tag)
        self.session.listExternalRepos.assert_not_called()

    @mock.patch('sys.stdout', new_callable=StringIO)
    @mock.patch('koji.util.eventFromOpts', return_value={'id': 1000, 'ts': 1000000.11})
    def test_list_external_repos_tag_without_inherit(self, event_opts, stdout):
        args = ['--event', str(self.event['id']), '--tag', self.test_tag]

        self.session.getTagExternalRepos.return_value = self.tag_external_repos
        anon_handle_list_external_repos(self.options, self.session, args)
        actual = stdout.getvalue()
        expected = """Querying at event %i (%s)
%i  %s           None       %s
%i  %s           None       %s
""" % (self.event['id'], self.event['timestr'], self.tag_external_repos[0]['priority'],
       self.tag_external_repos[0]['external_repo_name'], self.tag_external_repos[0]['url'],
       self.tag_external_repos[1]['priority'], self.tag_external_repos[1]['external_repo_name'],
       self.tag_external_repos[1]['url'])
        self.assertMultiLineEqual(actual, expected)
        self.session.getTagExternalRepos.assert_called_once_with(
            event=self.event['id'], repo_info=None, tag_info=self.test_tag)
        self.session.getExternalRepoList.assert_not_called()
        self.session.listExternalRepos.assert_not_called()

    @mock.patch('sys.stdout', new_callable=StringIO)
    @mock.patch('koji.util.eventFromOpts', return_value={'id': 1000, 'ts': 1000000.11})
    def test_list_external_repos_tag_without_inherit_without_quiet(self, event_opts, stdout):
        self.options.quiet = False
        args = ['--event', str(self.event['id']), '--tag', self.test_tag]
        self.session.getTagExternalRepos.return_value = self.tag_external_repos
        anon_handle_list_external_repos(self.options, self.session, args)
        actual = stdout.getvalue()
        expected = """Querying at event %i (%s)
Pri External repo name        Mode       URL
--- ------------------------- ---------- ----------------------------------------
%i  %s           None       %s
%i  %s           None       %s
""" % (self.event['id'], self.event['timestr'], self.tag_external_repos[0]['priority'],
       self.tag_external_repos[0]['external_repo_name'], self.tag_external_repos[0]['url'],
       self.tag_external_repos[1]['priority'], self.tag_external_repos[1]['external_repo_name'],
       self.tag_external_repos[1]['url'])
        self.assertMultiLineEqual(actual, expected)
        self.session.getTagExternalRepos.assert_called_once_with(
            event=self.event['id'], repo_info=None, tag_info=self.test_tag)
        self.session.getExternalRepoList.assert_not_called()
        self.session.listExternalRepos.assert_not_called()

    @mock.patch('sys.stdout', new_callable=StringIO)
    @mock.patch('koji.util.eventFromOpts', return_value=None)
    def test_list_external_repos_used(self, event_opts, stdout):
        args = ['--used', '--id', str(self.repo_id)]
        self.session.getTagExternalRepos.return_value = self.tag_external_repos
        anon_handle_list_external_repos(self.options, self.session, args)
        actual = stdout.getvalue()
        expected = """%s             %i  None       %s
%s             %i  None       %s
""" % (self.tag_external_repos[0]['tag_name'], self.tag_external_repos[0]['priority'],
       self.tag_external_repos[0]['external_repo_name'], self.tag_external_repos[1]['tag_name'],
       self.tag_external_repos[1]['priority'], self.tag_external_repos[1]['external_repo_name'])
        self.assertMultiLineEqual(actual, expected)
        self.session.getTagExternalRepos.assert_called_once_with(repo_info=self.repo_id)
        self.session.getExternalRepoList.assert_not_called()
        self.session.listExternalRepos.assert_not_called()

    @mock.patch('sys.stdout', new_callable=StringIO)
    @mock.patch('koji.util.eventFromOpts', return_value=None)
    def test_list_external_repos_used_without_quiet(self, event_opts, stdout):
        self.options.quiet = False
        args = ['--used', '--id', str(self.repo_id)]
        self.session.getTagExternalRepos.return_value = self.tag_external_repos
        anon_handle_list_external_repos(self.options, self.session, args)
        actual = stdout.getvalue()
        expected = """Tag                  Pri Mode       External repo name
-------------------- --- ---------- -------------------------
%s             %i  None       %s
%s             %i  None       %s
""" % (self.tag_external_repos[0]['tag_name'], self.tag_external_repos[0]['priority'],
       self.tag_external_repos[0]['external_repo_name'], self.tag_external_repos[1]['tag_name'],
       self.tag_external_repos[1]['priority'], self.tag_external_repos[1]['external_repo_name'])
        self.assertMultiLineEqual(actual, expected)
        self.session.getTagExternalRepos.assert_called_once_with(repo_info=self.repo_id)
        self.session.getExternalRepoList.assert_not_called()
        self.session.listExternalRepos.assert_not_called()

    @mock.patch('sys.stdout', new_callable=StringIO)
    @mock.patch('koji.util.eventFromOpts', return_value={'id': 1000, 'ts': 1000000.11})
    def test_list_external_repos_basic(self, event_opts, stdout):
        args = ['--event', str(self.event['id']), '--name', self.repo_name, '--url', self.repo_url]
        self.session.listExternalRepos.return_value = [self.repo_info]
        anon_handle_list_external_repos(self.options, self.session, args)
        actual = stdout.getvalue()
        expected = """Querying at event %i (%s)
%s                 %s
""" % (self.event['id'], self.event['timestr'], self.repo_name, self.repo_url)
        self.assertMultiLineEqual(actual, expected)
        self.session.listExternalRepos.assert_called_once_with(
            event=self.event['id'], info=self.repo_name, url=self.repo_url)
        self.session.getTagExternalRepos.assert_not_called()
        self.session.getExternalRepoList.assert_not_called()

    @mock.patch('sys.stdout', new_callable=StringIO)
    @mock.patch('koji.util.eventFromOpts', return_value={'id': 1000, 'ts': 1000000.11})
    def test_list_external_repos_basic_without_queit(self, event_opts, stdout):
        self.options.quiet = False
        args = ['--event', str(self.event['id']), '--name', self.repo_name, '--url', self.repo_url]
        self.session.listExternalRepos.return_value = [self.repo_info]
        anon_handle_list_external_repos(self.options, self.session, args)
        actual = stdout.getvalue()
        expected = """Querying at event %i (%s)
External repo name        URL
------------------------- ----------------------------------------
%s                 %s
""" % (self.event['id'], self.event['timestr'], self.repo_name, self.repo_url)
        self.assertMultiLineEqual(actual, expected)
        self.session.listExternalRepos.assert_called_once_with(
            event=self.event['id'], info=self.repo_name, url=self.repo_url)
        self.session.getTagExternalRepos.assert_not_called()
        self.session.getExternalRepoList.assert_not_called()

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
