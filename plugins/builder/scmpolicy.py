import logging
import re
import subprocess

import six

from koji import ActionNotAllowed, GenericError
from koji.plugin import callback


logger = logging.getLogger('koji.plugins.scmpolicy')


@callback('postSCMCheckout')
def assert_scm_policy(clb_type, *args, **kwargs):
    taskinfo = kwargs['taskinfo']
    session = kwargs['session']
    build_tag = kwargs['build_tag']
    scminfo = kwargs['scminfo']
    srcdir = kwargs['srcdir']
    scratch = kwargs['scratch']

    method = get_task_method(session, taskinfo)

    policy_data = {
        'build_tag': build_tag,
        'method': method,
        'scratch': scratch,
        'branches': get_branches(srcdir)
    }

    # Merge scminfo into data with "scm_" prefix. And "scm*" are changed to "scm_*".
    for k, v in six.iteritems(scminfo):
        policy_data[re.sub(r'^(scm_?)?', 'scm_', k)] = v

    logger.info("Checking SCM policy for task %s", taskinfo['id'])
    logger.debug("Policy data: %r", policy_data)

    # check the policy
    try:
        session.host.assertPolicy('scm', policy_data)
        logger.info("SCM policy check for task %s: PASSED", taskinfo['id'])
    except ActionNotAllowed:
        logger.warning("SCM policy check for task %s: DENIED", taskinfo['id'])
        raise


def get_task_method(session, taskinfo):
    """Get the Task method from taskinfo"""
    method = None
    if isinstance(taskinfo, six.integer_types):
        taskinfo = session.getTaskInfo(taskinfo, strict=True)
    if isinstance(taskinfo, dict):
        method = taskinfo.get('method')
    if method is None:
        raise GenericError("Invalid taskinfo: %s" % taskinfo)
    return method


def get_branches(srcdir):
    """Determine which remote branches contain the current checkout"""
    cmd = ['git', 'branch', '-r', '--contains', 'HEAD']
    proc = subprocess.Popen(cmd, cwd=srcdir, stdout=subprocess.PIPE)
    (out, _) = proc.communicate()
    status = proc.wait()
    if status != 0:
        raise Exception('Error getting branches for git checkout')

    # cut off origin/ prefix
    branches = [b.strip() for b in out.decode().split('\n') if 'origin/HEAD' not in b and b]
    branches = [re.sub('^origin/', '', b) for b in branches]
    return branches
