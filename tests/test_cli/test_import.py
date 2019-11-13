from __future__ import absolute_import
import mock
import os
import six
try:
    import unittest2 as unittest
except ImportError:
    import unittest

import koji
from koji_cli.commands import handle_import
from . import utils

def md5_to_bytes(s):
    if six.PY2:
        return bytearray.fromhex(unicode(s))
    else:
        return bytearray.fromhex(s)

class TestImport(utils.CliTestCase):

    # Show long diffs in error output...
    maxDiff = None

    def setUp(self):
        self.huburl = "https://%s.local/%shub" % (self.progname, self.progname)
        self.md5 = '00112233445566778899aabbccddeeff'
        self.fake_srv_dir = '/path/to/server/import'

        #
        # RPM header example (bash-4.4.12-5.fc26.x86_64.rpm):
        # {
        #   'sourcepackage': None,
        #   'name': 'bash',
        #   'sigmd5': 'J\x15\xca\x94\xb1\xacY\xd5\xef\x9f\xc6\xd5\n\xd7?>',
        #   'epoch': None,
        #   'version': '4.4.12',
        #   'release': '5.fc26',
        #   'sourcerpm': 'bash-4.4.12-5.fc26.src.rpm',
        #   'arch': 'x86_64'
        # }
        #
        # SRPM header example (bash-4.4.12-5.fc26.src.rpm):
        # {
        #   'sourcepackage': 1,
        #   'name': 'bash',
        #   'sigmd5': '\x8a\x17\x05\xe8k\xef\x15\x16V[\x02\x9cs\xab\x7f\xdd',
        #   'epoch': None,
        #   'version': '4.4.12',
        #   'release': '5.fc26',
        #   'sourcerpm': None,
        #   'arch': 'x86_64'
        # }
        self.srpm_header = {
            'sourcepackage': 1,
            'name': 'bash',
            'sigmd5': md5_to_bytes(self.md5),
            'epoch': None,
            'version': '4.4.12',
            'release': '5.fc26',
            'sourcerpm': None,
            'arch': 'x86_64'
        }

        self.rpm_header = {
            'sourcepackage': None,
            'name': 'bash',
            'sigmd5': md5_to_bytes(self.md5),
            'epoch': None,
            'version': '4.4.12',
            'release': '5.fc26',
            'sourcerpm': 'bash-4.4.12-5.fc26.src.rpm',
            'arch': 'x86_64'
        }

        # koji.BUILD_STATES
        self.bstate = {
            'BUILDING': 0,
            'COMPLETE': 1,
            'DELETED': 2,
            'FAILED': 3,
            'CANCELED': 4,
        }

        self.error_format = """Usage: %s import [options] <package> [<package> ...]
(Specify the --help global option for a list of other help options)

%s: error: {message}
""" % (self.progname, self.progname)

    def __do_import_test(self, options, session, arguments, **kwargs):
        expected = kwargs.get('expected', None)
        rpm_header = kwargs.get('rpm_header', {})
        fake_srv_path = kwargs.get('srv_path', '/path/to/server/import')
        upload_rpm_mock = kwargs.get('upload_rpm_mock', session.uploadWrapper)

        with mock.patch('koji.get_header_fields') as get_header_fields_mock:
            with mock.patch('koji_cli.commands.unique_path') as unique_path_mock:
                with mock.patch('koji_cli.commands.activate_session') as activate_session_mock:
                    with mock.patch('sys.stdout', new_callable=six.StringIO) as stdout:
                        with upload_rpm_mock:
                            get_header_fields_mock.return_value = rpm_header
                            unique_path_mock.return_value = fake_srv_path
                            handle_import(options, session, arguments)

        # check output message
        self.assert_console_message(stdout, expected)

        # check mock calls
        activate_session_mock.assert_called_with(session, options)
        get_header_fields_mock.assert_called_with(
            arguments[0],
            ('name', 'version', 'release', 'epoch',
             'arch', 'sigmd5', 'sourcepackage', 'sourcerpm')
        )

        session.getRPM.assert_called_with(
            dict((k, rpm_header.get(k, ''))
                 for k in ['release', 'version', 'arch', 'name'])
        )

        unique_path_mock.assert_called_with('cli-import')
        upload_rpm_mock.assert_called_with(arguments[0], self.fake_srv_dir)
        session.importRPM.assert_called_with(
            self.fake_srv_dir, os.path.basename(arguments[0]))

        # reset for next test
        activate_session_mock.reset_mock()
        get_header_fields_mock.reset_mock()
        unique_path_mock.reset_mock()
        upload_rpm_mock.reset_mock()
        session.getRPM.reset_mock()
        session.importRPM.reset_mock()

    def __skip_import_test(self, options, session, arguments, **kwargs):
        expected = kwargs.get('expected', None)
        rpm_header = kwargs.get('rpm_header', {})

        with mock.patch('koji.get_header_fields') as get_header_fields_mock:
            with mock.patch('koji_cli.commands.activate_session') as activate_session_mock:
                with mock.patch('sys.stdout', new_callable=six.StringIO) as stdout:
                    get_header_fields_mock.return_value = rpm_header
                    handle_import(options, session, arguments)

        # check output message
        self.assert_console_message(stdout, expected)

        # check mock calls
        activate_session_mock.assert_called_with(session, options)
        get_header_fields_mock.assert_called_with(
            arguments[0],
            ('name', 'version', 'release', 'epoch',
             'arch', 'sigmd5', 'sourcepackage', 'sourcerpm')
        )

        session.getRPM.assert_called_with(
            dict((k, rpm_header.get(k, ''))
                 for k in ['release', 'version', 'arch', 'name'])
        )

        session.uploadWrapper.assert_not_called()
        session.importRPM.assert_not_called()

    def test_handle_import_src_rpm_import_with_no_exist_build(self):
        """Test handle_import source RPM import.
           No build is on the server case,
           this tests are focusing on do_import() function coverage.
        """
        arguments = ['/path/to/bash-4.4.12-5.fc26.src.rpm', '--src-epoch', 'None']
        options = mock.MagicMock()
        session = mock.MagicMock()

        # No exist build test case
        # import general case
        session.getBuild.return_value = None
        session.getRPM.return_value = None
        expected = "uploading %s... done\n" % arguments[0]
        expected += "importing %s... done\n" % arguments[0]
        self.__do_import_test(
            options, session, arguments,
            rpm_header=self.srpm_header, expected=expected)

        # import error case
        session.importRPM.side_effect = koji.GenericError('fake-import-error')
        expected = "uploading %s... done\n" % arguments[0]
        expected += "importing %s... \n" % arguments[0]
        expected += "Error importing: fake-import-error\n"
        self.__do_import_test(
            options, session, arguments,
            rpm_header=self.srpm_header, expected=expected)

        # import with --link (hardlink) option
        session.importRPM.side_effect = None
        expected = "importing %s... done\n" % arguments[0]
        self.__do_import_test(
            options, session, arguments + ['--link'],
            upload_rpm_mock=mock.patch('koji_cli.commands.linked_upload').start(),
            rpm_header=self.srpm_header, expected=expected)
        session.uploadWrapper.assert_not_called()

    def test_handle_import_src_rpm_import_with_exist_build(self):
        """Test handle_import source RPM import with exist build case."""
        arguments = ['/path/to/bash-4.4.12-5.fc26.src.rpm']
        options = mock.MagicMock()
        session = mock.MagicMock()
        false_md5 = 'ffeeddccbbaa99887766554433221100'

        #
        # getBuild return example (bash-4.4.12-5.fc26.src.rpm)
        # {
        #   'package_name': 'bash',
        #   'extra': None,
        #   'creation_time': '2017-11-08 18:56:31.359440',
        #   'completion_time': '2017-11-08 18:56:31.359440',
        #   'package_id': 1,
        #   'id': 1,
        #   'build_id': 1,
        #   'state': 1,
        #   'source': None,
        #   'epoch': None,
        #   'version': '4.4.12',
        #   'completion_ts': 1510167391.35944,
        #   'owner_id': 1,
        #   'owner_name': 'kojiadmin',
        #   'nvr': 'bash-4.4.12-5.fc26',
        #   'start_time': '2017-11-08 18:56:31.359440',
        #   'creation_event_id': 81,
        #   'start_ts': 1510167391.35944,
        #   'volume_id': 0,
        #   'creation_ts': 1510167391.35944,
        #   'name': 'bash',
        #   'task_id': None,
        #   'volume_name': 'DEFAULT',
        #   'release': '5.fc26'
        # }
        #

        #
        # getRPM return example:
        # {
        #   'build_id': 1,
        #   'name': 'bash',
        #   'extra': None,
        #   'external_repo_id': 0,
        #   'buildtime': 1496119944,
        #   'id': 1,
        #   'epoch': None,
        #   'version': '4.4.12',
        #   'buildroot_id': None,
        #   'metadata_only': False,
        #   'release': '5.fc26',
        #   'arch': 'src',
        #   'payloadhash': '8a1705e86bef1516565b029c73ab7fdd',
        #   'external_repo_name': 'INTERNAL',
        #   'size': 9462614
        # }
        #

        # Case 1: build exists and status is 'COMPLETE', md5 matched
        # reseult: import skipped
        session.getBuild.return_value = {'state': self.bstate['COMPLETE']}
        session.getRPM.return_value = {
            'external_repo_id': 0,
            'external_repo_name': 'INTERNAL',
            'payloadhash': self.md5
        }
        expected = "RPM already imported: %s\n" % arguments[0]
        expected += "Skipping import\n"
        self.__skip_import_test(
            options, session, arguments,
            rpm_header=self.srpm_header,
            expected=expected)

        # Case 2: build exists and status is 'COMPLETE', md5 mismatched
        # reseult: import skipped
        session.getRPM.return_value['payloadhash'] = false_md5
        expected = "WARNING: md5sum mismatch for %s\n" % arguments[0]
        expected += "  A different rpm with the same name has already been imported\n"
        expected += "  Existing sigmd5 is %r, your import has %r\n" % (false_md5, self.md5)
        expected += "Skipping import\n"
        self.__skip_import_test(
            options, session, arguments,
            rpm_header=self.srpm_header,
            expected=expected)

        # Case 3: build exists and status is 'COMPLETE', has external_repo_id
        # reseult: import will be performed
        session.getRPM.return_value['external_repo_id'] = 1
        expected = "uploading %s... done\n" % arguments[0]
        expected += "importing %s... done\n" % arguments[0]
        self.__do_import_test(
            options, session, arguments,
            rpm_header=self.srpm_header,
            expected=expected)

        nvr = '%(name)s-%(version)s-%(release)s' % self.srpm_header

        # Case 4: build exists and the status is FAILED or CANCELED
        #         without --create-build option.
        # result: import skipped
        session.getBuild.return_value = {
            'name': 'bash',
            'version': '4.4.12',
            'release': '5.fc26',
            'state': self.bstate['FAILED']}
        session.getRPM.return_value = {
            'external_repo_name': 'INTERNAL',
            'payloadhash': self.md5
        }
        expected = "Build %s state is %s. Skipping import\n" % (nvr, 'FAILED')
        with mock.patch('koji.get_header_fields') as get_header_fields_mock:
            with mock.patch('koji_cli.commands.activate_session') as activate_session_mock:
                with mock.patch('sys.stdout', new_callable=six.StringIO) as stdout:
                    get_header_fields_mock.return_value = self.srpm_header
                    handle_import(options, session, arguments)
        activate_session_mock.assert_called_with(session, options)
        self.assert_console_message(stdout, expected)

        # Case 5: build exists and the status is FAILED or CANCELED
        #         with --create-build option.
        # result: empty build will be created,
        #         import will be performed.
        expected = "Creating empty build: %s\n" % nvr
        expected += "uploading %s... done\n" % arguments[0]
        expected += "importing %s... done\n" % arguments[0]

        session.getBuild.side_effect = [
            # simulate build fail case
            {'name': 'bash',
             'version': '4.4.12',
             'release': '5.fc26',
             'state': self.bstate['FAILED']},

            # after calling createEmptyBuild, getBuild should return:
            {'name': 'bash',
             'version': '4.4.12',
             'release': '5.fc26',
             'state': self.bstate['COMPLETE']},
        ]

        # no RPM info is returned
        session.getRPM.return_value = {}
        self.__do_import_test(
            options, session, arguments + ['--create-build'],
            rpm_header=self.srpm_header,
            expected=expected)

        kwarg = dict((k, self.rpm_header.get(k, None))
                     for k in ['name', 'version', 'release', 'epoch'])
        session.createEmptyBuild.assert_called_with(**kwarg)

    @mock.patch('sys.stdout', new_callable=six.StringIO)
    @mock.patch('sys.stderr', new_callable=six.StringIO)
    @mock.patch('koji.get_header_fields')
    @mock.patch('koji_cli.commands.activate_session')
    def test_handle_import_binary_rpm_import_with_no_build_exist(
            self,
            activate_session_mock,
            get_header_fields_mock,
            stderr,
            stdout):
        """Test handle_import binary RPM import with no exist build case."""
        arguments = ['/path/to/bash-4.4.12-5.fc26.rpm']
        options = mock.MagicMock()
        session = mock.MagicMock()

        get_header_fields_mock.return_value = self.rpm_header

        nvr = '%(name)s-%(version)s-%(release)s' % get_header_fields_mock.return_value

        # Case 1. without exist build on server
        # result: abort
        session.getBuild.return_value = None
        handle_import(options, session, arguments)
        expected = "Missing build or srpm: %s\n" % nvr
        expected += "Aborting import\n"
        self.assert_console_message(stdout, expected)

        # Case 2. without exist build on server,
        #         with --create-build option
        # result: import will be performed
        session.getBuild.return_value = None
        session.getRPM.return_value = None

        expected = "Missing build or srpm: %s\n" % nvr
        expected += "Creating empty build: %s\n" % nvr
        expected += "uploading %s... done\n" % arguments[0]
        expected += "importing %s... done\n" % arguments[0]

        self.__do_import_test(
            options, session, arguments + ['--create-build'],
            rpm_header=self.rpm_header,
            expected=expected)

        kwarg = dict((k, self.rpm_header.get(k, None))
                     for k in ['name', 'version', 'release', 'epoch'])
        session.createEmptyBuild.assert_called_with(**kwarg)

    @mock.patch('sys.stdout', new_callable=six.StringIO)
    @mock.patch('sys.stderr', new_callable=six.StringIO)
    @mock.patch('koji_cli.commands.activate_session')
    def test_handle_import_binary_rpm_with_exist_build(
            self,
            activate_session_mock,
            stderr,
            stdout):
        """Test handle_import binary RPM import with exist build case."""
        arguments = ['/path/to/bash-4.4.12-5.fc26.rpm']
        options = mock.MagicMock()
        session = mock.MagicMock()

        nvr = '%(name)s-%(version)s-%(release)s' % self.rpm_header

        # Case 1. have exist build on server, build status is COMPLETE case.
        # result: skip import
        session.getBuild.return_value = {'state': self.bstate['COMPLETE']}
        session.getRPM.return_value = {
            'external_repo_name': 'INTERNAL',
            'payloadhash': self.md5,
        }
        expected = "RPM already imported: %s\n" % arguments[0]
        expected += "Skipping import\n"
        self.__skip_import_test(
            options, session, arguments,
            rpm_header=self.rpm_header,
            expected=expected)

        # Case 2. have exist build on server, build status is failed,
        #         without --create-build case.
        # result: import will be skipped
        session.getBuild.return_value = {'state': self.bstate['FAILED']}
        expected = "Build %s state is %s. Skipping import\n" % (nvr, 'FAILED')
        self.__skip_import_test(
            options, session, arguments,
            rpm_header=self.rpm_header,
            expected=expected)

        # Case 3. have exist build on server, build status is failed,
        #         with --create-build,
        # result:
        #         empty build will be created,
        #         import will be performed.
        expected = "Creating empty build: %s\n" % nvr
        expected += "uploading %s... done\n" % arguments[0]
        expected += "importing %s... done\n" % arguments[0]

        session.getBuild.side_effect = [
            # binary rpm case,
            # getBuild is called to check build.
            {'state': self.bstate['FAILED']},

            # simulate build fail case
            {'name': 'bash',
             'version': '4.4.12',
             'release': '5.fc26',
             'state': self.bstate['FAILED']},

            # after calling createEmptyBuild, getBuild should return:
            {'name': 'bash',
             'version': '4.4.12',
             'release': '5.fc26',
             'state': self.bstate['COMPLETE']},
        ]

        # no RPM info is returned
        session.getRPM.return_value = {}
        self.__do_import_test(
            options, session, arguments + ['--create-build'],
            rpm_header=self.rpm_header,
            expected=expected)

        kwarg = dict((k, self.rpm_header.get(k, None))
                     for k in ['name', 'version', 'release', 'epoch'])
        session.createEmptyBuild.assert_called_with(**kwarg)

    @mock.patch('sys.stdout', new_callable=six.StringIO)
    @mock.patch('koji.get_header_fields')
    @mock.patch('koji_cli.commands.unique_path')
    @mock.patch('koji_cli.commands.activate_session')
    def test_handle_import_with_test_option(
            self,
            activate_session_mock,
            unique_path_mock,
            get_header_fields_mock,
            stdout):
        """Test handle_import RPM with --test option"""
        options = mock.MagicMock()
        session = mock.MagicMock()

        nvr = lambda: '%(name)s-%(version)s-%(release)s' % get_header_fields_mock.return_value

        # Case 1. SRPM case
        # result: skip because of --test
        get_header_fields_mock.return_value = self.srpm_header

        session.getBuild.return_value = {}
        session.getRPM.return_value = {}

        arguments = ['/path/to/bash-4.4.12-5.fc26.src.rpm', '--test']
        expected = "Test mode -- skipping import for %s\n" % arguments[0]

        handle_import(options, session, arguments)
        self.assert_console_message(stdout, expected)
        unique_path_mock.assert_not_called()
        session.importRPM.assert_not_called()

        # Case 2. Binary RPM case (need --create-build option)
        # result: skip because of --test
        session.getBuild.side_effect = [
            # binary rpm case,
            # getBuild is called to check build.
            {'state': self.bstate['FAILED']},

            # simulate build fail case
            {'name': 'bash',
             'version': '4.4.12',
             'release': '5.fc26',
             'state': self.bstate['FAILED']},
        ]

        get_header_fields_mock.return_value = self.rpm_header

        arguments = ['/path/to/bash-4.4.12-5.fc26.rpm', '--test', '--create-build']
        expected = "Test mode -- would have created empty build: %s\n" % nvr()
        expected += "Test mode -- skipping import for %s\n" % arguments[0]

        with mock.patch('koji_cli.commands.unique_path') as unique_path_mock:
            handle_import(options, session, arguments)
        self.assert_console_message(stdout, expected)
        unique_path_mock.assert_not_called()
        session.createEmptyBuild.assert_not_called()
        session.importRPM.assert_not_called()

    @mock.patch('sys.stdout', new_callable=six.StringIO)
    @mock.patch('koji.get_header_fields')
    @mock.patch('koji_cli.commands.unique_path')
    @mock.patch('koji_cli.commands.activate_session')
    def test_handle_import_with_epoch_option(
            self,
            activate_session_mock,
            unique_path_mock,
            get_header_fields_mock,
            stdout):
        """Test handle_import RPM with --src-epoch option"""
        options = mock.MagicMock()
        session = mock.MagicMock()
        epoch = "1"
        nvr = '%(name)s-%(version)s-%(release)s' % self.rpm_header

        # Binary RPM case (need --create-build option)
        # result: skip because of --test
        arguments = ['/path/to/bash-4.4.12-5.fc26.rpm',
                     '--create-build',
                     '--src-epoch', epoch]

        expected = "Creating empty build: %s\n" % nvr
        expected += "uploading %s... done\n" % arguments[0]
        expected += "importing %s... done\n" % arguments[0]

        session.getBuild.side_effect = [
            # binary rpm case,
            # getBuild is called to check build.
            {'state': self.bstate['FAILED']},

            # simulate build fail case
            {'name': 'bash',
             'version': '4.4.12',
             'release': '5.fc26',
             'state': self.bstate['FAILED']},

            # after calling createEmptyBuild, getBuild should return:
            {'name': 'bash',
             'version': '4.4.12',
             'release': '5.fc26',
             'state': self.bstate['COMPLETE']},
        ]

        # no RPM info is returned
        session.getRPM.return_value = {}
        self.__do_import_test(
            options, session, arguments + ['--create-build'],
            rpm_header=self.rpm_header,
            expected=expected)

        kwarg = dict((k, self.rpm_header.get(k, None))
                     for k in ['name', 'version', 'release', 'epoch'])
        kwarg['epoch'] = int(epoch)
        session.createEmptyBuild.assert_called_with(**kwarg)

    @mock.patch('sys.stdout', new_callable=six.StringIO)
    @mock.patch('sys.stderr', new_callable=six.StringIO)
    @mock.patch('koji.get_header_fields')
    @mock.patch('koji_cli.commands.activate_session')
    def test_handle_import_has_build_states_test(
            self,
            activate_session_mock,
            get_header_fields_mock,
            stderr,
            stdout):
        """Test handle_import RPM with existing build but status not COMPLETE case"""
        arguments = ['/path/to/bash-4.4.12-5.fc26.src.rpm']
        options = mock.MagicMock()
        session = mock.MagicMock()

        get_header_fields_mock.return_value = self.srpm_header

        test_cases = [
            {
                'state': 'FAILED',
                'msg': "Build %s state is %s. Skipping import"
            },
            {
                'state': 'CANCELED',
                'msg': "Build %s state is %s. Skipping import"
            },
            {
                'state': 'DELETED',
                'msg': 'Build %s exists with state=%s. Skipping import'
            },
            {
                'state': 'BUILDING',
                'msg': 'Build %s exists with state=%s. Skipping import'
            }
        ]

        nvr = '%(name)s-%(version)s-%(release)s' % \
            get_header_fields_mock.return_value
        # build failed cases
        for case in test_cases:
            session.getBuild.return_value = {
                'state': self.bstate[case['state']]}

            handle_import(options, session, arguments)
            expected = case['msg'] % (nvr, case['state']) + "\n"
            self.assert_console_message(stdout, expected)
            get_header_fields_mock.assert_called_with(
                arguments[0],
                ('name', 'version', 'release', 'epoch',
                 'arch', 'sigmd5', 'sourcepackage', 'sourcerpm')
            )
            activate_session_mock.assert_called_with(session, options)
            session.getRPM.assert_not_called()
            session.importRPM.assert_not_called()

    @mock.patch('sys.stderr', new_callable=six.StringIO)
    @mock.patch('koji_cli.commands.activate_session')
    def test_handle_import_argument_error(
            self,
            activate_session_mock,
            stderr):
        """Test handle_import function with error arguments"""
        options = mock.MagicMock()
        session = mock.MagicMock()
        epoch = 'zzz'

        test_cases = [
            # empty argument error
            {
                'arguments': [],
                'error': "At least one package must be specified"
            },
            # invalid epoch number test (epoch must be integer)
            {
                'arguments': ['pkg', '--src-epoch', epoch],
                'error': "Invalid value for epoch: %s" % epoch
            }
        ]

        for case in test_cases:
            expect = self.format_error_message(case['error'])
            self.assert_system_exit(
                handle_import,
                options,
                session,
                case['arguments'],
                stderr=expect,
                activate_session=None)
            activate_session_mock.assert_not_called()

    def test_handle_import_help(self):
        """Test handle_import function help message"""
        self.assert_help(
            handle_import,
            """Usage: %s import [options] <package> [<package> ...]
(Specify the --help global option for a list of other help options)

Options:
  -h, --help            show this help message and exit
  --link                Attempt to hardlink instead of uploading
  --test                Don't actually import
  --create-build        Auto-create builds as needed
  --src-epoch=SRC_EPOCH
                        When auto-creating builds, use this epoch
""" % self.progname)


if __name__ == '__main__':
    unittest.main()
