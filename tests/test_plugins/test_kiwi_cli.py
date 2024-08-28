import mock
import io
import os
import sys


sys.path = [os.path.join(os.path.dirname(__file__), '..')] + sys.path
from test_cli import utils

import plugins.cli.kiwi as kiwi

class TestAddChannel(utils.CliTestCase):
    def setUp(self):
        self.maxDiff = None
        self.task_id = 1
        self.options = mock.MagicMock()
        self.session = mock.MagicMock()
        self.session.hub_version = (1, 35, 0)
        #self.activate_session_mock = mock.patch('koji_cli.lib.activate_session').start()
        self.error_format = """Usage: %s add-channel [options] <channel_name>
(Specify the --help global option for a list of other help options)

%s: error: {message}
""" % (self.progname, self.progname)
        self.target = 'target'
        self.description_scm = 'git://scm'
        self.description_path = 'path/to/file.kiwi'

    def tearDown(self):
        mock.patch.stopall()

    @mock.patch('sys.stderr', new_callable=io.StringIO)
    @mock.patch('sys.stdout', new_callable=io.StringIO)
    def test_handle_kiwi_build_old_hub(self, stdout, stderr):
        # missing use_buildroot_repo option
        kiwi.watch_tasks = mock.MagicMock()
        self.session.hub_version = (1, 34, 1)
        self.session.kiwiBuild.return_value = self.task_id
        rv = kiwi.handle_kiwi_build(self.options, self.session,
                                    [
                                      self.target,
                                      self.description_scm,
                                      self.description_path
                                    ])
        actual = stderr.getvalue()
        expected = 'hub version is < 1.35, buildroot repo is always used in addition to specified repos\n'
        self.assertMultiLineEqual(actual, expected)
        self.assertMultiLineEqual(stdout.getvalue(), '')
        self.session.kiwiBuild.assert_called_once_with(
            arches=[],
            target=self.target,
            desc_url=self.description_scm,
            desc_path=self.description_path,
        )
        self.assertNotEqual(rv, 1)

    @mock.patch('sys.stderr', new_callable=io.StringIO)
    @mock.patch('sys.stdout', new_callable=io.StringIO)
    def test_handle_kiwi_build_newd_hub(self, stdout, stderr):
        # introduced use_buildroot_repo option
        kiwi.watch_tasks = mock.MagicMock()
        self.session.hub_version = (1, 35, 0)
        self.session.kiwiBuild.return_value = self.task_id
        rv = kiwi.handle_kiwi_build(self.options, self.session,
                                    [
                                      self.target,
                                      self.description_scm,
                                      self.description_path
                                    ])
        actual = stderr.getvalue()
        expected = 'no repos given, using buildroot repo\n'
        self.assertMultiLineEqual(actual, expected)
        self.assertMultiLineEqual(stdout.getvalue(), '')
        self.session.kiwiBuild.assert_called_once_with(
            arches=[],
            target=self.target,
            desc_url=self.description_scm,
            desc_path=self.description_path,
            use_buildroot_repo=True,
        )
        self.assertNotEqual(rv, 1)

    @mock.patch('sys.stderr', new_callable=io.StringIO)
    @mock.patch('sys.stdout', new_callable=io.StringIO)
    def test_handle_kiwi_all_options(self, stdout, stderr):
        # introduced use_buildroot_repo option
        kiwi.watch_tasks = mock.MagicMock()
        self.session.hub_version = (1, 35, 0)
        self.session.kiwiBuild.return_value = self.task_id
        rv = kiwi.handle_kiwi_build(self.options, self.session,
                                    [
                                      self.target,
                                      self.description_scm,
                                      self.description_path,
                                      '--scratch',
                                      '--version=test_version',
                                      '--release=test_release',
                                      '--repo=https://test_repo_1',
                                      '--repo=https://test_repo_2',
                                      '--buildroot-repo',
                                      '--repo-releasever=releasever',
                                      '--noprogress',
                                      '--kiwi-profile=profile.kiwi',
                                      '--type=build_type',
                                      '--type-attr=type_attr',
                                      '--result-bundle-name-format=name_format',
                                      '--make-prep',
                                      '--can-fail=x86_64',
                                      '--arch=x86_64',
                                      '--arch=s390x',
                                      '--nowait',
                                    ])
        actual = stderr.getvalue()
        expected = ''
        self.assertMultiLineEqual(actual, expected)
        self.assertMultiLineEqual(stdout.getvalue(), '')
        self.session.kiwiBuild.assert_called_once_with(
            arches=['x86_64', 's390x'],
            target=self.target,
            desc_url=self.description_scm,
            desc_path=self.description_path,
            scratch=True,
            optional_arches=['x86_64'],
            profile='profile.kiwi',
            version='test_version',
            release='test_release',
            make_prep=True,
            type='build_type',
            type_attr=['type_attr'],
            result_bundle_name_format='name_format',
            repos=['https://test_repo_1', 'https://test_repo_2'],
            repo_releasever='releasever',
            use_buildroot_repo=True,
        )
        self.assertNotEqual(rv, 1)


