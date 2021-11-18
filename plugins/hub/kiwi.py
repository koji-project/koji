import koji
import koji.tasks
import kojihub

from koji.context import context
from koji.plugin import export

koji.tasks.LEGACY_SIGNATURES['kiwiBuild'] = [
    [['target', 'arches', 'desc_url', 'desc_path', 'opts'],
     None, None, (None,)]]
koji.tasks.LEGACY_SIGNATURES['createKiwiImage'] = [
    [['name', 'version', 'release', 'arch',
      'target_info', 'build_tag', 'repo_info', 'desc_url', 'desc_path', 'opts'],
     None, None, (None,)]]


@export
def kiwiBuild(target, arches, desc_url, desc_path, optional_arches=None, profile=None,
              scratch=False, priority=None):
    context.session.assertPerm('image')
    taskOpts = {
        'channel': 'image',
    }
    if priority:
        if priority < 0:
            if not context.session.hasPerm('admin'):
                raise koji.ActionNotAllowed(
                    'only admins may create high-priority tasks')
        taskOpts['priority'] = koji.PRIO_DEFAULT + priority

    opts = {
        'optional_arches': optional_arches,
        'profile': profile,
        'scratch': scratch,
    }
    return kojihub.make_task('kiwiBuild',
                             [target, arches, desc_url, desc_path, opts],
                             **taskOpts)
