import koji
import koji.tasks
import kojihub

from koji.context import context
from koji.plugin import export

koji.tasks.LEGACY_SIGNATURES['dudBuild'] = [
    [['dud_name', 'dud_version', 'arches', 'target', 'pkg_list', 'opts'],
     None, None, (None,)]]
koji.tasks.LEGACY_SIGNATURES['createDudIso'] = [
    [['dud_name', 'dud_version', 'dud_release', 'arch',
      'target_info', 'build_tag', 'repo_info', 'pkg_list', 'opts'],
     None, None, (None,)]]

# /usr/lib/koji-hub-plugins/


@export
def dudBuild(dud_name, dud_version, arches, target, pkg_list, optional_arches=None, scratch=False,
             alldeps=False, scmurl=None, priority=None):
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
        'scratch': scratch,
        'alldeps': alldeps,
        'scmurl': scmurl,
        'optional_arches': optional_arches,
    }

    return kojihub.make_task('dudBuild',
                             [dud_name, dud_version, arches, target, pkg_list, opts],
                             **taskOpts)
