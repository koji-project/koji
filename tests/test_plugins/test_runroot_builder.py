import unittest
import mock
import ConfigParser

# inject builder data
from tests.test_builder.loadkojid import kojid
import __main__
__main__.BuildRoot = kojid.BuildRoot

import koji
from runroot import RunRootTask

class FakeConfigParser(object):
    def __init__(self):
        self.CONFIG = {
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
            },
        }

    def read(self, path):
        return

    def has_option(self, section, key):
        return section in self.CONFIG and key in self.CONFIG[section]

    def has_section(self, section):
        return section in self.CONFIG

    def get(self, section, key):
        try:
            return self.CONFIG[section][key]
        except KeyError:
            raise ConfigParser.NoOptionError(section, key)


class TestRunrootConfig(unittest.TestCase):
    @mock.patch('ConfigParser.SafeConfigParser')
    def test_bad_config_paths0(self, safe_config_parser):
        cp = FakeConfigParser()
        del cp.CONFIG['path0']['mountpoint']
        safe_config_parser.return_value = cp
        session = mock.MagicMock()
        options = mock.MagicMock()
        options.workdir = '/tmp/nonexistentdirectory'
        with self.assertRaises(koji.GenericError) as cm:
            RunRootTask(123, 'runroot', {}, session, options)
        self.assertEqual(cm.exception.message,
            "bad config: missing options in path0 section")

    @mock.patch('ConfigParser.SafeConfigParser')
    def test_bad_config_absolute_path(self, safe_config_parser):
        cp = FakeConfigParser()
        cp.CONFIG['paths']['default_mounts'] = ''
        safe_config_parser.return_value = cp
        session = mock.MagicMock()
        options = mock.MagicMock()
        options.workdir = '/tmp/nonexistentdirectory'
        with self.assertRaises(koji.GenericError) as cm:
            RunRootTask(123, 'runroot', {}, session, options)
        self.assertEqual(cm.exception.message,
            "bad config: all paths (default_mounts, safe_roots, path_subs) needs to be absolute: ")

    @mock.patch('ConfigParser.SafeConfigParser')
    def test_valid_config(self, safe_config_parser):
        safe_config_parser.return_value = FakeConfigParser()
        session = mock.MagicMock()
        options = mock.MagicMock()
        options.workdir = '/tmp/nonexistentdirectory'
        RunRootTask(123, 'runroot', {}, session, options)

class TestMounts(unittest.TestCase):
    @mock.patch('ConfigParser.SafeConfigParser')
    def setUp(self, safe_config_parser):
        safe_config_parser.return_value = FakeConfigParser()
        self.session = mock.MagicMock()
        options = mock.MagicMock()
        options.workdir = '/tmp/nonexistentdirectory'
        self.t = RunRootTask(123, 'runroot', {}, self.session, options)

    def test_get_path_params(self):
        # non-existent item
        with self.assertRaises(koji.GenericError):
            self.t._get_path_params('nonexistent_dir')

        # valid item
        self.assertEqual(self.t._get_path_params('/mnt/archive', 'rw'),
            ('archive.org:/vol/archive/', '/mnt/archive', 'nfs', 'rw,hard,intr,nosuid,nodev,noatime,tcp'))

    @mock.patch('os.path.isdir')
    @mock.patch('runroot.open')
    @mock.patch('runroot.log_output')
    def test_do_mounts(self, log_output, file_mock, is_dir):
        log_output.return_value = 0 # successful mount

        # no mounts, don't do anything
        self.t.logger = mock.MagicMock()
        self.t.do_mounts('rootdir', [])
        self.t.logger.assert_not_called()

        # mountpoint has no absolute_path
        with self.assertRaises(koji.GenericError) as cm:
            self.t.do_mounts('rootdir', [('nfs:nfs', 'relative_path', 'nfs', '')])
        self.assertEqual(cm.exception.message,
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
        self.assertEqual(cm.exception.message,
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
        self.assertEqual(cm.exception.message,
            "No such directory or mount: archive.org:/vol/archive/")

        # bg option forbidden
        log_output.reset_mock()
        mount = list(self.t._get_path_params('/mnt/archive'))
        mount[3] += ',bg'
        is_dir.return_value = False
        with self.assertRaises(koji.GenericError) as cm:
            self.t.do_mounts('rootdir', [mount])
        self.assertEqual(cm.exception.message,
            "bad config: background mount not allowed")

    @mock.patch('os.unlink')
    @mock.patch('commands.getstatusoutput')
    @mock.patch('os.path.exists')
    def test_undo_mounts(self, path_exists, getstatusoutput, os_unlink):
        self.t.logger = mock.MagicMock()

        # correct
        getstatusoutput.return_value = (0, 'ok')
        path_exists.return_value = True
        with mock.patch('runroot.open', mock.mock_open(read_data = 'mountpoint')):
            self.t.undo_mounts('rootdir')
        self.t.logger.assert_has_calls([
            mock.call.debug('Unmounting runroot mounts'),
            mock.call.info("Unmounting (runroot): ['mountpoint']"),
        ])
        os_unlink.assert_called_once_with('rootdir/tmp/runroot_mounts')

        # fail
        os_unlink.reset_mock()
        getstatusoutput.return_value = (1, 'error')
        path_exists.return_value = True
        with mock.patch('runroot.open', mock.mock_open(read_data = 'mountpoint')):
            with self.assertRaises(koji.GenericError) as cm:
                self.t.undo_mounts('rootdir')
            self.assertEqual(cm.exception.message, 'Unable to unmount: mountpoint: error')
        os_unlink.assert_not_called()

class TestHandler(unittest.TestCase):
    # TODO
    pass
