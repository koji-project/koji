from __future__ import absolute_import

import mock
from six.moves import StringIO

import koji
from koji_cli.commands import anon_handle_list_buildroot
from . import utils


class TestListBuilds(utils.CliTestCase):
    def setUp(self):
        self.maxDiff = None
        self.options = mock.MagicMock()
        self.options.debug = False
        self.session = mock.MagicMock()
        self.session.getAPIVersion.return_value = koji.API_VERSION
        self.ensure_connection_mock = mock.patch('koji_cli.commands.ensure_connection').start()
        self.error_format = """Usage: %s list-buildroot [options] <buildroot-id>
(Specify the --help global option for a list of other help options)

%s: error: {message}
""" % (self.progname, self.progname)

    def tearDown(self):
        mock.patch.stopall()

    def test_list_buildroot_without_args(self):
        self.assert_system_exit(
            anon_handle_list_buildroot,
            self.options, self.session, [],
            stderr=self.format_error_message('Incorrect number of arguments'),
            exit_code=2,
            activate_session=None)
        self.ensure_connection_mock.assert_not_called()
        self.session.listRPMs.assert_not_called()

    @mock.patch('sys.stdout', new_callable=StringIO)
    def test_list_buildroot_with_verbose_with_rpms_without_archives(self, stdout):
        expected_output = """Component RPMs:
testpackage-1.1-7.f33.noarch
testpkg-1.171-5.fc33.noarch [update]
tpkg-4.11-1.fc33.x86_64 [update]
"""
        list_rpms = [{'arch': 'noarch', 'is_update': True, 'nvr': 'testpkg-1.171-5.fc33'},
                     {'arch': 'noarch', 'is_update': False, 'nvr': 'testpackage-1.1-7.f33'},
                     {'arch': 'x86_64', 'is_update': True, 'nvr': 'tpkg-4.11-1.fc33'}]
        self.session.listRPMs.return_value = list_rpms
        self.session.listArchives.return_value = []
        rv = anon_handle_list_buildroot(self.options, self.session, ['--verbose', '1'])
        self.assertEqual(rv, None)
        self.assert_console_message(stdout, expected_output)
        self.ensure_connection_mock.assert_called_once_with(self.session, self.options)
        self.session.listRPMs.assert_called_once_with(componentBuildrootID=1)
        self.session.listArchives.assert_called_once_with(componentBuildrootID=1)

    @mock.patch('sys.stdout', new_callable=StringIO)
    def test_list_buildroot_with_verbose_without_rpms_with_archives(self, stdout):
        expected_output = """Component Archives:
archivename1.tar.gz
archivename2.zip
"""
        list_archives = [{'filename': 'archivename2.zip'},
                         {'filename': 'archivename1.tar.gz'}]
        self.session.listRPMs.return_value = []
        self.session.listArchives.return_value = list_archives
        rv = anon_handle_list_buildroot(self.options, self.session, ['--verbose', '1'])
        self.assertEqual(rv, None)
        self.assert_console_message(stdout, expected_output)
        self.ensure_connection_mock.assert_called_once_with(self.session, self.options)
        self.session.listRPMs.assert_called_once_with(componentBuildrootID=1)
        self.session.listArchives.assert_called_once_with(componentBuildrootID=1)

    @mock.patch('sys.stdout', new_callable=StringIO)
    def test_list_buildroot_with_verbose_with_rpms_with_archives(self, stdout):
        expected_output = """Component RPMs:
testpackage-1.1-7.f33.noarch
testpkg-1.171-5.fc33.noarch [update]
tpkg-4.11-1.fc33.x86_64 [update]

Component Archives:
archivename1.tar.gz
archivename2.zip
"""
        list_rpms = [{'arch': 'noarch', 'is_update': True, 'nvr': 'testpkg-1.171-5.fc33'},
                     {'arch': 'noarch', 'is_update': False, 'nvr': 'testpackage-1.1-7.f33'},
                     {'arch': 'x86_64', 'is_update': True, 'nvr': 'tpkg-4.11-1.fc33'}]
        list_archives = [{'filename': 'archivename2.zip'},
                         {'filename': 'archivename1.tar.gz'}]
        self.session.listRPMs.return_value = list_rpms
        self.session.listArchives.return_value = list_archives
        rv = anon_handle_list_buildroot(self.options, self.session, ['--verbose', '1'])
        self.assertEqual(rv, None)
        self.assert_console_message(stdout, expected_output)
        self.ensure_connection_mock.assert_called_once_with(self.session, self.options)
        self.session.listRPMs.assert_called_once_with(componentBuildrootID=1)
        self.session.listArchives.assert_called_once_with(componentBuildrootID=1)

    @mock.patch('sys.stdout', new_callable=StringIO)
    def test_list_buildroot_with_built_with_rpms_without_archives(self, stdout):
        expected_output = """Built RPMs:
testpackage-1.1-7.f33.x86_64
testpkg-1.171-5.fc33.noarch
tpkg-4.11-1.fc33.noarch
"""
        list_rpms = [{'arch': 'noarch', 'nvr': 'testpkg-1.171-5.fc33'},
                     {'arch': 'x86_64', 'nvr': 'testpackage-1.1-7.f33'},
                     {'arch': 'noarch', 'nvr': 'tpkg-4.11-1.fc33'}]
        self.session.listRPMs.return_value = list_rpms
        self.session.listArchives.return_value = []
        rv = anon_handle_list_buildroot(self.options, self.session, ['--built', '2'])
        self.assertEqual(rv, None)
        self.assert_console_message(stdout, expected_output)
        self.ensure_connection_mock.assert_called_once_with(self.session, self.options)
        self.session.listRPMs.assert_called_once_with(buildrootID=2)
        self.session.listArchives.assert_called_once_with(buildrootID=2)

    @mock.patch('sys.stdout', new_callable=StringIO)
    def test_list_buildroot_with_built_without_rpms_with_archives(self, stdout):
        expected_output = """Built Archives:
archivename1.tar.gz
archivename2.zip
"""
        list_archives = [{'filename': 'archivename2.zip'},
                         {'filename': 'archivename1.tar.gz'}]
        self.session.listRPMs.return_value = []
        self.session.listArchives.return_value = list_archives
        rv = anon_handle_list_buildroot(self.options, self.session, ['--built', '2'])
        self.assertEqual(rv, None)
        self.assert_console_message(stdout, expected_output)
        self.ensure_connection_mock.assert_called_once_with(self.session, self.options)
        self.session.listRPMs.assert_called_once_with(buildrootID=2)
        self.session.listArchives.assert_called_once_with(buildrootID=2)

    def test_list_buildroot_help(self):
        self.assert_help(
            anon_handle_list_buildroot,
            """Usage: %s list-buildroot [options] <buildroot-id>
(Specify the --help global option for a list of other help options)

Options:
  -h, --help     show this help message and exit
  --built        Show the built rpms and archives
  -v, --verbose  Show more information
""" % self.progname)
        self.ensure_connection_mock.assert_not_called()
