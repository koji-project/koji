import sys

import koji
from koji.context import context
from koji.plugin import export
sys.path.insert(0, '/usr/share/koji-hub/')
import kojihub  # noqa: E402

__all__ = ('saveFailedTree',)

CONFIG_FILE = '/etc/koji-hub/plugins/save_failed_tree.conf'
config = None
allowed_methods = None


@export
def saveFailedTree(buildrootID, full=False, **opts):
    """Create saveFailedTree task

    If arguments are invalid, error message is returned. Otherwise task id of
    newly created task is returned."""
    global config, allowed_methods

    # let it raise errors
    buildrootID = int(buildrootID)
    full = bool(full)

    # read configuration only once
    if config is None:
        config = koji.read_config_files([(CONFIG_FILE, True)])
        allowed_methods = config.get('permissions', 'allowed_methods').split(',')
        if len(allowed_methods) == 1 and allowed_methods[0] == '*':
            allowed_methods = '*'

    brinfo = kojihub.get_buildroot(buildrootID, strict=True)
    taskID = brinfo['task_id']
    task_info = kojihub.Task(taskID).getInfo()
    if task_info['state'] != koji.TASK_STATES['FAILED']:
        raise koji.PreBuildError(
            "Task %s has not failed. Only failed tasks can upload their buildroots." % taskID)
    elif allowed_methods != '*' and task_info['method'] not in allowed_methods:
        raise koji.PreBuildError(
            "Only %s tasks can upload their buildroots (Task %s is %s)." %
            (', '.join(allowed_methods), task_info['id'], task_info['method']))
    elif task_info["owner"] != context.session.user_id and not context.session.hasPerm('admin'):
        raise koji.ActionNotAllowed("Only owner of failed task or 'admin' can run this task.")
    elif not kojihub.get_host(task_info['host_id'])['enabled']:
        raise koji.PreBuildError("Host is disabled.")

    args = koji.encode_args(buildrootID, full, **opts)
    taskopts = {
        'assign': brinfo['host_id'],
    }
    return kojihub.make_task('saveFailedTree', args, **taskopts)
