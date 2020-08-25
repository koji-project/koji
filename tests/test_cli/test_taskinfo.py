from __future__ import absolute_import, print_function
import collections
import mock
import six
import time
try:
    import unittest2 as unittest
except ImportError:
    import unittest

import koji
from koji_cli.commands import anon_handle_taskinfo, \
    _printTaskInfo, _parseTaskParams

from . import utils


class TestParseTaskParams(utils.CliTestCase):

    # Show long diffs in error output...
    maxDiff = None

    def setUp(self):
        self.session = mock.MagicMock()
        self.build_templ = {
            'package_name': 'bash',
            'version': '4.4.12',
            'release': '5.fc26',
            'epoch': None,
            'nvr': 'bash-4.4.12-5.fc26',
            'build_id': 1,
        }

    def __run_parseTask_test(self, method, params, expect):
        self.session.getTaskRequest.return_value = params
        lines = _parseTaskParams(self.session, method, 1, '/mnt/koji')
        self.assertEquals(lines, expect)

    def test_error_with_param(self):
        params = []
        expect = ['Unable to parse task parameters']
        with mock.patch('koji_cli.commands.logging.getLogger', create=True) as get_logger_mock:
            h = get_logger_mock()
            h.isEnabledFor.return_value = True
            self.__run_parseTask_test('buildSRPMFromCVS', params, expect)
        logger = get_logger_mock()
        logger.isEnabledFor.assert_called_once()
        logger.debug.assert_called_once()

    def test_buildSRPMFrom(self):
        # from CVS case
        params = ['cvs.src.org']
        expect = ["CVS URL: %s" % params[0]]
        self.__run_parseTask_test('buildSRPMFromCVS', params, expect)

        # from SCM case
        params = ['git.github.com']
        expect = ["SCM URL: %s" % params[0]]
        self.__run_parseTask_test('buildSRPMFromSCM', params, expect)

    def test_buildArch(self):
        name = 'TEST'
        topdir = '/mnt/koji'
        self.session.getTag.return_value = {'name': name}
        params = ['path/to/bash-4.4.12-5.fc26.src.rpm', 2, 'x86_64', True, {'repo_id': 1}]
        expect = ["SRPM: %s/work/%s" % (topdir, params[0])]
        expect.append("Build Tag: %s" % name)
        expect.append("Build Arch: %s" % params[2])
        expect.append("SRPM Kept: %r" % params[3])
        expect.append("Options:")
        expect.append("  repo_id: 1")
        self.__run_parseTask_test('buildArch', params, expect)

    def test_tagBuild(self):
        params = [1, 1, False, None, True]
        self.session.getTag.return_value = {'name': 'fedora'}
        self.session.getBuild.return_value = self.build_templ
        expect = ["Destination Tag: fedora"]
        expect.append("Build: bash-4.4.12-5.fc26")
        self.__run_parseTask_test('tagBuild', params, expect)

    def test_buildNotification(self):
        params = [['r1', 'r2'],
                  self.build_templ,
                  {'name': 'fedora'},
                  'fedoraproject.org']
        expect = ["Recipients: %s" % (", ".join(params[0]))]
        expect.append("Build: %s" % self.build_templ['nvr'])
        expect.append("Build Target: %s" % params[2]['name'])
        expect.append("Web URL: %s" % params[3])
        self.__run_parseTask_test('buildNotification', params, expect)

    def test_build(self):
        params = ['path/to/bash-4.4.12-5.fc26.src.rpm',
                  'fedora26-build',
                  {'build-test': True}]
        expect = ["Source: %s" % params[0]]
        expect.append("Build Target: %s" % params[1])
        expect.append("Options:")
        expect.append("  build-test: True")
        self.__run_parseTask_test('build', params, expect)

    def test_maven(self):
        params = ['scm.maven.org', 'maven-target', {'maven-test': True}]
        expect = ["SCM URL: %s" % params[0]]
        expect.append("Build Target: %s" % params[1])
        expect.append("Options:")
        expect.append("  maven-test: True")
        self.__run_parseTask_test('maven', params, expect)

    def test_buildMaven(self):
        params = ['scm.maven.org', {'name': 'maven-tag'}, {'build-test': True}]
        expect = ["SCM URL: %s" % params[0]]
        expect.append("Build Tag: %s" % params[1]['name'])
        expect.append("Options:")
        expect.append("  build-test: True")
        self.__run_parseTask_test('buildMaven', params, expect)

    def test_wrapperRPM(self):
        target = 'test-target'
        params = ['http://path.to/pkg.spec', {'name': 'build-tag'},
                  self.build_templ,
                  {
                    'id': 1,
                    'method': 'wrapperRPM',
                    'arch': 'x86_64',
                    'request': [1, {'name': target}, self.build_templ]
                  },
                  {'wrapRPM-test': True}]
        expect = ["Spec File URL: %s" % params[0]]
        expect.append("Build Tag: %s" % params[1]['name'])
        expect.append("Build: %s" % self.build_templ['nvr'])
        task_info = "wrapperRPM (%s, %s)" % (target, self.build_templ['nvr'])
        expect.append("Task: %s %s" % (params[3]['id'], task_info))
        expect.append("Options:")
        expect.append("  wrapRPM-test: True")
        self.__run_parseTask_test('wrapperRPM', params, expect)

    def test_chainmaven(self):
        params = [{
                    'maven-pkg-1': {'build-opt': '--test'},
                    'maven-pkg-2': {'build-opt': '-O2'},
                  },
                  'build-target',
                  {'chainmaven-test': True}]
        expect = ["Builds:"]
        for pkg, opt in params[0].items():
            expect.append("  %s" % pkg)
            for k, v in opt.items():
                expect.append("    %s: %s" % (k, v))
        expect.append("Build Target: %s" % params[1])
        expect.append("Options:")
        expect.append("  chainmaven-test: True")
        self.__run_parseTask_test('chainmaven', params, expect)

    def test_winbuild(self):
        params = ['vm-builder', 'github.com', 'target',
                  {'winver': 10}]
        expect = ["VM: %s" % params[0]]
        expect.append("SCM URL: %s" % params[1])
        expect.append("Build Target: %s" % params[2])
        expect.append("Options:")
        expect.append("  winver: 10")
        self.__run_parseTask_test('winbuild', params, expect)

    def test_vmExec(self):
        params = ['vm-name',
                  ['x86_64', {'cpu': 'GenuineIntel'}],
                  {'optimize': '-O3'}]
        expect = ["VM: %s" % params[0]]
        expect.append("Exec Params:")
        expect.append("  x86_64")
        expect.append("    cpu: GenuineIntel")
        expect.append("Options:")
        expect.append("  optimize: -O3")
        self.__run_parseTask_test('vmExec', params, expect)

    def test_createXXX(self):
        params = ['name', '1.0', '1', 'x86_64', 'target_info',
                  'build-tag', 'Repo', 'kickstart.ks', {}]
        fields = ['Name', 'Version', 'Release', 'Arch', 'Target Info',
                  'Build Tag', 'Repo', 'Kickstart File']
        template = list()
        for n, v in zip(fields, params):
            template.append("%s: %s" % (n, v))

        for method in ('createLiveCD', 'createAppliance', 'createLiveMedia'):
            params[-1] = {"extra": "test-%s" % method}
            expect = list(template)
            expect.append("Options:")
            expect.append("  extra: test-%s" % method)
            self.__run_parseTask_test(method, params, expect)

    def test_appliance_livecd_livemedia(self):
        params = ['name', '1.0', 'x86_64, ppc64', 'target_info',
                  'kickstart.ks', {}]
        fields = ['Name', 'Version', 'Arches', 'Target', 'Kickstart']
        template = list()
        for n, v in zip(fields, params):
            template.append("%s: %s" % (n, v))

        for method in ('appliance', 'livecd', 'livemedia'):
            params[-1] = {"extra": "test-%s" % method}
            expect = list(template)
            expect.append("Options:")
            expect.append("  extra: test-%s" % method)
            self.__run_parseTask_test(method, params, expect)

    def test_newRepo(self):
        params = [0]
        self.session.getTag.return_value = {'name': 'f26'}
        expect = ['Tag: f26']
        self.__run_parseTask_test('newRepo', params, expect)

    def test_prepRepo(self):
        params = [{'name': 'f26'}]
        expect = ['Tag: f26']
        self.__run_parseTask_test('prepRepo', params, expect)

    def test_createRepo(self):
        params = [1, 'x86_64', {'id': 1, 'create_ts': 0},
                  [{'external_repo_name': 'fedoraproject.net'},
                   {'external_repo_name': 'centos.org'}]]
        expect = ["Repo ID: %i" % params[0]]
        expect.append("Arch: %s" % params[1])
        expect.append("Old Repo ID: %i" % params[2]['id'])
        expect.append("Old Repo Creation: Thu, 01 Jan 1970")
        expect.append("External Repos: %s" % ', '.join(
                      [ext['external_repo_name'] for ext in params[3]]))
        with mock.patch('koji.formatTimeLong',
                        return_value='Thu, 01 Jan 1970'):
            self.__run_parseTask_test('createrepo', params, expect)

    def test_tagNotification(self):
        params = [['kojiadmin', 'user'],   # recipients
                  True,         # successful
                  1,            # dest tag id
                  2,            # src tag id
                  3,            # build id
                  0,            # user id
                  False,        # Ignoresuccess
                  'no error']   # Failure message

        destTag, srcTag = {'name': 'dest-tag-1'}, {'name': 'src-tag-2'}
        user = {'name': 'kojiadmin'}

        self.session.getTag.side_effect = [destTag, srcTag]
        self.session.getBuild.return_value = self.build_templ
        self.session.getUser.return_value = user
        expect = ["Recipients: %s" % ", ".join(params[0])]
        expect.append("Successful?: %s" % (params[1] and 'yes' or 'no'))
        expect.append("Tagged Into: %s" % destTag['name'])
        expect.append("Moved From: %s" % srcTag['name'])
        expect.append("Build: %s" % self.build_templ['nvr'])
        expect.append("Tagged By: %s" % user['name'])
        expect.append("Ignore Success?: %s" % (params[6] and 'yes' or 'no'))
        expect.append("Failure Message: %s" % params[7])
        self.__run_parseTask_test('tagNotification', params, expect)

    def test_dependantTask(self):
        params = [
            [1, 2, 3, 4],        # dependant task ids
            [
              ['buildSRPMFromSCM', ['param1', 'param2'], {'scm': 'github.com'}],
              ['build', ['param1', 'param2'], {'arch': 'x86_64'}],
              ['tagBuild', ['tagname', 'param2'], {}]
            ]
        ]
        expect = ["Dependant Tasks: %s" % ", ".join([str(dep) for dep in params[0]])]
        expect.append("Subtasks:")
        for subtask in params[1]:
            expect.append("  Method: %s" % subtask[0])
            expect.append("  Parameters: %s" % ", ".join(
                          [str(subparam) for subparam in subtask[1]]))
            if subtask[2]:
                expect.append('  Options:')
                for k, v in subtask[2].items():
                    expect.append('    %s: %s' % (k, v))
            expect.append('')
        self.__run_parseTask_test('dependantTask', params, expect)

    def test_chainbuild(self):
        params = [[
                    ['base-grp', 'desktop-grp'],
                    ['base-grp', 'devel-grp'],
                  ],
                  'f26',
                  {'extra': 'f26-pre-release'}]
        expect = ["Build Groups:"]
        for i, grp in enumerate(params[0]):
            expect.append('  %i: %s' % (i+1, ', '.join(grp)))
        expect.append("Build Target: %s" % params[1])
        expect.append("Options:")
        expect.append("  extra: f26-pre-release")
        self.__run_parseTask_test('chainbuild', params, expect)

    def test_waitrepo(self):
        params = ['build-taget', True, ['bash-4.4.12-5.fc26']]
        expect = ["Build Target: %s" % params[0]]
        expect.append("Newer Than: %s" % params[1])
        expect.append("NVRs: %s" % ', '.join(params[2]))
        self.__run_parseTask_test('waitrepo', params, expect)


class TestPrintTaskInfo(utils.CliTestCase):

    # Show long diffs in error output...
    maxDiff = None

    def setUp(self):
        self.host_info = {
            "comment": None,
            "arches": "x86_64",
            "task_load": 0.0,
            "capacity": 2.0,
            "name": "kojibuilder",
            "ready": True,
            "user_id": 3,
            "enabled": True,
            "id": 1,
            "description": None
        }

        self.task_info_templ = {
            'weight': 0.1,
            'parent': None,
            'create_ts': 1000,
            'start_ts': 2000,
            'completion_ts': 3000,
            'state': 2,
            'awaited': None,
            'label': None,
            'priority': 15,
            'channel_id': 2,
            'waiting': False,
            'id': 1,
            'owner': 1,
            'host_id': 1,
            'arch': 'noarch',
            'method': 'newRepo'
        }

        self.tag_info = {
            'maven_support': False,
            'locked': False,
            'name': 'fedora26-build',
            'extra': {},
            'perm': None,
            'id': 2,
            'arches': 'x86_64',
            'maven_include_all': False,
            'perm_id': None
        }

        self.user_info = {
            'status': 0,
            'usertype': 0,
            'id': 1,
            'name': 'kojiadmin',
            'krb_principal': None
        }

    @mock.patch('koji_cli.commands.list_task_output_all_volumes')
    def test_printTaskInfo_create_repo(self, list_task_output_mock):
        session = mock.MagicMock()

        parent = self.task_info_templ.copy()
        parent.update({
            'method': 'newRepo',
            'host_id': None,
        })

        children = self.task_info_templ.copy()
        children.update({
            'id': 2,
            'parent': 1,
            'request': [1, 'x86_64', None],
            'label': 'x86_64',
            'channel_id': 2,
            'host_id': None,
            'method': 'createrepo'
        })

        session.getTaskInfo.side_effect = [parent, children]

        session.listBuildroots.return_value = {}
        session.listBuilds.return_value = {}

        session.getTag.return_value = self.tag_info
        session.getUser.return_value = self.user_info

        session.getTaskRequest.return_value = [1, 'x86_64', None]
        session.getTaskChildren.side_effect = [[children], []]
        task_output = {
            'mergerepos.log': ['DEFAULT'],
            'createrepo.log': ['DEFAULT']
        }
        list_task_output_mock.side_effect = [
            {},
            task_output
        ]
        expected = """\
Task: 1
Type: newRepo
Request Parameters:
  Tag: fedora26-build
Owner: kojiadmin
State: closed
Created: Thu Jan  1 00:16:40 1970
Started: Thu Jan  1 00:33:20 1970
Finished: Thu Jan  1 00:50:00 1970

  Task: 2
  Type: createrepo
  Request Parameters:
    Repo ID: 1
    Arch: x86_64
  Owner: kojiadmin
  State: closed
  Created: Thu Jan  1 00:16:40 1970
  Started: Thu Jan  1 00:33:20 1970
  Finished: Thu Jan  1 00:50:00 1970
  Log Files:
    %s
    %s

""" % tuple('/mnt/koji/work/tasks/2/2/' + k for k in task_output.keys())

        with mock.patch('sys.stdout', new_callable=six.StringIO) as stdout:
            with mock.patch('time.localtime', new=time.gmtime):
                _printTaskInfo(session, 1, '/mnt/koji')
        self.assert_console_message(stdout, expected)

    @mock.patch('koji_cli.commands.list_task_output_all_volumes')
    def test_printTaskInfo_build_srpm(self, list_task_output_mock):
        session = mock.MagicMock()

        parent = self.task_info_templ.copy()
        parent.update({
            'method': 'build',
        })

        child_build = parent.copy()
        child_build.update({
            'id': 2,
            'parent': 1,
            'request': ['path/to/bash.src.rpm', 2, 'x86_64', True, {'repo_id': 1}],
            'method': 'buildArch',
        })

        child_tag = parent.copy()
        child_tag.update({
            'id': 3,
            'parent': 1,
            'request': [1, 1, False, None, True],
            'arch': 'noarch',
            'method': 'tagBuild'
        })

        buildroot_info = [{
            'id': 1,
            'repo_id': 1,
            'tag_name': 'fedora26-build',
            'host_name': 'kojibuilder',
        }]

        build_info = [{
            'package_name': 'bash',
            'version': '4.4.12',
            'release': '5.fc26',
            'epoch': None,
            'nvr': 'bash-4.4.12-5.fc26',
            'build_id': 1,
        }]

        files = {
            'bash-debuginfo-4.4.12-5.fc26.x86_64.rpm': ['DEFAULT'],
            'hw_info.log': ['DEFAULT'],
            'build.log': ['DEFAULT'],
            'bash-4.4.12-5.fc26.src.rpm': ['DEFAULT'],
            'root.log': ['DEFAULT'],
            'state.log': ['DEFAULT'],
            'mock_output.log': ['DEFAULT'],
            'bash-4.4.12-5.fc26.x86_64.rpm': ['DEFAULT'],
            'installed_pkgs.log': ['DEFAULT'],
            'bash-doc-4.4.12-5.fc26.x86_64.rpm': ['DEFAULT']
        }

        # need ordered dict to get same results
        files = collections.OrderedDict(sorted(list(files.items()),
                                        key=lambda t: t[0]))

        list_task_output_mock.side_effect = [[], files, {}]

        session.getTaskInfo.side_effect = [parent, child_build, child_tag]
        session.listBuildroots.side_effect = [[], buildroot_info, []]
        session.listBuilds.side_effect = [build_info, [], []]

        session.getTag.return_value = self.tag_info
        session.getUser.return_value = self.user_info
        session.getBuild.return_value = build_info[0]

        session.getHost.return_value = self.host_info
        session.getTaskRequest.side_effect = [
            ['path/to/bash-4.4.12-5.fc26.src.rpm', 'fedora26-build', {}],
            ['path/to/bash-4.4.12-5.fc26.src.rpm', 2, 'x86_64', True, {'repo_id': 1}],
            [1, 1, False, None, True]
        ]

        session.getTaskChildren.side_effect = [[child_build, child_tag], [], []]

        expected = """\
Task: 1
Type: build
Request Parameters:
  Source: path/to/bash-4.4.12-5.fc26.src.rpm
  Build Target: fedora26-build
Owner: kojiadmin
State: closed
Created: Thu Jan  1 00:16:40 1970
Started: Thu Jan  1 00:33:20 1970
Finished: Thu Jan  1 00:50:00 1970
Host: kojibuilder
Build: bash-4.4.12-5.fc26 (1)

  Task: 2
  Type: buildArch
  Request Parameters:
    SRPM: /mnt/koji/work/path/to/bash-4.4.12-5.fc26.src.rpm
    Build Tag: fedora26-build
    Build Arch: x86_64
    SRPM Kept: True
    Options:
      repo_id: 1
  Owner: kojiadmin
  State: closed
  Created: Thu Jan  1 00:16:40 1970
  Started: Thu Jan  1 00:33:20 1970
  Finished: Thu Jan  1 00:50:00 1970
  Host: kojibuilder
  Buildroots:
    /var/lib/mock/fedora26-build-1-1/
  Log Files:
    /mnt/koji/work/tasks/2/2/build.log
    /mnt/koji/work/tasks/2/2/hw_info.log
    /mnt/koji/work/tasks/2/2/installed_pkgs.log
    /mnt/koji/work/tasks/2/2/mock_output.log
    /mnt/koji/work/tasks/2/2/root.log
    /mnt/koji/work/tasks/2/2/state.log
  Output:
    /mnt/koji/work/tasks/2/2/bash-4.4.12-5.fc26.src.rpm
    /mnt/koji/work/tasks/2/2/bash-4.4.12-5.fc26.x86_64.rpm
    /mnt/koji/work/tasks/2/2/bash-debuginfo-4.4.12-5.fc26.x86_64.rpm
    /mnt/koji/work/tasks/2/2/bash-doc-4.4.12-5.fc26.x86_64.rpm

  Task: 3
  Type: tagBuild
  Request Parameters:
    Destination Tag: fedora26-build
    Build: bash-4.4.12-5.fc26
  Owner: kojiadmin
  State: closed
  Created: Thu Jan  1 00:16:40 1970
  Started: Thu Jan  1 00:33:20 1970
  Finished: Thu Jan  1 00:50:00 1970
  Host: kojibuilder

"""
        with mock.patch('sys.stdout', new_callable=six.StringIO) as stdout:
            with mock.patch('time.localtime', new=time.gmtime):
                _printTaskInfo(session, 1, '/mnt/koji')
        self.assert_console_message(stdout, expected)

    def test_printTaskInfo_no_task(self):
        """Test _printTaskInfo with no task found"""
        session = mock.MagicMock()
        task_id = 1
        session.getTaskInfo.return_value = None

        with self.assertRaises(koji.GenericError) as cm:
            _printTaskInfo(session, task_id, '/')
        self.assertEquals(str(cm.exception), "No such task: %d" % task_id)


class TestTaskInfo(utils.CliTestCase):

    # Show long diffs in error output...
    maxDiff = None

    def setUp(self):
        self.error_format = """Usage: %s taskinfo [options] <task_id> [<task_id> ...]
(Specify the --help global option for a list of other help options)

%s: error: {message}
""" % (self.progname, self.progname)

    @mock.patch('sys.stdout', new_callable=six.StringIO)
    @mock.patch('koji_cli.commands.activate_session')
    @mock.patch('koji_cli.commands.ensure_connection')
    def test_anon_handle_taskinfo(
            self,
            ensure_connection_mock,
            activate_session_mock,
            stdout):
        """Test anon_handle_taskinfo function"""
        session = mock.MagicMock()
        options = mock.MagicMock()

        # Case 1. no task id error
        expected = self.format_error_message(
            "You must specify at least one task ID")

        self.assert_system_exit(
            anon_handle_taskinfo,
            options,
            session,
            [],
            stderr=expected,
            activate_session=None)
        activate_session_mock.assert_not_called()

        # Case 2. show task info
        task_output = """Task: 1
Type: newRepo
Owner: kojiadmin
State: closed
Created: Thu Nov 16 17:34:29 2017
Started: Thu Nov 16 17:51:07 2017
Finished: Thu Nov 16 17:54:55 2017
Host: kojibuilder
"""

        def print_task(*args, **kwargs):
            print(task_output, end='')

        with mock.patch('koji_cli.commands._printTaskInfo', new=print_task):
            anon_handle_taskinfo(options, session, ['1'])
        self.assert_console_message(stdout, task_output)

    def test_anon_handle_taskinfo_help(self):
        self.assert_help(
            anon_handle_taskinfo,
            """Usage: %s taskinfo [options] <task_id> [<task_id> ...]
(Specify the --help global option for a list of other help options)

Options:
  -h, --help     show this help message and exit
  -r, --recurse  Show children of this task as well
  -v, --verbose  Be verbose
""" % self.progname)


if __name__ == '__main__':
    unittest.main()
