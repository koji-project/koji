from __future__ import absolute_import
import mock
from six.moves import StringIO
import koji

from koji_cli.commands import handle_list_signed
from . import utils


class TestListSigned(utils.CliTestCase):

    def setUp(self):
        self.options = mock.MagicMock()
        self.options.debug = True
        self.session = mock.MagicMock()
        self.activate_session_mock = mock.patch('koji_cli.commands.activate_session').start()
        self.error_format = """Usage: %s list-signed [options]
(Specify the --help global option for a list of other help options)

%s: error: {message}
""" % (self.progname, self.progname)

    def __vm(self, result):
        m = koji.VirtualCall('mcall_method', [], {})
        if isinstance(result, dict) and result.get('faultCode'):
            m._result = result
        else:
            m._result = (result,)
        return m

    def test_list_signed_help(self):
        self.assert_help(
            handle_list_signed,
            """Usage: %s list-signed [options]
(Specify the --help global option for a list of other help options)

You must have local access to Koji's topdir filesystem.

Options:
  -h, --help     show this help message and exit
  --key=KEY      Only list RPMs signed with this key
  --build=BUILD  Only list RPMs from this build
  --rpm=RPM      Only list signed copies for this RPM
  --tag=TAG      Only list RPMs within this tag
""" % self.progname)

    def test_list_signed_without_arg(self):
        arguments = []
        self.assert_system_exit(
            handle_list_signed,
            self.options, self.session, arguments,
            stdout='',
            stderr=self.format_error_message(
                "At least one from --build, --rpm, --tag needs to be specified."),
            exit_code=2,
            activate_session=None)
        self.activate_session_mock.assert_not_called()
        self.session.getBuild.assert_not_called()
        self.session.listRPMs.assert_not_called()
        self.session.queryRPMSigs.assert_not_called()
        self.session.getRPM.assert_not_called()

    def test_list_signed_rpm_external_rpm_error(self):
        arguments = ['--rpm=test-rpm']
        rinfo = {'id': 123, 'name': 'test', 'version': '1.3', 'release': 1, 'arch': 'test-arch',
                 'external_repo_name': 'ext-repo', 'external_repo_id': 456}
        err_msg = "External rpm: %(name)s-%(version)s-%(release)s.%(arch)s@" \
                  "%(external_repo_name)s" % rinfo
        self.session.getRPM.return_value = rinfo
        self.assert_system_exit(
            handle_list_signed,
            self.options, self.session, arguments,
            stdout='',
            stderr=self.format_error_message(err_msg),
            exit_code=2,
            activate_session=None)
        self.activate_session_mock.assert_called_once_with(self.session, self.options)
        self.session.getBuild.assert_not_called()
        self.session.listRPMs.assert_not_called()
        self.session.queryRPMSigs.assert_not_called()
        self.session.getRPM.assert_called_once_with('test-rpm', strict=True)

    @mock.patch('koji.pathinfo.build', return_value='fakebuildpath')
    @mock.patch('sys.stdout', new_callable=StringIO)
    def test_list_signed_rpm_with_build_non_exist_path(self, stdout, pb):
        binfo = {'build_id': 1, 'id': 1, 'name': 'test-build', 'release': '1', 'task_id': 8,
                 'version': '1', 'state': 1, 'completion_ts': 1614869140.368759,
                 'owner_name': 'kojiadmin', 'volume_name': 'DEFAULT',
                 'package_name': 'test-package'}
        list_rpms = [{'id': 123, 'name': 'test', 'version': '1.3', 'release': 1,
                      'arch': 'test-arch', 'external_repo_name': 'ext-repo',
                      'external_repo_id': 456, 'build_id': 1}]
        sigRpm = [{'rpm_id': 123, 'sigkey': 'qwertyuiop'}]
        self.session.getBuild.return_value = binfo
        self.session.listRPMs.return_value = list_rpms
        self.session.queryRPMSigs.return_value = sigRpm
        handle_list_signed(self.options, self.session, ['--build=test-build'])
        path = 'fakebuildpath/data/signed/%s/%s/%s-%s-%s.%s.rpm' \
               % (sigRpm[0]['sigkey'], list_rpms[0]['arch'], list_rpms[0]['name'],
                  list_rpms[0]['version'], list_rpms[0]['release'], list_rpms[0]['arch'])
        self.assert_console_message(stdout, 'No copy: %s\n' % path)
        self.activate_session_mock.assert_called_once_with(self.session, self.options)
        self.session.getBuild.assert_called_once_with('test-build', strict=True)
        self.session.listRPMs.assert_called_once_with(buildID=binfo['id'])
        self.session.queryRPMSigs.assert_called_once_with(rpm_id=list_rpms[0]['id'])
        self.session.getRPM.assert_not_called()

    @mock.patch('os.path.exists', return_value=True)
    @mock.patch('koji.pathinfo.build', return_value='fakebuildpath')
    @mock.patch('sys.stdout', new_callable=StringIO)
    def test_list_signed_rpm_with_build_valid(self, stdout, pb, os_path_exists):
        binfo = {'build_id': 1,
                 'id': 1,
                 'name': 'test-build',
                 'release': '1',
                 'task_id': 8,
                 'version': '1',
                 'state': 1,
                 'completion_ts': 1614869140.368759,
                 'owner_name': 'kojiadmin',
                 'volume_name': 'DEFAULT',
                 'package_name': 'test-package'}
        list_rpms = [
            {'id': 123, 'name': 'test', 'version': '1.3', 'release': 1, 'arch': 'test-arch',
             'build_id': 1}]
        sigRpm = [{'rpm_id': 123, 'sigkey': 'qwertyuiop'}]
        self.session.getBuild.return_value = binfo
        self.session.listRPMs.return_value = list_rpms
        self.session.queryRPMSigs.return_value = sigRpm
        handle_list_signed(self.options, self.session, ['--build=test-build'])
        path = 'fakebuildpath/data/signed/%s/%s/%s-%s-%s.%s.rpm' \
               % (sigRpm[0]['sigkey'], list_rpms[0]['arch'], list_rpms[0]['name'],
                  list_rpms[0]['version'], list_rpms[0]['release'], list_rpms[0]['arch'])
        self.assert_console_message(stdout, '%s\n' % path)
        self.activate_session_mock.assert_called_once_with(self.session, self.options)
        self.session.getBuild.assert_called_once_with('test-build', strict=True)
        self.session.listRPMs.assert_called_once_with(buildID=binfo['id'])
        self.session.queryRPMSigs.assert_called_once_with(rpm_id=list_rpms[0]['id'])
        self.session.getRPM.assert_not_called()

    @mock.patch('os.path.exists', return_value=True)
    @mock.patch('koji.pathinfo.build', return_value='fakebuildpath')
    @mock.patch('sys.stdout', new_callable=StringIO)
    def test_list_signed_rpm_with_rpm_and_with_key_valid(self, stdout, pb, os_path_exists):
        rinfo_1 = {'id': 123, 'name': 'test', 'version': '1.3', 'release': 1, 'arch': 'test-arch',
                   'build_id': 2}
        rinfo_2 = {'id': 124, 'name': 'test-2', 'version': '1.5', 'release': 1,
                   'arch': 'test-arch', 'build_id': 3}
        sigRpm = [{'rpm_id': 124, 'sigkey': 'qwertyuiop'}]
        self.session.getRPM.side_effect = [rinfo_1, rinfo_2]
        self.session.queryRPMSigs.return_value = sigRpm
        handle_list_signed(self.options, self.session, ['--rpm=test-rpm', '--key=qwertyuiop'])
        path = 'fakebuildpath/data/signed/%s/%s/%s-%s-%s.%s.rpm' \
               % (sigRpm[0]['sigkey'], rinfo_2['arch'], rinfo_2['name'],
                  rinfo_2['version'], rinfo_2['release'], rinfo_2['arch'])
        self.assert_console_message(stdout, '%s\n' % path)
        self.activate_session_mock.assert_called_once_with(self.session, self.options)
        self.session.getBuild.assert_called_once_with(rinfo_2['build_id'])
        self.session.listRPMs.assert_not_called()
        self.session.queryRPMSigs.assert_called_once_with(sigkey='qwertyuiop',
                                                          rpm_id=rinfo_1['id'])
        self.session.getRPM.assert_has_calls([mock.call('test-rpm', strict=True),
                                              mock.call(rinfo_2['id'])])

    @mock.patch('os.path.exists', return_value=True)
    @mock.patch('koji.pathinfo.build', return_value='fakebuildpath')
    @mock.patch('sys.stdout', new_callable=StringIO)
    def test_list_signed_rpm_tag_valid_and_with_key(self, stdout, pb, os_path_exists):
        tagged_rpms = [{'id': 100,
                        'build_id': 1,
                        'name': 'rpmA',
                        'version': '0.0.1',
                        'release': '1.el6',
                        'arch': 'noarch',
                        'sigkey': 'sigkey',
                        'extra': 'extra-value'},
                       ]
        tagged_builds = [{'id': 1,
                          'name': 'packagename',
                          'version': 'version',
                          'release': '1.el6',
                          'nvr': 'n-v-r',
                          'tag_name': 'tag',
                          'owner_name': 'owner',
                          'extra': 'extra-value-2',
                          'package_name': 'packagename'}]
        self.session.listTaggedRPMS.return_value = [tagged_rpms, tagged_builds]
        sigRpm = [{'rpm_id': 100, 'sigkey': 'qwertyuiop'}]
        mcall = self.session.multicall.return_value.__enter__.return_value
        mcall.queryRPMSigs.return_value = self.__vm(sigRpm)
        handle_list_signed(self.options, self.session, ['--tag=test-tag'])
        path = 'fakebuildpath/data/signed/%s/%s/%s-%s-%s.%s.rpm' \
               % (sigRpm[0]['sigkey'], tagged_rpms[0]['arch'], tagged_rpms[0]['name'],
                  tagged_rpms[0]['version'], tagged_rpms[0]['release'], tagged_rpms[0]['arch'])
        self.assert_console_message(stdout, '%s\n' % path)
        self.activate_session_mock.assert_called_once_with(self.session, self.options)
        self.session.listTaggedRPMS.assert_called_once_with(
            'test-tag', inherit=False, latest=False)
        self.session.getBuild.assert_not_called()
        self.session.listRPMs.assert_not_called()
        self.session.queryRPMSigs.assert_not_called()
        self.session.getRPM.assert_not_called()
