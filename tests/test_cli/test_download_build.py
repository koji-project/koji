from __future__ import absolute_import

try:
    from unittest import mock
except ImportError:
    import mock
from six.moves import StringIO

import koji
from koji_cli.commands import anon_handle_download_build
from . import utils


class TestDownloadBuild(utils.CliTestCase):
    def setUp(self):
        self.maxDiff = None
        self.options = mock.MagicMock()
        self.options.debug = False
        self.session = mock.MagicMock()
        self.session.getAPIVersion.return_value = koji.API_VERSION
        self.error_format = """Usage: %s download-build [options] <n-v-r|build_id>

Downloads files from the specified build entry
Note: scratch builds do not have build entries. Use download-task for those
(Specify the --help global option for a list of other help options)

%s: error: {message}
""" % (self.progname, self.progname)

        self.build_templ = {
            'package_name': 'bash',
            'version': '4.4.12',
            'release': '5.fc26',
            'epoch': None,
            'nvr': 'bash-4.4.12-5.fc26',
            'build_id': 1,
            'id': 123,
            'name': 'bash',
        }
        self.b_label = '%(name)s-%(version)s-%(release)s' % self.build_templ

        self.getrpminfo = {'arch': 'noarch',
                           'build_id': 1,
                           'buildroot_id': 3,
                           'buildtime': 1615877809,
                           'epoch': 7,
                           'id': 294,
                           'name': 'test-rpm',
                           'release': '11',
                           'version': '1.1',
                           'payloadhash': 'b2b95550390e5f213fc25f33822425f7',
                           'size': 7030,
                           'nvr': 'test-rpm-1.1-11'
                           }
        self.listbuilds = [{'build_id': 1,
                            'epoch': 17,
                            'extra': None,
                            'name': 'test-build',
                            'nvr': 'test-build-1-11.f35',
                            'owner_id': 1,
                            'owner_name': 'testuser',
                            'package_id': 4,
                            'package_name': 'test-build',
                            'release': '11.f35',
                            'state': 1,
                            'task_id': 3,
                            'version': '1', }]
        self.sigkey = 'testkey'
        self.tag = 'test-tag'

    def test_download_build_without_argument(self):
        expected = self.format_error_message("Please specify a package N-V-R or build ID")
        self.assert_system_exit(
            anon_handle_download_build,
            self.options,
            self.session,
            [],
            stderr=expected,
            activate_session=None,
            exit_code=2
        )

    def test_download_build_more_arguments(self):
        expected = self.format_error_message(
            "Only a single package N-V-R or build ID may be specified")
        self.assert_system_exit(
            anon_handle_download_build,
            self.options,
            self.session,
            ['1', '2'],
            stderr=expected,
            activate_session=None,
            exit_code=2
        )

    def __vm(self, result):
        m = koji.VirtualCall('mcall_method', [], {})
        if isinstance(result, dict) and result.get('faultCode'):
            m._result = result
        else:
            m._result = (result,)
        return m

    @mock.patch('sys.stderr', new_callable=StringIO)
    def test_download_build_with_non_exist_sigkey(self, stderr):
        build_id = '1'
        nvra = "%(nvr)s-%(arch)s.rpm" % self.getrpminfo
        expected = "No such sigkey %s for rpm %s\n" % (self.sigkey, nvra)
        mcall = self.session.multicall.return_value.__enter__.return_value
        mcall.queryRPMSigs.return_value = self.__vm([])
        self.session.getRPM.return_value = self.getrpminfo
        self.session.getBuild.return_value = self.build_templ
        rv = anon_handle_download_build(self.options, self.session, [build_id, '--rpm',
                                                                     '--key', self.sigkey])
        self.assertEqual(rv, None)
        self.assert_console_message(stderr, expected)

    def test_download_build_without_rpm(self):
        build_id = '1'
        expected = "No such rpm: %s\n" % build_id
        self.session.getRPM.return_value = None
        self.assert_system_exit(
            anon_handle_download_build,
            self.options,
            self.session,
            ['--rpm', build_id],
            stderr=expected,
            activate_session=None,
            exit_code=1
        )

    def test_download_build_no_build(self):
        build_id = '1'
        expected = "No such build: %s\n" % build_id
        self.session.getRPM.return_value = self.getrpminfo
        self.session.getBuild.return_value = None
        self.assert_system_exit(
            anon_handle_download_build,
            self.options,
            self.session,
            [build_id],
            stderr=expected,
            activate_session=None,
            exit_code=1
        )

    def test_download_build_latest_from_no_build(self):
        nvr = self.build_templ['nvr']
        expected = "%s has no builds of %s\n" % (self.tag, nvr)
        self.session.getRPM.return_value = self.getrpminfo
        self.session.listTagged.return_value = []
        self.assert_system_exit(
            anon_handle_download_build,
            self.options,
            self.session,
            [nvr, '--latestfrom', self.tag],
            stderr=expected,
            activate_session=None,
            exit_code=1
        )

    def test_download_build_latest_from_build_id(self):
        build_id = '1'
        expected = self.format_error_message(
            "--latestfrom not compatible with build IDs, specify a package name.")
        self.assert_system_exit(
            anon_handle_download_build,
            self.options,
            self.session,
            [build_id, '--latestfrom', self.tag],
            stderr=expected,
            activate_session=None,
            exit_code=2
        )

    @mock.patch('sys.stdout', new_callable=StringIO)
    @mock.patch('sys.stderr', new_callable=StringIO)
    def test_download_task_id(self, stderr, stdout):
        build_id = '1'
        self.session.listBuilds.return_value = self.listbuilds
        anon_handle_download_build(self.options, self.session, ['--task-id', build_id])
        self.assert_console_message(stdout, "")
        self.assert_console_message(stderr, "")

    def test_download_no_asociated_build_task(self):
        build_id = '1'
        self.session.listBuilds.return_value = []
        self.assert_system_exit(
            anon_handle_download_build,
            self.options,
            self.session,
            ['--task-id', build_id],
            stderr='No associated builds for task %s\n' % build_id,
            stdout='',
            activate_session=None,
            exit_code=1
        )

    def test_download_build_latest_from_error_find_build(self):
        build_id = 'package-name'
        self.session.listTagged.side_effect = koji.GenericError
        self.assert_system_exit(
            anon_handle_download_build,
            self.options,
            self.session,
            [build_id, '--latestfrom', self.tag],
            stderr='Error finding latest build: {}\n',
            activate_session=None,
            exit_code=1
        )

    def test_download_build_topurl_none(self):
        build_id = '1'
        self.assert_system_exit(
            anon_handle_download_build,
            self.options,
            self.session,
            [build_id, '--topurl', None],
            stderr='You must specify --topurl to download files\n',
            activate_session=None,
            exit_code=1
        )

    @mock.patch('koji.buildLabel')
    def test_download_build_type_not_scratch(self, build_label):
        build_id = '1'
        type = 'rpm'
        self.session.listArchives.return_value = []
        nvr = self.build_templ['nvr']
        build_label.return_value = nvr
        self.assert_system_exit(
            anon_handle_download_build,
            self.options,
            self.session,
            [build_id, '--type', type],
            stderr='No %s archives available for %s\n' % (type, nvr),
            activate_session=None,
            exit_code=1
        )

    @mock.patch('koji.buildLabel')
    def test_download_build_without_all_rpms_with_arches(self, build_label):
        build_id = '1'
        arches = ['testarch', 'testarch2']
        build_label.return_value = self.b_label
        self.session.getRPM.return_value = self.getrpminfo
        self.session.getBuild.return_value = self.build_templ
        self.session.listRPMs.return_value = []
        self.assert_system_exit(
            anon_handle_download_build,
            self.options,
            self.session,
            [build_id, '--arch', arches[0], '--arch', arches[1], '--key', self.sigkey],
            stderr='No %s or %s packages available for %s\n'
                   % (arches[0], arches[1], self.b_label),
            activate_session=None,
            exit_code=1
        )

    @mock.patch('koji.buildLabel')
    def test_download_build_without_all_rpms(self, build_label):
        build_id = '1'
        build_label.return_value = self.b_label
        self.session.getRPM.return_value = self.getrpminfo
        self.session.getBuild.return_value = self.build_templ
        self.session.listRPMs.return_value = []
        self.assert_system_exit(
            anon_handle_download_build,
            self.options,
            self.session,
            [build_id, '--key', self.sigkey],
            stderr='No packages available for %s\n' % self.b_label,
            activate_session=None,
            exit_code=1
        )

    def test_handle_add_volume_help(self):
        self.assert_help(
            anon_handle_download_build,
            """Usage: %s download-build [options] <n-v-r|build_id>

Downloads files from the specified build entry
Note: scratch builds do not have build entries. Use download-task for those
(Specify the --help global option for a list of other help options)

Options:
  -h, --help            show this help message and exit
  -a ARCH, --arch=ARCH  Only download packages for this arch (may be used
                        multiple times)
  --type=TYPE           Download archives of the given type, rather than rpms
                        (maven, win, image, remote-sources)
  --latestfrom=LATESTFROM
                        Download the latest build from this tag
  --debuginfo           Also download -debuginfo rpms
  --task-id             Interperet id as a task id
  --rpm                 Download the given rpm
  --key=KEY             Download rpms signed with the given key
  --topurl=URL          URL under which Koji files are accessible
  --noprogress          Do not display progress meter
  -q, --quiet           Suppress output
""" % self.progname)
