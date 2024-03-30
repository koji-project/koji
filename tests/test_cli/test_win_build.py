from __future__ import absolute_import

import mock
from six.moves import StringIO

import koji
from koji_cli.commands import handle_win_build
from . import utils


class TestWinBuild(utils.CliTestCase):
    def setUp(self):
        self.options = mock.MagicMock()
        self.options.debug = False
        self.options.quiet = None
        self.options.weburl = 'https://testwebkoji.org'
        self.options.poll_interval = 0
        self.session = mock.MagicMock()
        self.session.getAPIVersion.return_value = koji.API_VERSION
        self.stderr = mock.patch('sys.stderr', new_callable=StringIO).start()
        self.stdout = mock.patch('sys.stdout', new_callable=StringIO).start()
        self.target = 'test-target'
        self.dest_tag = 'destination-test_tag'
        self.target_info = {'build_tag': 4,
                            'build_tag_name': 'test_tag',
                            'dest_tag': 5,
                            'dest_tag_name': self.dest_tag,
                            'id': 2,
                            'name': self.target}
        self.scm_url = 'git://test.redhat.com/rpms/pkg-1.1.0' \
                       '?#3fab2ea42ecdc30a41daf1306154dfa04c4d64fd'
        self.vm = 'test-vm'
        self.watch_tasks_mock = mock.patch('koji_cli.commands.watch_tasks').start()
        self.watch_tasks_mock.return_value = 0
        self.running_in_bg_mock = mock.patch('koji_cli.commands._running_in_bg').start()
        self.error_format = """Usage: %s win-build [options] <target> <URL> <VM>
(Specify the --help global option for a list of other help options)

%s: error: {message}
""" % (self.progname, self.progname)

    def tearDown(self):
        mock.patch.stopall()

    def test_win_build_without_option(self):
        self.assert_system_exit(
            handle_win_build,
            self.options, self.session, [],
            stderr=self.format_error_message(
                "Exactly three arguments (a build target, a SCM URL, and a VM name) are required"),
            stdout='',
            activate_session=None,
            exit_code=2)
        self.session.getBuildTarget.assert_not_called()
        self.session.getTag.assert_not_called()
        self.running_in_bg_mock.assert_not_called()
        self.session.logout.assert_not_called()
        self.watch_tasks_mock.assert_not_called()

    def test_win_build_non_exist_build_target(self):
        self.session.getBuildTarget.return_value = None
        self.assert_system_exit(
            handle_win_build,
            self.options, self.session, [self.target, self.scm_url, self.vm],
            stderr=self.format_error_message("No such build target: %s" % self.target),
            stdout='',
            activate_session=None,
            exit_code=2)
        self.session.getBuildTarget.assert_called_once_with(self.target)
        self.session.getTag.assert_not_called()
        self.running_in_bg_mock.assert_not_called()
        self.session.logout.assert_not_called()
        self.watch_tasks_mock.assert_not_called()

    def test_win_build_non_exist_dest_tag(self):
        self.session.getBuildTarget.return_value = self.target_info
        self.session.getTag.return_value = None
        self.assert_system_exit(
            handle_win_build,
            self.options, self.session, [self.target, self.scm_url, self.vm],
            stderr=self.format_error_message("No such destination tag: %s" % self.dest_tag),
            stdout='',
            activate_session=None,
            exit_code=2)
        self.session.getBuildTarget.assert_called_once_with(self.target)
        self.session.getTag.assert_called_once_with(self.target_info['dest_tag'])
        self.running_in_bg_mock.assert_not_called()
        self.session.logout.assert_not_called()
        self.watch_tasks_mock.assert_not_called()

    def test_win_build_dest_tag_locked(self):
        dest_tag_info = {'name': self.dest_tag, 'locked': True}

        self.session.getBuildTarget.return_value = self.target_info
        self.session.getTag.return_value = dest_tag_info
        self.assert_system_exit(
            handle_win_build,
            self.options, self.session, [self.target, self.scm_url, self.vm],
            stderr=self.format_error_message("Destination tag %s is locked" % self.dest_tag),
            stdout='',
            activate_session=None,
            exit_code=2)
        self.session.getBuildTarget.assert_called_once_with(self.target)
        self.session.getTag.assert_called_once_with(self.target_info['dest_tag'])
        self.running_in_bg_mock.assert_not_called()
        self.session.logout.assert_not_called()
        self.watch_tasks_mock.assert_not_called()

    def test_win_build_not_queit_and_repo_id(self):
        self.running_in_bg_mock.return_value = True
        task_id = 111
        expected_output = """Created task: %d
Task info: %s/taskinfo?taskID=%s
""" % (task_id, self.options.weburl, task_id)
        self.session.winBuild.return_value = task_id
        rv = handle_win_build(self.options, self.session,
                              ["none", self.scm_url, self.vm, '--background', '--repo-id=10'])
        self.assertEqual(rv, None)
        self.assert_console_message(self.stdout, expected_output)
        self.assert_console_message(self.stderr, "")
        self.session.getBuildTarget.assert_not_called()
        self.session.getTag.assert_not_called()
        self.running_in_bg_mock.assert_called_once()
        self.session.logout.assert_not_called()
        self.watch_tasks_mock.assert_not_called()

    def test_win_build_wait_opt(self):
        task_id = 111
        dest_tag_info = {'name': self.dest_tag, 'locked': False}

        self.session.getBuildTarget.return_value = self.target_info
        self.session.getTag.return_value = dest_tag_info
        expected_output = """Created task: %d
Task info: %s/taskinfo?taskID=%s
""" % (task_id, self.options.weburl, task_id)
        self.session.winBuild.return_value = task_id
        rv = handle_win_build(self.options, self.session,
                              [self.target, self.scm_url, self.vm, '--wait'])
        self.assertEqual(rv, 0)
        self.assert_console_message(self.stdout, expected_output)
        self.assert_console_message(self.stderr, "")
        self.session.getBuildTarget.assert_called_once_with(self.target)
        self.session.getTag.assert_called_once_with(self.target_info['dest_tag'])
        self.running_in_bg_mock.assert_not_called()
        self.session.logout.assert_called_once()
        self.watch_tasks_mock.assert_called_once_with(
            self.session, [task_id], quiet=self.options.quiet,
            poll_interval=self.options.poll_interval, topurl=self.options.topurl)

    def test_win_build_help(self):
        self.assert_help(
            handle_win_build,
            """Usage: %s win-build [options] <target> <URL> <VM>
(Specify the --help global option for a list of other help options)

Options:
  -h, --help         show this help message and exit
  --winspec=URL      SCM URL to retrieve the build descriptor from. If not
                     specified, the winspec must be in the root directory of
                     the source repository.
  --patches=URL      SCM URL of a directory containing patches to apply to the
                     sources before building
  --cpus=CPUS        Number of cpus to allocate to the build VM (requires
                     admin access)
  --mem=MEM          Amount of memory (in megabytes) to allocate to the build
                     VM (requires admin access)
  --static-mac       Retain the original MAC address when cloning the VM
  --specfile=URL     SCM URL of a spec file fragment to use to generate
                     wrapper RPMs
  --scratch          Perform a scratch build
  --repo-id=REPO_ID  Use a specific repo
  --skip-tag         Do not attempt to tag package
  --background       Run the build at a lower priority
  --wait             Wait on the build, even if running in the background
  --nowait           Don't wait on build
  --quiet            Do not print the task information
""" % self.progname)
