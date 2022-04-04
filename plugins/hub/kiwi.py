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
              scratch=False, priority=None, make_prep=False, repos=None, release=None):
    context.session.assertPerm('image')
    for i in [desc_url, desc_path, profile, release]:
        if i is not None:
            kojihub.check_value_type(i, cast=str)
    if repos:
        kojihub.check_value_type(repos, cast=list)
    kojihub.get_build_targets(target, strict=True)
    arches = koji.parse_arches(arches, strict=True, allow_none=False)
    optional_arches = koji.parse_arches(optional_arches, strict=True, allow_none=True)
    taskOpts = {
        'channel': 'image',
    }
    if priority:
        priority = kojihub.convert_value(priority, cast=int)
        if priority < 0:
            if not context.session.hasPerm('admin'):
                raise koji.ActionNotAllowed(
                    'only admins may create high-priority tasks')
        taskOpts['priority'] = koji.PRIO_DEFAULT + priority

    opts = {
        'optional_arches': optional_arches,
        'profile': profile,
        'scratch': bool(scratch),
        'release': release,
        'repos': repos or [],
        'make_prep': bool(make_prep),
    }
    return kojihub.make_task('kiwiBuild',
                             [target, arches, desc_url, desc_path, opts],
                             **taskOpts)
