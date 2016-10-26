import koji
from koji.plugin import export

import sys
sys.path.insert(0, '/usr/share/koji-hub/')
import kojihub

__all__ = ('saveFailedTree',)

@export
def saveFailedTree(taskID, full=False, **opts):
    # let it raise errors
    taskID = int(taskID)
    full = bool(full)

    task_info = kojihub.Task(taskID).getInfo()
    if task_info['state'] != koji.TASK_STATES['FAILED']:
        return 'Task %s has not failed.' % taskID
    elif task_info['method'] != 'buildArch':
        # TODO: allowed tasks could be defined in plugin hub config
        return 'Only buildArch tasks can upload buildroot (Task %(id)s is %(method)s).' % task_info
    # owner?
    # permissions?

    args = koji.encode_args(taskID, full, **opts)
    taskopts = {
        'assign': task_info['host_id'],
    }
    return kojihub.make_task('saveFailedTree', args, **taskopts)
