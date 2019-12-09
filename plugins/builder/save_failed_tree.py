from __future__ import absolute_import

import fnmatch
import os
import sys
import tarfile

import koji
import koji.tasks as tasks
from __main__ import BuildRoot

__all__ = ('SaveFailedTreeTask',)

CONFIG_FILE = '/etc/kojid/plugins/save_failed_tree.conf'
config = None


def omit_paths2(path):
    return any([fnmatch.fnmatch(path, f) for f in config['path_filters']])


def omit_paths3(tarinfo):
    if omit_paths2(tarinfo.name):
        return None
    else:
        return tarinfo


def read_config():
    global config
    cp = koji.read_config_files(CONFIG_FILE)
    config = {
        'path_filters': [],
        'volume': None,
    }
    if cp.has_option('filters', 'paths'):
        config['path_filters'] = cp.get('filters', 'paths').split()
    if cp.has_option('general', 'volume'):
        config['volume'] = cp.get('general', 'volume').strip()


class SaveFailedTreeTask(tasks.BaseTaskHandler):
    Methods = ['saveFailedTree']
    _taskWeight = 3.0

    def handler(self, buildrootID, full=False):
        self.logger.debug("Saving buildroot %d [full=%s]", buildrootID, full)
        read_config()

        brinfo = self.session.getBuildroot(buildrootID)
        if brinfo is None:
            raise koji.GenericError("Nonexistent buildroot: %s" % buildrootID)
        host_id = self.session.host.getHost()['id']
        if brinfo['host_id'] != host_id:
            raise koji.GenericError("Task is run on wrong builder")
        broot = BuildRoot(self.session, self.options, brinfo['id'])
        path = broot.rootdir()

        if full:
            self.logger.debug("Adding buildroot (full): %s" % path)
        else:
            path = os.path.join(path, 'builddir')
            self.logger.debug("Adding buildroot: %s" % path)
        if not os.path.exists(path):
            raise koji.GenericError("Buildroot directory is missing: %s" % path)

        tar_path = os.path.join(self.workdir, 'broot-%s.tar.gz' % buildrootID)
        self.logger.debug("Creating buildroot archive %s", tar_path)
        f = tarfile.open(tar_path, "w:gz")
        if sys.version_info[0] < 3:
            f.add(path, exclude=omit_paths2)
        else:
            f.add(path, filter=omit_paths3)
        f.close()

        self.logger.debug("Uploading %s to hub", tar_path)
        self.uploadFile(tar_path, volume=config['volume'])
        os.unlink(tar_path)
        self.logger.debug("Finished saving buildroot %s", buildrootID)
