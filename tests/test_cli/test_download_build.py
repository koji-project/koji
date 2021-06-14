from __future__ import absolute_import

import mock
from six.moves import StringIO

import koji
from koji_cli.commands import anon_handle_download_build
from . import utils


class TestDownloadBuild(utils.CliTestCase):
    def setUp(self):
        self.options = mock.MagicMock()
        self.options.debug = False
        self.session = mock.MagicMock()
        self.session.getAPIVersion.return_value = koji.API_VERSION

        self.build_templ = {
            'package_name': 'bash',
            'version': '4.4.12',
            'release': '5.fc26',
            'epoch': None,
            'nvr': 'bash-4.4.12-5.fc26',
            'build_id': 1,
        }

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
        self.sigkey = 'testkey'
        self.tag = 'test-tag'

    @mock.patch('sys.stderr', new_callable=StringIO)
    def test_download_build_without_option(self, stderr):
        expected = "Usage: %s download-build [options] <n-v-r | build_id | package>\n" \
                   "(Specify the --help global option for a list of other help options)\n\n" \
                   "%s: error: Please specify a package N-V-R or build ID\n" \
                   % (self.progname, self.progname)
        with self.assertRaises(SystemExit) as ex:
            anon_handle_download_build(self.options, self.session, [])
        self.assertExitCode(ex, 2)
        self.assert_console_message(stderr, expected)

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

    @mock.patch('sys.stderr', new_callable=StringIO)
    def test_download_build_without_rpm(self, stderr):
        build_id = '1'
        expected = "No such rpm: %s\n" % build_id
        self.session.getRPM.return_value = None
        with self.assertRaises(SystemExit) as ex:
            anon_handle_download_build(self.options, self.session, ['--rpm', build_id])
        self.assertExitCode(ex, 1)
        self.assert_console_message(stderr, expected)

    @mock.patch('sys.stderr', new_callable=StringIO)
    def test_download_build_no_build(self, stderr):
        build_id = '1'
        expected = "No such build: %s\n" % build_id
        self.session.getRPM.return_value = self.getrpminfo
        self.session.getBuild.return_value = None
        with self.assertRaises(SystemExit) as ex:
            anon_handle_download_build(self.options, self.session, [build_id])
        self.assertExitCode(ex, 1)
        self.assert_console_message(stderr, expected)

    @mock.patch('sys.stderr', new_callable=StringIO)
    def test_download_build_latest_from_no_build(self, stderr):
        nvr = self.build_templ['nvr']
        expected = "%s has no builds of %s\n" % (self.tag, nvr)
        self.session.getRPM.return_value = self.getrpminfo
        self.session.listTagged.return_value = []
        with self.assertRaises(SystemExit) as ex:
            anon_handle_download_build(self.options, self.session, [nvr, '--latestfrom', self.tag])
        self.assertExitCode(ex, 1)
        self.assert_console_message(stderr, expected)

    @mock.patch('sys.stderr', new_callable=StringIO)
    def test_download_build_latest_from_build_id(self, stderr):
        build_id = '1'
        expected = "Usage: %s download-build [options] <n-v-r | build_id | package>\n" \
                   "(Specify the --help global option for a list of other help options)\n\n" \
                   "%s: error: --latestfrom not compatible with build IDs, " \
                   "specify a package name.\n" % (self.progname, self.progname)
        with self.assertRaises(SystemExit) as ex:
            anon_handle_download_build(self.options, self.session, [build_id, '--latestfrom',
                                                                    self.tag])
        self.assertExitCode(ex, 2)
        self.assert_console_message(stderr, expected)

    def test_handle_add_volume_help(self):
        self.assert_help(
            anon_handle_download_build,
            """Usage: %s download-build [options] <n-v-r | build_id | package>
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
