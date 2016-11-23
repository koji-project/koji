import fnmatch
import os
import tarfile
import ConfigParser
import koji.tasks as tasks
from __main__ import BuildRoot

__all__ = ('SaveFailedTreeTask',)

CONFIG_FILE = '/etc/kojid/plugins/save_failed_tree.conf'
config = None

def omit_paths(tarinfo):
    if any([fnmatch.fnmatch(tarinfo.name, f) for f in config['path_filters']]):
        return None
    else:
        return tarinfo

def read_config():
    global config
    cp = ConfigParser.SafeConfigParser()
    cp.read(CONFIG_FILE)
    config = {
        'path_filters': [],
    }
    if cp.has_option('filters', 'paths'):
        config['path_filters'] = cp.get('filters', 'paths').split(':')

class SaveFailedTreeTask(tasks.BaseTaskHandler):
    Methods = ['saveFailedTree']
    _taskWeight = 3.0

    def handler(self, taskID, full=False):
        self.logger.debug("Starting saving buildroots for task %d [full=%s]" % (taskID, full))
        read_config()
        tar_path = os.path.join(self.workdir, 'broots-task-%s.tar.gz' % taskID)
        f = tarfile.open(tar_path, "w:gz")
        for broot in self.session.listBuildroots(taskID=taskID):
            broot = BuildRoot(self.session, self.options, broot['id'])
            path = broot.rootdir()
            if full:
                self.logger.debug("Adding buildroot (full): %s" % path)
            else:
                path = os.path.join(path, 'builddir')
                self.logger.debug("Adding buildroot: %s" % path)
            f.add(path, filter=omit_paths)
        f.close()
        self.logger.debug("Uploading %s to hub." % tar_path)
        self.uploadFile(tar_path)
        os.unlink(tar_path)
        self.logger.debug("Finished saving buildroots for task %d" % taskID)
