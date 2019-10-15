from __future__ import absolute_import
import copy
import mock
try:
    import unittest2 as unittest
except ImportError:
    import unittest

import six.moves.configparser

# inject builder data
from tests.test_builder.loadkojid import kojid
import __main__
__main__.BuildRoot = kojid.BuildRoot

import koji
import runroot

def mock_open():
    """Return the right patch decorator for open"""
    if six.PY2:
        return mock.patch('__builtin__.open')
    else:
        return mock.patch('builtins.open')


if six.PY2:
    CONFIG_PARSER = 'six.moves.configparser.SafeConfigParser'
else:
    CONFIG_PARSER = 'six.moves.configparser.ConfigParser'


CONFIG1 = {
        'paths': {
            'default_mounts': '/mnt/archive,/mnt/workdir',
            'safe_roots': '/mnt/workdir/tmp',
            'path_subs':
            '/mnt/archive/prehistory/,/mnt/prehistoric_disk/archive/prehistory',
        },
        'path0': {
            'mountpoint': '/mnt/archive',
            'path': 'archive.org:/vol/archive',
            'fstype': 'nfs',
            'options': 'ro,hard,intr,nosuid,nodev,noatime,tcp',
        }}


CONFIG2 = {
        'paths': {
            'default_mounts': '/mnt/archive,/mnt/workdir',
            'safe_roots': '/mnt/workdir/tmp',
            'path_subs':
                '\n'
                '/mnt/archive/prehistory/,/mnt/prehistoric_disk/archive/prehistory\n'
                '/mnt/archve/workdir,/mnt/workdir\n',
        },
        'path0': {
            'mountpoint': '/mnt/archive',
            'path': 'archive.org:/vol/archive',
            'fstype': 'nfs',
            'options': 'ro,hard,intr,nosuid,nodev,noatime,tcp',
        },
        'path1': {
            'mountpoint': '/mnt/workdir',
            'path': 'archive.org:/vol/workdir',
            'fstype': 'nfs',
            'options': 'ro,hard,intr,nosuid,nodev,noatime,tcp',
        },
        'path2': {
            'mountpoint': '/mnt/prehistoric_disk',
            'path': 'archive.org:/vol/prehistoric_disk',
            'fstype': 'nfs',
            'options': 'ro,hard,intr,nosuid,nodev,noatime,tcp',
        }}


class FakeConfigParser(object):

    def __init__(self, config=None):
        if config is None:
            self.CONFIG = copy.deepcopy(CONFIG1)
        else:
            self.CONFIG = copy.deepcopy(config)

    def read(self, path):
        return

    def sections(self):
        return list(self.CONFIG.keys())

    def has_option(self, section, key):
        return section in self.CONFIG and key in self.CONFIG[section]

    def has_section(self, section):
        return section in self.CONFIG

    def get(self, section, key):
        try:
            return self.CONFIG[section][key]
        except KeyError:
            raise six.moves.configparser.NoOptionError(section, key)


class TestRunrootConfig(unittest.TestCase):
    @mock.patch(CONFIG_PARSER)
    def test_bad_config_paths0(self, config_parser):
        cp = FakeConfigParser()
        del cp.CONFIG['path0']['mountpoint']
        config_parser.return_value = cp
        session = mock.MagicMock()
        options = mock.MagicMock()
        options.workdir = '/tmp/nonexistentdirectory'
        with self.assertRaises(koji.GenericError) as cm:
            runroot.RunRootTask(123, 'runroot', {}, session, options)
        self.assertEqual(cm.exception.args[0],
            "bad config: missing options in path0 section")

    @mock.patch(CONFIG_PARSER)
    def test_bad_config_absolute_path(self, config_parser):
        cp = FakeConfigParser()
        cp.CONFIG['paths']['default_mounts'] = ''
        config_parser.return_value = cp
        session = mock.MagicMock()
        options = mock.MagicMock()
        options.workdir = '/tmp/nonexistentdirectory'
        with self.assertRaises(koji.GenericError) as cm:
            runroot.RunRootTask(123, 'runroot', {}, session, options)
        self.assertEqual(cm.exception.args[0],
            "bad config: all paths (default_mounts, safe_roots, path_subs) needs to be absolute: ")

    @mock.patch(CONFIG_PARSER)
    def test_valid_config(self, config_parser):
        config_parser.return_value = FakeConfigParser()
        session = mock.MagicMock()
        options = mock.MagicMock()
        options.workdir = '/tmp/nonexistentdirectory'
        runroot.RunRootTask(123, 'runroot', {}, session, options)

    @mock.patch(CONFIG_PARSER)
    def test_valid_config_alt(self, config_parser):
        config_parser.return_value = FakeConfigParser(CONFIG2)
        session = mock.MagicMock()
        options = mock.MagicMock()
        options.workdir = '/tmp/nonexistentdirectory'
        runroot.RunRootTask(123, 'runroot', {}, session, options)

    @mock.patch(CONFIG_PARSER)
    def test_pathnum_gaps(self, config_parser):
        session = mock.MagicMock()
        options = mock.MagicMock()
        options.workdir = '/tmp/nonexistentdirectory'
        config = CONFIG2.copy()
        config_parser.return_value = FakeConfigParser(config)
        task1 = runroot.RunRootTask(123, 'runroot', {}, session, options)
        # adjust the path numbers (but preserving order) and do it again
        config = CONFIG2.copy()
        config['path99'] = config['path1']
        config['path999'] = config['path2']
        del config['path1']
        del config['path2']
        config_parser.return_value = FakeConfigParser(config)
        task2 = runroot.RunRootTask(123, 'runroot', {}, session, options)
        # resulting processed config should be the same
        self.assertEqual(task1.config, task2.config)
        paths = list([CONFIG2[k] for k in ('path0', 'path1', 'path2')])
        self.assertEqual(task2.config['paths'], paths)

    @mock.patch(CONFIG_PARSER)
    def test_bad_path_sub(self, config_parser):
        session = mock.MagicMock()
        options = mock.MagicMock()
        options.workdir = '/tmp/nonexistentdirectory'
        config = copy.deepcopy(CONFIG2)
        config['paths']['path_subs'] += 'incorrect:format'
        config_parser.return_value = FakeConfigParser(config)
        with self.assertRaises(koji.GenericError):
            runroot.RunRootTask(123, 'runroot', {}, session, options)


class TestMounts(unittest.TestCase):
    @mock.patch(CONFIG_PARSER)
    def setUp(self, config_parser):
        config_parser.return_value = FakeConfigParser()
        self.session = mock.MagicMock()
        options = mock.MagicMock()
        options.workdir = '/tmp/nonexistentdirectory'
        self.t = runroot.RunRootTask(123, 'runroot', {}, self.session, options)

    def test_get_path_params(self):
        # non-existent item
        with self.assertRaises(koji.GenericError):
            self.t._get_path_params('nonexistent_dir')

        # valid item
        self.assertEqual(self.t._get_path_params('/mnt/archive', 'rw'),
            ('archive.org:/vol/archive/', '/mnt/archive', 'nfs', 'rw,hard,intr,nosuid,nodev,noatime,tcp'))

    @mock_open()
    @mock.patch('os.path.isdir')
    @mock.patch('runroot.log_output')
    def test_do_mounts(self, log_output, is_dir, open_mock):
        log_output.return_value = 0 # successful mount

        # no mounts, don't do anything
        self.t.logger = mock.MagicMock()
        self.t.do_mounts('rootdir', [])
        self.t.logger.assert_not_called()

        # mountpoint has no absolute_path
        with self.assertRaises(koji.GenericError) as cm:
            self.t.do_mounts('rootdir', [('nfs:nfs', 'relative_path', 'nfs', '')])
        self.assertEqual(cm.exception.args[0],
                "invalid mount point: relative_path")

        # cover missing opts
        self.t.do_mounts('rootdir', [('nfs:nfs', '/mnt/archive', 'nfs', None)])

        # standard
        log_output.reset_mock()
        mounts = [self.t._get_path_params('/mnt/archive')]
        self.t.do_mounts('rootdir', mounts)
        log_output.assert_called_once_with(self.session, 'mount',
                ['mount', '-t', 'nfs', '-o', 'ro,hard,intr,nosuid,nodev,noatime,tcp',
                'archive.org:/vol/archive/', 'rootdir/mnt/archive'],
                '/tmp/nonexistentdirectory/tasks/123/123/do_mounts.log',
                'tasks/123/123', append=True, logerror=True)

        # mount command failed
        log_output.reset_mock()
        log_output.return_value = 1
        #self.t.undo_mounts = mock.MagicMock()
        mounts = [self.t._get_path_params('/mnt/archive')]
        with self.assertRaises(koji.GenericError) as cm:
            self.t.do_mounts('rootdir', mounts)
        self.assertEqual(cm.exception.args[0],
            'Unable to mount rootdir/mnt/archive: mount -t nfs -o'
            ' ro,hard,intr,nosuid,nodev,noatime,tcp archive.org:/vol/archive/'
            ' rootdir/mnt/archive was killed by signal 1')

        # bind ok
        log_output.return_value = 0
        log_output.reset_mock()
        mount = list(self.t._get_path_params('/mnt/archive'))
        mount[3] += ',bind'
        is_dir.return_value = True
        self.t.do_mounts('rootdir', [mount])
        log_output.assert_called_once_with(self.session, 'mount',
                ['mount', '-t', 'none', '-o', 'ro,hard,intr,nosuid,nodev,noatime,tcp,bind',
                'archive.org:/vol/archive/', 'rootdir/mnt/archive'],
                '/tmp/nonexistentdirectory/tasks/123/123/do_mounts.log',
                'tasks/123/123', append=True, logerror=True)

        # bind - target doesn't exist
        mount = list(self.t._get_path_params('/mnt/archive'))
        mount[3] += ',bind'
        is_dir.return_value = False
        with self.assertRaises(koji.GenericError) as cm:
            self.t.do_mounts('rootdir', [mount])
        self.assertEqual(cm.exception.args[0],
            "No such directory or mount: archive.org:/vol/archive/")

        # bg option forbidden
        log_output.reset_mock()
        mount = list(self.t._get_path_params('/mnt/archive'))
        mount[3] += ',bg'
        is_dir.return_value = False
        with self.assertRaises(koji.GenericError) as cm:
            self.t.do_mounts('rootdir', [mount])
        self.assertEqual(cm.exception.args[0],
            "bad config: background mount not allowed")

    def test_do_extra_mounts(self):
        self.t.do_mounts = mock.MagicMock()
        self.t._get_path_params = mock.MagicMock()
        self.t._get_path_params.return_value = 'path_params'

        # no mounts
        self.t.do_extra_mounts('rootdir', [])
        self.t.do_mounts.assert_called_once_with('rootdir', [])

        # safe mount
        self.t.do_mounts.reset_mock()
        self.t.do_extra_mounts('rootdir', ['/mnt/workdir/tmp/xyz'])
        self.t.do_mounts.assert_called_once_with('rootdir', ['path_params'])

        # unsafe mount
        self.t.do_mounts.reset_mock()
        with self.assertRaises(koji.GenericError):
            self.t.do_extra_mounts('rootdir', ['unsafe'])
        self.t.do_mounts.assert_not_called()

        # hackish mount
        self.t.do_mounts.reset_mock()
        with self.assertRaises(koji.GenericError):
            self.t.do_extra_mounts('rootdir', ['/mnt/workdir/tmp/../xyz'])
        self.t.do_mounts.assert_not_called()


    @mock_open()
    @mock.patch('runroot.scan_mounts')
    @mock.patch('os.unlink')
    @mock.patch('subprocess.Popen')
    @mock.patch('os.path.exists')
    def test_undo_mounts(self, path_exists, popen, os_unlink, scan_mounts, m_open):
        self.t.logger = mock.MagicMock()
        scan_mounts.return_value = ['mount_1', 'mount_2']

        # correct
        popen.return_value.wait.return_value = 0
        path_exists.return_value = True
        m_open.return_value.__enter__.return_value.readlines.return_value = ['mountpoint']
        self.t.undo_mounts('rootdir')
        self.t.logger.assert_has_calls([
            mock.call.debug('Unmounting runroot mounts'),
            mock.call.info("Unmounting (runroot): ['mountpoint', 'mount_2', 'mount_1']"),
        ])
        os_unlink.assert_called_once_with('rootdir/tmp/runroot_mounts')

        # fail
        os_unlink.reset_mock()
        popen.return_value.wait.return_value = 1
        popen.return_value.stdout.read.return_value = ''
        popen.return_value.stderr.read.return_value = 'error'
        path_exists.return_value = True
        with self.assertRaises(koji.GenericError) as cm:
            self.t.undo_mounts('rootdir')
        self.assertEqual(cm.exception.args[0],
            'Unable to unmount: mountpoint: error, mount_2: error, mount_1: error')

        os_unlink.assert_not_called()

class TestHandler(unittest.TestCase):
    @mock.patch(CONFIG_PARSER)
    def setUp(self, config_parser):
        self.session = mock.MagicMock()
        self.br = mock.MagicMock()
        self.br.mock.return_value = 0
        self.br.id = 678
        self.br.rootdir.return_value = '/rootdir'
        runroot.BuildRoot = mock.MagicMock()
        runroot.BuildRoot.return_value = self.br

        options = mock.MagicMock()
        options.workdir = '/tmp/nonexistentdirectory'
        #options.topurl = 'http://topurl'
        options.topurls = None
        self.t = runroot.RunRootTask(123, 'runroot', {}, self.session, options)
        self.t.config['default_mounts'] = ['default_mount']
        self.t.config['internal_dev_setup'] = None
        self.t.do_mounts = mock.MagicMock()
        self.t.do_extra_mounts = mock.MagicMock()
        self.t.undo_mounts = mock.MagicMock()
        self.t.uploadFile = mock.MagicMock()
        self.t._get_path_params = mock.MagicMock()
        self.t._get_path_params.side_effect = lambda x: x

    def tearDown(self):
        runroot.BuildRoot = kojid.BuildRoot

    @mock.patch('platform.uname')
    @mock.patch('os.system')
    def test_handler_simple(self, os_system, platform_uname):
        platform_uname.return_value = ('system', 'node', 'release', 'version', 'machine', 'arch')
        self.session.getBuildConfig.return_value = {
            'id': 456,
            'name': 'tag_name',
            'arches': 'noarch x86_64',
            'extra': {},
        }
        self.session.repoInfo.return_value = {
            'id': 1,
            'create_event': 123,
            'state': koji.REPO_STATES['READY'],
            'tag_id': 456,
            'tag_name': 'tag_name',
        }
        self.session.getRepo.return_value = {
            'id': 1,
        }
        self.session.host.getHost.return_value = {'arches': 'x86_64'}
        self.t.handler('tag_name', 'noarch', 'command', weight=10.0,
                repo_id=1, packages=['rpm_a', 'rpm_b'], new_chroot=True,
                mounts=['/mnt/a'], skip_setarch=True,
                upload_logs=['log_1', 'log_2'])

        # calls
        self.session.host.setTaskWeight.assert_called_once_with(self.t.id, 10.0)
        self.session.host.getHost.assert_called_once_with()
        self.session.getBuildConfig.assert_called_once_with('tag_name')
        self.session.repoInfo.assert_called_once_with(1, strict=True)
        self.session.host.subtask.assert_not_called()
        runroot.BuildRoot.assert_called_once_with(self.session, self.t.options,
                'tag_name', 'x86_64', self.t.id, repo_id=1, setup_dns=True,
                internal_dev_setup=None)
        os_system.assert_called_once()
        self.session.host.setBuildRootState.assert_called_once_with(678, 'BUILDING')
        self.br.mock.assert_has_calls([
            mock.call(['--install', 'rpm_a', 'rpm_b']),
            mock.call(['chroot', '--new-chroot', '--arch', 'arch', '--', '/bin/sh', '-c', '{ command; } < /dev/null 2>&1 | /usr/bin/tee /builddir/runroot.log; exit ${PIPESTATUS[0]}']),
        ])
        self.session.host.updateBuildRootList.assert_called_once_with(678, self.br.getPackageList())
        self.t.do_mounts.assert_called_once_with('/rootdir', ['default_mount'])
        self.t.do_extra_mounts.assert_called_once_with('/rootdir', ['/mnt/a'])
        self.t.uploadFile.assert_has_calls([
            mock.call('/rootdir/builddir/runroot.log'),
            mock.call('/rootdir/log_1'),
            mock.call('/rootdir/log_2'),
        ])
