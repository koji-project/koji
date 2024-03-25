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
              scratch=False, priority=None, make_prep=False, repos=None, release=None,
              type=None, type_attr=None, result_bundle_name_format=None, use_buildroot_repo=True):
    context.session.assertPerm('image')
    for i in [desc_url, desc_path, profile, release]:
        if i is not None:
            kojihub.convert_value(i, cast=str, check_only=True)
    if repos:
        kojihub.convert_value(repos, cast=list, check_only=True)
    if type_attr:
        kojihub.convert_value(type_attr, cast=list, check_only=True)
    if result_bundle_name_format:
        kojihub.convert_value(result_bundle_name_format, cast=str, check_only=True)
    kojihub.get_build_target(target, strict=True)
    if isinstance(arches, list):
        arches = " ".join(arches)
    arches = koji.parse_arches(arches, to_list=True, strict=True, allow_none=False)
    if isinstance(optional_arches, list):
        optional_arches = " ".join(optional_arches)
    optional_arches = koji.parse_arches(
        optional_arches, to_list=True, strict=True, allow_none=True)
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

    opts = {}
    if scratch:
        opts['scratch'] = True
    if profile:
        opts['profile'] = profile
    if release:
        opts['release'] = release
    if optional_arches:
        opts['optional_arches'] = optional_arches
    if repos:
        opts['repos'] = repos
    if make_prep:
        opts['make_prep'] = True
    if type:
        opts['type'] = type
    if not use_buildroot_repo:
        opts['use_buildroot_repo'] = False
    if type_attr:
        opts['type_attr'] = type_attr
    if result_bundle_name_format:
        opts['result_bundle_name_format'] = result_bundle_name_format
    return kojihub.make_task('kiwiBuild',
                             [target, arches, desc_url, desc_path, opts],
                             **taskOpts)
