import sys
import os
import time

import mock
import six

from koji_cli.commands import anon_handle_list_tagged
from . import utils


class TestCliListTagged(utils.CliTestCase):
    # Show long diffs in error output...
    maxDiff = None

    def setUp(self):
        self.original_timezone = os.environ.get('TZ')
        os.environ['TZ'] = 'US/Eastern'
        time.tzset()
        self.error_format = """Usage: %s list-tagged [options] <tag> [<package>]
(Specify the --help global option for a list of other help options)

%s: error: {message}
""" % (self.progname, self.progname)
        self.session = mock.MagicMock()
        self.options = mock.MagicMock(quiet=False)
        self.session.getTag.return_value = {'id': 1}
        self.session.listTaggedRPMS.return_value = [[{'id': 100,
                                                      'build_id': 1,
                                                      'name': 'rpmA',
                                                      'version': '0.0.1',
                                                      'release': '1.el6',
                                                      'arch': 'noarch',
                                                      'sigkey': 'sigkey'},
                                                     {'id': 101,
                                                      'build_id': 1,
                                                      'name': 'rpmA',
                                                      'version': '0.0.1',
                                                      'release': '1.el6',
                                                      'arch': 'x86_64',
                                                      'sigkey': 'sigkey'}
                                                     ], [{'id': 1,
                                                          'name': 'packagename',
                                                          'version': 'version',
                                                          'release': '1.el6',
                                                          'nvr': 'n-v-r',
                                                          'tag_name': 'tag',
                                                          'owner_name': 'owner'}]]
        self.session.listTagged.return_value = [{'id': 1,
                                                 'name': 'packagename',
                                                 'version': 'version',
                                                 'release': '1.el6',
                                                 'nvr': 'n-v-r',
                                                 'tag_name': 'tag',
                                                 'owner_name': 'owner'}]

    def tearDown(self):
        if self.original_timezone is None:
            del os.environ['TZ']
        else:
            os.environ['TZ'] = self.original_timezone
        time.tzset()

    @mock.patch('sys.stdout', new_callable=six.StringIO)
    @mock.patch('koji.util.eventFromOpts', return_value={'id': 1000,
                                                         'ts': 1000000.11})
    @mock.patch('koji_cli.commands.ensure_connection')
    def test_list_tagged_builds(self, ensure_connection_mock,
                                event_from_opts_mock, stdout):
        args = ['tag', 'pkg', '--latest', '--inherit', '--event=1000']

        anon_handle_list_tagged(self.options, self.session, args)
        ensure_connection_mock.assert_called_once_with(self.session)
        self.session.getTag.assert_called_once_with('tag', event=1000)
        self.session.listTagged.assert_called_once_with('tag',
                                                        event=1000,
                                                        inherit=True,
                                                        latest=True,
                                                        package='pkg')
        self.session.listTaggedRPMS.assert_not_called()
        self.assert_console_message(stdout,
                                    'Querying at event 1000 (Mon Jan 12 08:46:40 1970)\n'
                                    'Build                                     Tag                   Built by\n'
                                    '----------------------------------------  --------------------  ----------------\n'
                                    'n-v-r                                     tag                   owner\n')

    @mock.patch('sys.stdout', new_callable=six.StringIO)
    @mock.patch('koji.util.eventFromOpts', return_value=None)
    @mock.patch('koji_cli.commands.ensure_connection')
    def test_list_tagged_builds_paths(self, ensure_connection_mock,
                                      event_from_opts_mock, stdout):
        args = ['tag', 'pkg', '--latest', '--inherit', '--paths']

        anon_handle_list_tagged(self.options, self.session, args)
        self.assert_console_message(stdout,
                                    'Build                                     Tag                   Built by\n'
                                    '----------------------------------------  --------------------  ----------------\n'
                                    '/mnt/koji/packages/packagename/version/1.el6  tag                   owner\n')

    @mock.patch('sys.stdout', new_callable=six.StringIO)
    @mock.patch('koji.util.eventFromOpts', return_value=None)
    @mock.patch('koji_cli.commands.ensure_connection')
    def test_list_tagged_rpms(self, ensure_connection_mock,
                              event_from_opts_mock, stdout):
        args = ['tag', 'pkg', '--latest-n=3', '--rpms', '--sigs',
                '--arch=x86_64', '--arch=noarch']

        anon_handle_list_tagged(self.options, self.session, args)
        ensure_connection_mock.assert_called_once_with(self.session)
        self.session.getTag.assert_called_once_with('tag', event=None)
        self.session.listTaggedRPMS.assert_called_once_with('tag',
                                                            package='pkg',
                                                            inherit=None,
                                                            latest=3,
                                                            rpmsigs=True,
                                                            arch=['x86_64',
                                                                  'noarch'])
        self.session.listTagged.assert_not_called()
        self.assert_console_message(stdout,
                                    'sigkey rpmA-0.0.1-1.el6.noarch\n'
                                    'sigkey rpmA-0.0.1-1.el6.x86_64\n')

    @mock.patch('sys.stdout', new_callable=six.StringIO)
    @mock.patch('koji.util.eventFromOpts', return_value=None)
    @mock.patch('koji_cli.commands.ensure_connection')
    def test_list_tagged_rpms_paths(self, ensure_connection_mock,
                                    event_from_opts_mock, stdout):
        args = ['tag', 'pkg', '--latest-n=3', '--rpms',
                '--arch=x86_64', '--paths']

        anon_handle_list_tagged(self.options, self.session, args)
        self.assert_console_message(stdout,
                                    '/mnt/koji/packages/packagename/version/1.el6/noarch/rpmA-0.0.1-1.el6.noarch.rpm\n'
                                    '/mnt/koji/packages/packagename/version/1.el6/x86_64/rpmA-0.0.1-1.el6.x86_64.rpm\n')

    @mock.patch('sys.stdout', new_callable=six.StringIO)
    @mock.patch('koji.util.eventFromOpts', return_value=None)
    @mock.patch('koji_cli.commands.ensure_connection')
    def test_list_tagged_sigs_paths(self, ensure_connection_mock,
                                    event_from_opts_mock, stdout):
        args = ['tag', 'pkg', '--latest-n=3', '--rpms', '--sigs',
                '--arch=x86_64', '--paths']

        anon_handle_list_tagged(self.options, self.session, args)
        self.assert_console_message(stdout, '')

    @mock.patch('sys.stdout', new_callable=six.StringIO)
    @mock.patch('koji.util.eventFromOpts', return_value=None)
    @mock.patch('koji_cli.commands.ensure_connection')
    def test_list_tagged_type(self, ensure_connection_mock,
                              event_from_opts_mock, stdout):
        args = ['tag', 'pkg', '--latest-n=3', '--type=maven']
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
        ensure_connection_mock.assert_called_once_with(self.session)
        self.session.getTag.assert_called_once_with('tag', event=None)
        self.session.listTagged.assert_called_once_with('tag',
                                                        package='pkg',
                                                        inherit=None,
                                                        latest=3,
                                                        type='maven')
        self.session.listTaggedRPMS.assert_not_called()
        self.assert_console_message(stdout,
                                    'Build                                     Tag                   Group Id              Artifact Id           Built by\n'
                                    '----------------------------------------  --------------------  --------------------  --------------------  ----------------\n'
                                    'n-v-r                                     tag                   group                 artifact              owner\n')

    @mock.patch('sys.stdout', new_callable=six.StringIO)
    @mock.patch('koji.util.eventFromOpts', return_value=None)
    @mock.patch('koji_cli.commands.ensure_connection')
    def test_list_tagged_type_paths(self, ensure_connection_mock,
                              event_from_opts_mock, stdout):
        args = ['tag', 'pkg', '--latest-n=3', '--type=maven', '--paths']
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
        self.assert_console_message(stdout,
                                    'Build                                     Tag                   Group Id              Artifact Id           Built by\n'
                                    '----------------------------------------  --------------------  --------------------  --------------------  ----------------\n'
                                    '/mnt/koji/packages/packagename/version/1.el6/maven  tag                   group                 artifact              owner\n')

    @mock.patch('koji_cli.commands.ensure_connection')
    @mock.patch('koji.util.eventFromOpts', return_value={'id': 1000,
                                                         'ts': 1000000.11})
    def test_list_tagged_args(self, event_from_opts_mock, ensure_connection_mock):
        # Case 1, no argument
        expected = self.format_error_message(
            "A tag name must be specified")
        self.assert_system_exit(
            anon_handle_list_tagged,
            self.options,
            self.session,
            [],
            stderr=expected,
            activate_session=None)

        # Case 2, arguments > 2
        expected = self.format_error_message(
            "Only one package name may be specified")
        self.assert_system_exit(
            anon_handle_list_tagged,
            self.options,
            self.session,
            ['tag', 'pkg1', 'pkg2'],
            stderr=expected,
            activate_session=None)

        # Case 3, no tag found
        expected = self.format_error_message(
            "No such tag: tag")
        self.session.getTag.return_value = None
        self.assert_system_exit(
            anon_handle_list_tagged,
            self.options,
            self.session,
            ['tag', 'pkg1'],
            stderr=expected,
            activate_session=None)

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
