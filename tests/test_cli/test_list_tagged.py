import os
import time

import mock
import six

from koji_cli.commands import anon_handle_list_tagged
from . import utils


class TestCliListTagged(utils.CliTestCase):

    def setUp(self):
        self.maxDiff = None
        self.original_timezone = os.environ.get('TZ')
        os.environ['TZ'] = 'US/Eastern'
        time.tzset()
        self.error_format = """Usage: %s list-tagged [options] <tag> [<package>]
(Specify the --help global option for a list of other help options)

%s: error: {message}
""" % (self.progname, self.progname)
        self.session = mock.MagicMock()
        self.options = mock.MagicMock(quiet=False)
        self.tag = 'tag'
        self.pkg = 'pkg'
        self.event_id = 1000
        self.type = 'maven'
        self.session.getTag.return_value = {'id': 1}
        self.session.listTaggedRPMS.return_value = [[{'id': 100,
                                                      'build_id': 1,
                                                      'name': 'rpmA',
                                                      'version': '0.0.1',
                                                      'release': '1.el6',
                                                      'arch': 'noarch',
                                                      'sigkey': 'sigkey',
                                                      'extra': 'extra-value'},
                                                     {'id': 101,
                                                      'build_id': 1,
                                                      'name': 'rpmA',
                                                      'version': '0.0.1',
                                                      'release': '1.el6',
                                                      'arch': 'x86_64',
                                                      'sigkey': 'sigkey',
                                                      'extra': None}
                                                     ], [{'id': 1,
                                                          'name': 'packagename',
                                                          'version': 'version',
                                                          'release': '1.el6',
                                                          'nvr': 'n-v-r',
                                                          'tag_name': 'tag',
                                                          'owner_name': 'owner',
                                                          'extra': 'extra-value-2'}]]
        self.session.listTagged.return_value = [{'id': 1,
                                                 'name': 'packagename',
                                                 'version': 'version',
                                                 'release': '1.el6',
                                                 'nvr': 'n-v-r',
                                                 'tag_name': 'tag',
                                                 'owner_name': 'owner',
                                                 'extra': 'extra-value-2'}]
        self.ensure_connection_mock = mock.patch('koji_cli.commands.ensure_connection').start()

    def tearDown(self):
        if self.original_timezone is None:
            del os.environ['TZ']
        else:
            os.environ['TZ'] = self.original_timezone
        time.tzset()

    @mock.patch('sys.stdout', new_callable=six.StringIO)
    @mock.patch('koji.util.eventFromOpts', return_value={'id': 1000,
                                                         'ts': 1000000.11})
    def test_list_tagged_builds(self, event_from_opts_mock, stdout):
        expected = """Querying at event 1000 (Mon Jan 12 08:46:40 1970)
Build                                     Tag                   Built by
----------------------------------------  --------------------  ----------------
n-v-r                                     tag                   owner
"""
        args = [self.tag, self.pkg, '--latest', '--inherit', '--event', str(self.event_id)]

        anon_handle_list_tagged(self.options, self.session, args)
        self.ensure_connection_mock.assert_called_once_with(self.session, self.options)
        self.session.getTag.assert_called_once_with(self.tag, event=self.event_id)
        self.session.listTagged.assert_called_once_with(
            self.tag, event=self.event_id, inherit=True, latest=True, package=self.pkg)
        self.session.listTaggedRPMS.assert_not_called()
        self.assert_console_message(stdout, expected)

    @mock.patch('sys.stdout', new_callable=six.StringIO)
    @mock.patch('koji.util.eventFromOpts', return_value=None)
    def test_list_tagged_builds_paths(self, event_from_opts_mock, stdout):
        expected = """Build                                     Tag                   Built by
----------------------------------------  --------------------  ----------------
/mnt/koji/packages/packagename/version/1.el6  tag                   owner
"""
        args = [self.tag, self.pkg, '--latest', '--inherit', '--paths']

        anon_handle_list_tagged(self.options, self.session, args)
        self.assert_console_message(stdout, expected)
        self.ensure_connection_mock.assert_called_once_with(self.session, self.options)
        self.session.getTag.assert_called_once_with(self.tag, event=None)
        self.session.listTagged.assert_called_once_with(
            self.tag, inherit=True, latest=True, package=self.pkg)
        self.session.listTaggedRPMS.assert_not_called()

    @mock.patch('sys.stdout', new_callable=six.StringIO)
    @mock.patch('koji.util.eventFromOpts', return_value=None)
    def test_list_tagged_rpms(self, event_from_opts_mock, stdout):
        expected = """sigkey rpmA-0.0.1-1.el6.noarch
sigkey rpmA-0.0.1-1.el6.x86_64
"""
        args = [self.tag, self.pkg, '--latest-n=3', '--rpms', '--sigs',
                '--arch=x86_64', '--arch=noarch']

        anon_handle_list_tagged(self.options, self.session, args)
        self.ensure_connection_mock.assert_called_once_with(self.session, self.options)
        self.session.getTag.assert_called_once_with(self.tag, event=None)
        self.session.listTaggedRPMS.assert_called_once_with(
            self.tag, package=self.pkg, inherit=None, latest=3, rpmsigs=True,
            arch=['x86_64', 'noarch'])
        self.session.listTagged.assert_not_called()
        self.assert_console_message(stdout, expected)

    @mock.patch('os.path.isdir', return_value=True)
    @mock.patch('os.path.exists', return_value=True)
    @mock.patch('sys.stdout', new_callable=six.StringIO)
    @mock.patch('koji.util.eventFromOpts', return_value=None)
    def test_list_tagged_rpms_paths(self, event_from_opts_mock, stdout, os_path_exists, isdir):
        expected = """/mnt/koji/packages/packagename/version/1.el6/noarch/rpmA-0.0.1-1.el6.noarch.rpm
/mnt/koji/packages/packagename/version/1.el6/x86_64/rpmA-0.0.1-1.el6.x86_64.rpm
"""
        args = [self.tag, self.pkg, '--latest-n=3', '--rpms', '--arch=x86_64', '--paths']

        anon_handle_list_tagged(self.options, self.session, args)
        self.assert_console_message(stdout, expected)
        self.ensure_connection_mock.assert_called_once_with(self.session, self.options)
        self.session.getTag.assert_called_once_with(self.tag, event=None)
        self.session.listTaggedRPMS.assert_called_once_with(
            self.tag, package=self.pkg, inherit=None, latest=3, arch=['x86_64'])
        self.session.listTagged.assert_not_called()

    @mock.patch('os.path.exists')
    @mock.patch('sys.stdout', new_callable=six.StringIO)
    @mock.patch('koji.util.eventFromOpts', return_value=None)
    def test_list_tagged_sigs_paths(self, event_from_opts_mock, stdout, os_path_exists):
        expected = ""
        args = [self.tag, self.pkg, '--latest-n=3', '--rpms', '--sigs',
                '--arch=x86_64', '--paths']

        os_path_exists.side_effect = [True, False, False]
        anon_handle_list_tagged(self.options, self.session, args)
        self.assert_console_message(stdout, expected)
        self.ensure_connection_mock.assert_called_once_with(self.session, self.options)
        self.session.getTag.assert_called_once_with(self.tag, event=None)
        self.session.listTaggedRPMS.assert_called_once_with(
            self.tag, package=self.pkg, inherit=None, latest=3, rpmsigs=True, arch=['x86_64'])
        self.session.listTagged.assert_not_called()

    @mock.patch('sys.stdout', new_callable=six.StringIO)
    @mock.patch('koji.util.eventFromOpts', return_value=None)
    def test_list_tagged_type(self, event_from_opts_mock, stdout):
        expected = """Build                                     Tag                   Group Id              Artifact Id           Built by
----------------------------------------  --------------------  --------------------  --------------------  ----------------
n-v-r                                     tag                   group                 artifact              owner
"""
        args = [self.tag, self.pkg, '--latest-n=3', '--type', self.type]
        self.session.listTagged.return_value = [{'id': 1,
                                                 'name': 'packagename',
                                                 'version': 'version',
                                                 'release': '1.el6',
                                                 'nvr': 'n-v-r',
                                                 'tag_name': 'tag',
                                                 'owner_name': 'owner',
                                                 'maven_group_id': 'group',
                                                 'maven_artifact_id': 'artifact'}]

        anon_handle_list_tagged(self.options, self.session, args)
        self.ensure_connection_mock.assert_called_once_with(self.session, self.options)
        self.session.getTag.assert_called_once_with(self.tag, event=None)
        self.session.listTagged.assert_called_once_with(
            self.tag, package=self.pkg, inherit=None, latest=3, type=self.type)
        self.session.listTaggedRPMS.assert_not_called()
        self.assert_console_message(stdout, expected)

    @mock.patch('sys.stdout', new_callable=six.StringIO)
    @mock.patch('koji.util.eventFromOpts', return_value=None)
    def test_list_tagged_type_paths(self, event_from_opts_mock, stdout):
        expected = """Build                                     Tag                   Group Id              Artifact Id           Built by
----------------------------------------  --------------------  --------------------  --------------------  ----------------
/mnt/koji/packages/packagename/version/1.el6/maven  tag                   group                 artifact              owner
"""
        args = [self.tag, self.pkg, '--latest-n=3', '--type', self.type, '--paths']
        self.session.listTagged.return_value = [{'id': 1,
                                                 'name': 'packagename',
                                                 'version': 'version',
                                                 'release': '1.el6',
                                                 'nvr': 'n-v-r',
                                                 'tag_name': 'tag',
                                                 'owner_name': 'owner',
                                                 'maven_group_id': 'group',
                                                 'maven_artifact_id': 'artifact'}]

        anon_handle_list_tagged(self.options, self.session, args)
        self.assert_console_message(stdout, expected)
        self.ensure_connection_mock.assert_called_once_with(self.session, self.options)
        self.session.getTag.assert_called_once_with(self.tag, event=None)
        self.session.listTaggedRPMS.assert_not_called()
        self.session.listTagged.assert_called_once_with(
            self.tag, inherit=None, latest=3, package=self.pkg, type=self.type)

    def test_list_tagged_without_args(self):
        self.assert_system_exit(
            anon_handle_list_tagged,
            self.options, self.session, [],
            stderr=self.format_error_message("A tag name must be specified"),
            activate_session=None,
            exit_code=2)
        self.ensure_connection_mock.assert_not_called()
        self.session.getTag.assert_not_called()
        self.session.listTaggedRPMS.assert_not_called()
        self.session.listTagged.assert_not_called()

    def test_list_tagged_more_args(self):
        self.assert_system_exit(
            anon_handle_list_tagged,
            self.options, self.session, ['tag', 'pkg1', 'pkg2'],
            stderr=self.format_error_message("Only one package name may be specified"),
            activate_session=None,
            exit_code=2)
        self.ensure_connection_mock.assert_not_called()
        self.session.getTag.assert_not_called()
        self.session.listTaggedRPMS.assert_not_called()
        self.session.listTagged.assert_not_called()

    def test_list_tagged_tag_not_found(self):
        self.session.getTag.return_value = None
        self.assert_system_exit(
            anon_handle_list_tagged,
            self.options, self.session, ['tag', 'pkg1'],
            stderr=self.format_error_message("No such tag: tag"),
            activate_session=None,
            exit_code=2)
        self.ensure_connection_mock.assert_called_once_with(self.session, self.options)
        self.session.getTag.assert_called_once_with(self.tag, event=None)
        self.session.listTaggedRPMS.assert_not_called()
        self.session.listTagged.assert_not_called()

    def test_handle_list_tagged_help(self):
        self.assert_help(
            anon_handle_list_tagged,
            """Usage: %s list-tagged [options] <tag> [<package>]
(Specify the --help global option for a list of other help options)

Options:
  -h, --help      show this help message and exit
  --arch=ARCH     List rpms for this arch
  --rpms          Show rpms instead of builds
  --inherit       Follow inheritance
  --latest        Only show the latest builds/rpms
  --latest-n=N    Only show the latest N builds/rpms
  --quiet         Do not print the header information
  --paths         Show the file paths
  --sigs          Show signatures
  --type=TYPE     Show builds of the given type only. Currently supported
                  types: maven, win, image
  --event=EVENT#  query at event
  --ts=TIMESTAMP  query at last event before timestamp
  --repo=REPO#    query at event for a repo
""" % self.progname)
