from __future__ import absolute_import

try:
    from unittest import mock
except ImportError:
    import mock
from six.moves import StringIO

import koji
from koji_cli.commands import anon_handle_taginfo
from . import utils


class TestTaginfo(utils.CliTestCase):
    def setUp(self):
        self.maxDiff = None
        self.options = mock.MagicMock()
        self.options.debug = False
        self.session = mock.MagicMock()
        self.session.getAPIVersion.return_value = koji.API_VERSION
        self.error_format = """Usage: %s taginfo [options] <tag> [<tag> ...]
(Specify the --help global option for a list of other help options)

%s: error: {message}
""" % (self.progname, self.progname)

    def test_taginfo_without_option(self):
        self.assert_system_exit(
            anon_handle_taginfo,
            self.options, self.session, [],
            stdout='',
            stderr=self.format_error_message("Please specify a tag"),
            exit_code=2,
            activate_session=None)

        self.session.getBuildConfig.assert_not_called()
        self.session.getTagGroups.assert_not_called()
        self.session.mavenEnabled.assert_not_called()
        self.session.getBuildTargets.assert_not_called()
        self.session.getRepo.assert_not_called()
        self.session.getTagExternalRepos.assert_not_called()
        self.session.getInheritanceData.assert_not_called()

    def test_taginfo_non_exist_tag(self):
        tag = 'test-tag'
        self.session.getBuildConfig.return_value = None
        self.assert_system_exit(
            anon_handle_taginfo,
            self.options, self.session, [tag],
            stdout='',
            stderr=self.format_error_message("No such tag: %s" % tag),
            exit_code=2,
            activate_session=None)

        self.session.getBuildConfig.assert_called_once_with('test-tag')
        self.session.getTagGroups.assert_not_called()
        self.session.mavenEnabled.assert_not_called()
        self.session.getBuildTargets.assert_not_called()
        self.session.getRepo.assert_not_called()
        self.session.getTagExternalRepos.assert_not_called()
        self.session.getInheritanceData.assert_not_called()

    @mock.patch('sys.stdout', new_callable=StringIO)
    def test_taginfo(self, stdout):
        self.session.getBuildConfig.return_value = {
            'arches': 'x86_64',
            'config_inheritance': {'arches': None, 'extra': ['value']},
            'extra': {'tag2distrepo.keys': '9867c58f'},
            'id': 1111,
            'locked': True,
            'maven_include_all': False,
            'maven_support': True,
            'name': 'test-tag',
            'perm': 1,
            'perm_id': 'test-perm'}
        self.session.getTagGroups.return_value = [{'name': 'group-1'}, {'name': 'group-2'}]
        self.session.mavenEnabled.return_value = True
        self.session.getBuildTargets.side_effect = [[
            {'build_tag': 123,
             'build_tag_name': 'test-build-tag-1',
             'id': 111,
             'name': 'test-tag-1'}],
            [{'build_tag': 1111,
              'build_tag_name': 'test-tag',
              'id': 112,
              'name': 'test-tag-2'}]]
        self.session.getRepo.side_effect = [None, None, ]
        self.session.getTagExternalRepos.return_value = [{'external_repo_id': 11,
                                                          'external_repo_name': 'ext-repo',
                                                          'tag_id': 1111,
                                                          'tag_name': 'test-tag',
                                                          'priority': 5,
                                                          'merge_mode': 'simple',
                                                          'arches': 'x86_64 i686',
                                                          'url': 'test/url'}]
        self.session.getInheritanceData.return_value = [{'child_id': 1,
                                                         'intransitive': False,
                                                         'maxdepth': 111111,
                                                         'name': 'test-tag',
                                                         'noconfig': False,
                                                         'parent_id': 2,
                                                         'pkg_filter': 'pkg-filter',
                                                         'priority': 5,
                                                         'tag_id': 1111}]
        expected_stdout = """Tag: test-tag [1111]
Arches: x86_64
Groups: group-1, group-2
LOCKED
Required permission: 'test-perm'
Maven support?: yes
Include all Maven archives?: no
Tag options:
  tag2distrepo.keys : '9867c58f'
Targets that build into this tag:
  test-tag-1 (test-build-tag-1, no active repo)
This tag is a buildroot for one or more targets
Current repo: no active repo
Targets that build from this tag:
  test-tag-2
External repos:
    5 ext-repo (test/url, merge mode: simple), arches: x86_64 i686
Inheritance:
  5    MF.. test-tag [2]
    maxdepth: 111111
    package filter: pkg-filter
"""
        anon_handle_taginfo(self.options, self.session, ['test-tag'])
        self.assert_console_message(stdout, expected_stdout)
        self.session.getBuildConfig.assert_called_once_with('test-tag')
        self.session.getTagGroups.assert_called_once_with(1111)
        self.session.mavenEnabled.assert_called_once_with()
        self.session.getBuildTargets.assert_has_calls([mock.call(destTagID=1111)],
                                                      [mock.call(buildTagID=1111)])
        self.session.getRepo.assert_has_calls([mock.call(123)], [mock.call(1111)])
        self.session.getTagExternalRepos.assert_called_once_with(tag_info=1111)
        self.session.getInheritanceData.assert_called_once_with(1111)

    def test_taginfo_help(self):
        self.assert_help(
            anon_handle_taginfo,
            """Usage: %s taginfo [options] <tag> [<tag> ...]
(Specify the --help global option for a list of other help options)

Options:
  -h, --help      show this help message and exit
  --event=EVENT#  query at event
  --ts=TIMESTAMP  query at last event before timestamp
  --repo=REPO#    query at event for a repo
""" % self.progname)
