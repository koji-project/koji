from __future__ import absolute_import
import koji
import mock
import os
import time
from six.moves import StringIO

from koji_cli.commands import anon_handle_rpminfo
from . import utils


class TestRpminfo(utils.CliTestCase):
    def setUp(self):
        self.maxDiff = None
        self.options = mock.MagicMock()
        self.options.quiet = True
        self.options.debug = False
        self.session = mock.MagicMock()
        self.session.getAPIVersion.return_value = koji.API_VERSION
        self.original_timezone = os.environ.get('TZ')
        os.environ['TZ'] = 'UTC'
        time.tzset()
        self.buildroot_info = {'arch': 'x86_64',
                               'br_type': 0,
                               'host_id': 1,
                               'host_name': 'kojibuilder',
                               'id': 3,
                               'repo_id': 2,
                               'tag_id': 4,
                               'tag_name': 'test-tag',
                               'task_id': 10}
        self.buildinfo = {'build_id': 1,
                          'epoch': 7,
                          'id': 1,
                          'name': 'test-rpm',
                          'nvr': 'test-rpm-1.1-11',
                          'package_id': 2,
                          'package_name': 'test-rpm',
                          'release': '11',
                          'task_id': 8,
                          'version': '1.1'}
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
                           'size': 7030}

    def tearDown(self):
        if self.original_timezone is None:
            del os.environ['TZ']
        else:
            os.environ['TZ'] = self.original_timezone
        time.tzset()

    @mock.patch('sys.stdout', new_callable=StringIO)
    def test_handle_rpminfo_valid(self, stdout):
        rpm_nvra = 'test-rpm-1.1-11.noarch'
        self.session.getBuildroot.return_value = self.buildroot_info
        self.session.listBuildroots.return_value = [self.buildroot_info]
        self.session.getBuild.return_value = self.buildinfo
        self.session.getRPM.return_value = self.getrpminfo
        expected_output = """RPM: 7:test-rpm-1.1-11.noarch [294]
RPM Path: /mnt/koji/packages/test-rpm/1.1/11/noarch/test-rpm-1.1-11.noarch.rpm
SRPM: 7:test-rpm-1.1-11 [1]
SRPM Path: /mnt/koji/packages/test-rpm/1.1/11/src/test-rpm-1.1-11.src.rpm
Built: Tue, 16 Mar 2021 06:56:49 UTC
SIGMD5: b2b95550390e5f213fc25f33822425f7
Size: 7030
Build ID: 1
Buildroot: 3 (tag test-tag, arch x86_64, repo 2)
Build Host: kojibuilder
Build Task: 10
Used in 1 buildroots:
        id build tag                    arch     build host                   
  -------- ---------------------------- -------- -----------------------------
         3 test-tag                     x86_64   kojibuilder                  
"""

        anon_handle_rpminfo(self.options, self.session, ['--buildroot', rpm_nvra])
        self.assert_console_message(stdout, expected_output)
        self.session.getBuildroot.assert_called_once_with(self.getrpminfo['buildroot_id'])
        self.session.listBuildroots.assert_called_once_with(queryOpts={'order': 'buildroot.id'},
                                                            rpmID=self.getrpminfo['id'])
        self.session.getBuild.assert_called_once_with(self.getrpminfo['build_id'])
        self.session.getRPM.assert_called_once_with(rpm_nvra)

    @mock.patch('sys.stderr', new_callable=StringIO)
    def test_handle_rpminfo_non_exist_nvra(self, stderr):
        rpm_nvra = 'test-rpm-nvra.arch'
        self.session.getRPM.return_value = None
        expected = "No such rpm: %s\n" % rpm_nvra + "\n"
        with self.assertRaises(SystemExit) as ex:
            anon_handle_rpminfo(self.options, self.session, ['--buildroot', rpm_nvra])
        self.assertExitCode(ex, 1)
        self.assert_console_message(stderr, expected)

    @mock.patch('sys.stderr', new_callable=StringIO)
    @mock.patch('sys.stdout', new_callable=StringIO)
    def test_handle_rpminfo_more_nvra_non_exist_nvra(self, stdout, stderr):
        rpm_nvra = 'test-rpm-1.1-11.noarch'
        non_exist_rpm_nvra = 'not-test-rpm-11-112.arch'
        self.session.getBuildroot.return_value = self.buildroot_info
        self.session.listBuildroots.return_value = [self.buildroot_info]
        self.session.getBuild.return_value = self.buildinfo
        self.session.getRPM.side_effect = [None, self.getrpminfo]
        expected_output = """RPM: 7:test-rpm-1.1-11.noarch [294]
RPM Path: /mnt/koji/packages/test-rpm/1.1/11/noarch/test-rpm-1.1-11.noarch.rpm
SRPM: 7:test-rpm-1.1-11 [1]
SRPM Path: /mnt/koji/packages/test-rpm/1.1/11/src/test-rpm-1.1-11.src.rpm
Built: Tue, 16 Mar 2021 06:56:49 UTC
SIGMD5: b2b95550390e5f213fc25f33822425f7
Size: 7030
Build ID: 1
Buildroot: 3 (tag test-tag, arch x86_64, repo 2)
Build Host: kojibuilder
Build Task: 10
Used in 1 buildroots:
        id build tag                    arch     build host                   
  -------- ---------------------------- -------- -----------------------------
         3 test-tag                     x86_64   kojibuilder                  
"""

        expected_error = "No such rpm: %s\n" % non_exist_rpm_nvra + "\n"
        with self.assertRaises(SystemExit) as ex:
            anon_handle_rpminfo(self.options, self.session,
                                ['--buildroot', non_exist_rpm_nvra, rpm_nvra])
        self.assertExitCode(ex, 1)
        self.assert_console_message(stdout, expected_output)
        self.assert_console_message(stderr, expected_error)
        self.session.getBuildroot.assert_called_once_with(self.getrpminfo['buildroot_id'])
        self.session.listBuildroots.assert_called_once_with(queryOpts={'order': 'buildroot.id'},
                                                            rpmID=self.getrpminfo['id'])
        self.session.getBuild.assert_called_once_with(self.getrpminfo['build_id'])
        self.assertEqual(self.session.getRPM.call_count, 2)
