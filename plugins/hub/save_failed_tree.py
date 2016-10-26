import sys
import ConfigParser
import koji
from koji.plugin import export

sys.path.insert(0, '/usr/share/koji-hub/')
import kojihub

__all__ = ('saveFailedTree',)

CONFIG_FILE = '/etc/koji-hub/plugins/save_failed_tree.conf'
config = None
allowed_methods = None


@export
def saveFailedTree(taskID, full=False, **opts):
    '''xmlrpc method for creating saveFailedTree task. If arguments are
    invalid, error message is returned. Otherwise task id of newly created
    task is returned.'''
    global config, allowed_methods

    # let it raise errors
    taskID = int(taskID)
    full = bool(full)

    # read configuration only once
    if config is None:
        config = ConfigParser.SafeConfigParser()
        config.read(CONFIG_FILE)
        allowed_methods = config.get('permissions', 'allowed_methods').split()
        if len(allowed_methods) == 1 and allowed_methods[0] == '*':
            allowed_methods = '*'

    task_info = kojihub.Task(taskID).getInfo()
    if task_info['state'] != koji.TASK_STATES['FAILED']:
        return 'Task %s has not failed. Only failed tasks can upload their buildroots.' % taskID
    elif allowed_methods != '*' and task_info['method'] not in allowed_methods:
        return 'Only %s tasks can upload their buildroots (Task %s is %s).' % \
               (', '.join(allowed_methods), task_info['id'], task_info['method'])
    # owner?
    # permissions?

    args = koji.encode_args(taskID, full, **opts)
    taskopts = {
        'assign': task_info['host_id'],
    }
    return kojihub.make_task('saveFailedTree', args, **taskopts)
