# Task definitions used by various Koji daemons

# Copyright (c) 2010-2014 Red Hat, Inc.
#
#    Koji is free software; you can redistribute it and/or
#    modify it under the terms of the GNU Lesser General Public
#    License as published by the Free Software Foundation;
#    version 2.1 of the License.
#
#    This software is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
#    Lesser General Public License for more details.
#
#    You should have received a copy of the GNU Lesser General Public
#    License along with this software; if not, write to the Free Software
#    Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301  USA

# Authors:
#       Mike McLean <mikem@redhat.com>
#       Mike Bonnet <mikeb@redhat.com>
from __future__ import absolute_import

import logging
import os
import pprint
import random
import signal
import time

import six.moves.xmlrpc_client
from six.moves import range

import koji
import koji.plugin
import koji.util


def scan_mounts(topdir):
    """Search path for mountpoints"""
    mplist = []
    topdir = os.path.normpath(topdir)
    fo = open('/proc/mounts', 'r')
    logger = logging.getLogger("koji.build")
    for line in fo.readlines():
        path = line.split()[1]
        if path.startswith(topdir):
            if path.endswith(r'\040(deleted)'):
                path = path[:-13]
                logger.warning('Found deleted mountpoint: %s' % path)
            mplist.append(path)
    fo.close()
    # reverse sort so deeper dirs come first
    mplist.sort(reverse=True)
    return mplist


def umount_all(topdir):
    "Unmount every mount under topdir"
    logger = logging.getLogger("koji.build")
    for path in scan_mounts(topdir):
        logger.debug('Unmounting %s' % path)
        cmd = ['umount', '-l', path]
        rv = os.spawnvp(os.P_WAIT, cmd[0], cmd)
        if rv != 0:
            raise koji.GenericError('umount failed (exit code %r) for %s' % (rv, path))
    # check mounts again
    remain = scan_mounts(topdir)
    if remain:
        raise koji.GenericError("Unmounting incomplete: %r" % remain)


def safe_rmtree(path, unmount=False, strict=True):
    logger = logging.getLogger("koji.build")
    if unmount:
        umount_all(path)
    if os.path.isfile(path) or os.path.islink(path):
        logger.debug("Removing: %s" % path)
        try:
            os.remove(path)
        except Exception:
            if strict:
                raise
            else:
                logger.warning("Error removing: %s", exc_info=True)
                return 1
        return 0
    if not os.path.exists(path):
        logger.debug("No such path: %s" % path)
        return 0

    logger.debug('Scrubbing files in %s' % path)
    try:
        koji.util.rmtree(path)
    except Exception:
        logger.warning('file removal failed for %s' % path)
        if strict:
            raise
        return 1
    return 0


class ServerExit(Exception):
    """Raised to shutdown the server"""
    pass


class ServerRestart(Exception):
    """Raised to restart the server"""
    pass


class RefuseTask(Exception):
    """Raise to task handler to refuse a task"""
    pass


def parse_task_params(method, params):
    """Parse task params into a dictionary

    New tasks should already be dictionaries
    """

    # check for new style
    if len(params) == 1 and isinstance(params[0], dict) and '__method__' in params[0]:
        ret = params[0].copy()
        del ret['__method__']
        return ret

    # otherwise sort out the legacy signatures
    args, kwargs = koji.decode_args(*params)

    if method not in LEGACY_SIGNATURES:
        raise TypeError("No legacy signature for %s" % method)

    err = None
    for argspec in LEGACY_SIGNATURES[method]:
        try:
            params = koji.util.apply_argspec(argspec, args, kwargs)
            break
        except koji.ParameterError as e:
            if not err:
                err = e.args[0]
    else:
        raise koji.ParameterError("Invalid signature for %s: %s" % (method, err))

    return params


LEGACY_SIGNATURES = {
    # key is method name, value is list of possible signatures
    # signatures are like getargspec -- args, varargs, keywords, defaults
    'chainbuild': [
        [['srcs', 'target', 'opts'], None, None, (None,)],
    ],
    'waitrepo': [
        [['tag', 'newer_than', 'nvrs', 'min_event'], None, None, (None, None, None)],
        # [['tag', 'newer_than', 'nvrs'], None, None, (None, None)],
    ],
    'createLiveMedia': [
        [['name', 'version', 'release', 'arch', 'target_info', 'build_tag', 'repo_info', 'ksfile',
          'opts'],
         None, None, (None,)],
    ],
    'createAppliance': [
        [['name', 'version', 'release', 'arch', 'target_info', 'build_tag', 'repo_info', 'ksfile',
          'opts'],
         None, None, (None,)],
    ],
    'livecd': [
        [['name', 'version', 'arch', 'target', 'ksfile', 'opts'], None, None, (None,)],
    ],
    'buildNotification': [
        [['recipients', 'build', 'target', 'weburl'], None, None, None],
    ],
    'buildMaven': [
        [['url', 'build_tag', 'opts'], None, None, (None,)],
    ],
    'build': [
        [['src', 'target', 'opts'], None, None, (None,)],
    ],
    'buildSRPMFromSCM': [
        [['url', 'build_tag', 'opts'], None, None, (None,)],
    ],
    'rebuildSRPM': [
        [['srpm', 'build_tag', 'opts'], None, None, (None,)],
    ],
    'createrepo': [
        [['repo_id', 'arch', 'oldrepo'], None, None, None],
    ],
    'livemedia': [
        [['name', 'version', 'arches', 'target', 'ksfile', 'opts'], None, None, (None,)],
    ],
    'indirectionimage': [
        [['opts'], None, None, None],
    ],
    'wrapperRPM': [
        [['spec_url', 'build_target', 'build', 'task', 'opts'], None, None, (None,)],
    ],
    'createLiveCD': [
        [['name', 'version', 'release', 'arch', 'target_info', 'build_tag', 'repo_info', 'ksfile',
          'opts'],
         None, None, (None,)],
    ],
    'appliance': [
        [['name', 'version', 'arch', 'target', 'ksfile', 'opts'], None, None, (None,)],
    ],
    'image': [
        [['name', 'version', 'arches', 'target', 'inst_tree', 'opts'], None, None, (None,)],
    ],
    'tagBuild': [
        [['tag_id', 'build_id', 'force', 'fromtag', 'ignore_success'],
         None, None, (False, None, False)],
    ],
    'chainmaven': [
        [['builds', 'target', 'opts'], None, None, (None,)],
    ],
    'newRepo': [
        [['tag', 'event', 'src', 'debuginfo', 'separate_src'],
         None, None, (None, False, False, False)],
        [['tag', 'event', 'src', 'debuginfo', 'separate_src', 'opts'],
         None, None, (None, None, None, None, None)],
    ],
    'createImage': [
        [['name', 'version', 'release', 'arch', 'target_info', 'build_tag', 'repo_info',
          'inst_tree', 'opts'],
         None, None, (None,)],
    ],
    'tagNotification': [
        [['recipients', 'is_successful', 'tag_info', 'from_info', 'build_info', 'user_info',
          'ignore_success', 'failure_msg'],
         None, None, (None, '')],
    ],
    'buildArch': [
        [['pkg', 'root', 'arch', 'keep_srpm', 'opts'], None, None, (None,)],
    ],
    'maven': [
        [['url', 'target', 'opts'], None, None, (None,)],
    ],
    'waittest': [
        [['count', 'seconds'], None, None, (10,)],
    ],
    'default': [
        [[], 'args', 'opts', None],
    ],
    'shutdown': [
        [[], None, None, None],
    ],
    'restartVerify': [
        [['task_id', 'host'], None, None, None],
    ],
    'someMethod': [
        [[], 'args', None, None],
    ],
    'restart': [
        [['host'], None, None, None],
    ],
    'fork': [
        [['n', 'm'], None, None, (5, 37)],
    ],
    'sleep': [
        [['n'], None, None, None],
    ],
    'dependantTask': [
        [['wait_list', 'task_list'], None, None, None],
    ],
    'subtask': [
        [['n'], None, None, (4,)],
    ],
    'restartHosts': [
        [['options'], None, None, (None,)],
    ],
    'runroot': [
        [['root', 'arch', 'command', 'keep', 'packages', 'mounts', 'repo_id', 'skip_setarch',
          'weight', 'upload_logs', 'new_chroot'],
         None, None, (False, [], [], None, False, None, None, False)],
    ],
    'distRepo': [
        [['tag', 'repo_id', 'keys', 'task_opts'], None, None, None],
    ],
    'createdistrepo': [
        [['tag', 'repo_id', 'arch', 'keys', 'opts'], None, None, None],
    ],
    'saveFailedTree': [
        [['buildrootID', 'full'], None, None, (False,)],
    ],
    'vmExec': [
        [['name', 'task_info', 'opts'], None, None, None],
    ],
    'winbuild': [
        [['name', 'source_url', 'target', 'opts'], None, None, None],
    ],
}


class BaseTaskHandler(object):
    """The base class for task handlers

    Each task handler is a class, a new instance of which is created
    to handle each task.
    """

    # list of methods the class can handle
    Methods = []

    # Options:
    Foreground = False

    def __init__(self, id, method, params, session, options, workdir=None):
        self.id = id  # task id
        if method not in self.Methods:
            raise koji.GenericError('method "%s" is not supported' % method)
        self.method = method
        # handle named parameters
        self.params, self.opts = koji.decode_args(*params)
        self.session = session
        self.options = options
        if workdir is None:
            workdir = "%s/%s" % (self.options.workdir, koji.pathinfo.taskrelpath(id))
        self.workdir = workdir
        self.logger = logging.getLogger("koji.build.BaseTaskHandler")
        self.manager = None
        self.taskinfo = None

    def setManager(self, manager):
        """Set the manager attribute

        This is only used for foreground tasks to give them access
        to their task manager.
        """
        if not self.Foreground:
            return
        self.manager = manager

    def handler(self):
        """(abstract) the handler for the task."""
        raise NotImplementedError

    def run(self):
        """Execute the task"""
        self.createWorkdir()
        try:
            return koji.util.call_with_argcheck(self.handler, self.params, self.opts)
        finally:
            self.removeWorkdir()

    _taskWeight = 1.0

    def weight(self):
        """Return the weight of the task.

        This is run by the taskmanager before the task is run to determine
        the weight of the task. The weight is an abstract measure of the
        total load the task places on the system while running.

        A task may set _taskWeight for a constant weight different from 1, or
        override this function for more complicated situations.

        Note that task weight is partially ignored while the task is sleeping.
        """
        return getattr(self, '_taskWeight', 1.0)

    def createWorkdir(self):
        if self.workdir is None:
            return
        self.removeWorkdir()
        os.makedirs(self.workdir)

    def removeWorkdir(self):
        if self.workdir is None:
            return
        safe_rmtree(self.workdir, unmount=False, strict=True)
        # os.spawnvp(os.P_WAIT, 'rm', ['rm', '-rf', self.workdir])

    def wait(self, subtasks=None, all=False, failany=False, canfail=None,
             timeout=None):
        """Wait on subtasks

        subtasks is a list of integers (or an integer). If more than one subtask
        is specified, then the default behavior is to return when any of those
        tasks complete. However, if all is set to True, then it waits for all of
        them to complete.

        If all and failany are both set to True, then each finished task will
        be checked for failure, and a failure will cause all of the unfinished
        tasks to be cancelled.

        If canfail is given a list of task ids, then those tasks can fail
        without affecting the other tasks.

        If timeout is specified, then subtasks will be failed and an exception
        raised when the timeout is exceeded.

        special values:
            subtasks = None     specify all subtasks

        Implementation notes:
            The build daemon forks all tasks as separate processes. This function
            uses signal.pause to sleep. The main process watches subtasks in
            the database and will send the subprocess corresponding to the
            subtask a SIGUSR2 to wake it up when subtasks complete.
        """

        if canfail is None:
            checked = set()
        else:
            # canfail task are marked as checked
            checked = set(canfail)
        if isinstance(subtasks, int):
            # allow single integer w/o enclosing list
            subtasks = [subtasks]
        self.session.host.taskSetWait(self.id, subtasks)
        self.logger.debug("Waiting on %r" % subtasks)
        start = time.time()
        while True:
            finished, unfinished = self.session.host.taskWait(self.id)
            if len(unfinished) == 0:
                # all done
                break
            elif len(finished) > 0:
                if all:
                    if failany:
                        # we care only about tasks which are not correctly
                        # finished and in same time not in canfail list
                        for task in set(finished) - checked:
                            try:
                                self.session.getTaskResult(task)
                                checked.add(task)
                            except (koji.GenericError, six.moves.xmlrpc_client.Fault):
                                self.logger.info(
                                    "task %s failed or was canceled, cancelling unfinished tasks" %
                                    task)
                                self.session.cancelTaskChildren(self.id)
                                # reraise the original error now, rather than waiting for
                                # an error in taskWaitResults()
                                raise
                else:
                    # at least one done
                    break
            if timeout:
                # sleep until timeout is up (or let main process wake us up)
                remain = start + timeout - time.time()
                if remain > 0:
                    self.logger.debug("Sleeping for %.1fs", remain)
                    if hasattr(signal, 'sigtimedwait'):
                        # Note, that sigtimedwait doesn't trigger signal handler (from 3.3)
                        signal.sigtimedwait([signal.SIGUSR2], timeout)
                    else:
                        # time.sleep is not interruptible anymore from python 3.5
                        # https://peps.python.org/pep-0475/
                        time.sleep(remain)
                # check if we're timed out
                duration = time.time() - start
                if duration > timeout:
                    self.logger.info('Subtasks timed out')
                    self.session.cancelTaskChildren(self.id)
                    raise koji.GenericError('Subtasks timed out after %.1f '
                                            'seconds' % duration)
            else:
                # signal handler set by TaskManager.forkTask
                self.logger.debug("Pausing...")
                signal.pause()
                # main process will wake us up with SIGUSR2
                self.logger.debug("...waking up")

        self.logger.debug("Finished waiting")
        if all:
            finished = subtasks
        return dict(self.session.host.taskWaitResults(self.id, finished,
                                                      canfail=canfail))

    def getUploadDir(self):
        return koji.pathinfo.taskrelpath(self.id)

    def uploadFile(self, filename, relPath=None, remoteName=None, volume=None):
        """Upload the file with the given name to the task output directory
        on the hub."""
        uploadPath = self.getUploadDir()
        if relPath:
            relPath = relPath.strip('/')
            uploadPath += '/' + relPath
        self.session.uploadWrapper(filename, uploadPath, remoteName, volume=volume)

    def uploadTree(self, dirpath, flatten=False, volume=None):
        """Upload the directory tree at dirpath to the task directory on the
        hub, preserving the directory structure"""
        dirpath = dirpath.rstrip('/')
        for path, dirs, files in os.walk(dirpath):
            if flatten:
                relpath = None
            else:
                relpath = path[len(dirpath) + 1:]
            for f in files:
                filename = os.path.join(path, f)
                if not os.path.isfile(filename):
                    self.logger.warning('Skipping upload for non-file: %s', filename)
                    continue
                if os.stat(filename).st_size == 0:
                    self.logger.warning('Skipping upload for empty file: %s', filename)
                    continue
                self.uploadFile(filename, relpath, volume=volume)

    def chownTree(self, dirpath, uid, gid):
        """chown the given path and all files and directories under
        it to the given uid/gid."""
        for path, dirs, files in os.walk(dirpath):
            os.lchown(path, uid, gid)
            for filename in files:
                os.lchown(os.path.join(path, filename), uid, gid)

    def localPath(self, relpath):
        """Return a local path to a remote file.

        If the file is on an nfs mount, use that, otherwise download a copy"""
        if self.options.topurl:
            fn = "%s/local/%s" % (self.workdir, relpath)
            if os.path.exists(fn):
                # We've already downloaded this file,
                # just return the existing local path
                return fn
            self.logger.debug("Downloading %s", relpath)
            url = "%s/%s" % (self.options.topurl, relpath)
            if not os.path.exists(os.path.dirname(fn)):
                os.makedirs(os.path.dirname(fn))
            koji.downloadFile(url, path=fn)
        else:
            fn = "%s/%s" % (self.options.topdir, relpath)
        return fn

    def subtask(self, method, arglist, **opts):
        return self.session.host.subtask(method, arglist, self.id, **opts)

    def subtask2(self, __taskopts, __method, *args, **kwargs):
        return self.session.host.subtask2(self.id, __taskopts, __method, *args, **kwargs)

    def find_arch(self, arch, host, tag, preferred_arch=None):
        """
        For noarch tasks, find a canonical arch that is supported by both the host and tag.
        If the arch is anything other than noarch, return it unmodified.

        If preferred_arch is set, try to get it, but not fail on that
        """
        if arch != "noarch":
            return arch

        # We need a concrete arch. Pick one that:
        #  a) this host can handle
        #  b) the build tag can support
        #  c) is canonical
        host_arches = host['arches']
        if not host_arches:
            raise koji.BuildError("No arch list for this host: %s" %
                                  host['name'])
        tag_arches = tag['arches']
        if not tag_arches:
            raise koji.BuildError("No arch list for tag: %s" % tag['name'])
        # index canonical host arches
        host_arches = set([koji.canonArch(a) for a in host_arches.split()])
        # index canonical tag arches
        tag_arches = set([koji.canonArch(a) for a in tag_arches.split()])
        # find the intersection of host and tag arches
        common_arches = list(host_arches & tag_arches)
        if common_arches:
            if preferred_arch and preferred_arch in common_arches:
                self.logger.info('Valid arches: %s, using preferred: %s' %
                                 (' '.join(sorted(common_arches)), preferred_arch))
                return preferred_arch
            # pick one of the common arches randomly
            # need to re-seed the prng or we'll get the same arch every time,
            # because we just forked from a common parent
            random.seed()
            arch = random.choice(common_arches)
            self.logger.info('Valid arches: %s, using: %s' %
                             (' '.join(sorted(common_arches)), arch))
            return arch
        else:
            # no overlap
            raise koji.BuildError("host %s (%s) does not support any arches"
                                  " of tag %s (%s)" %
                                  (host['name'],
                                   ', '.join(sorted(host_arches)),
                                   tag['name'],
                                   ', '.join(sorted(tag_arches))))

    def getRepo(self, tag, builds=None, wait=False):
        """
        Get a repo that satisfies the given conditions. If there is no matching
        repo available, wait for one (via a waitrepo subtask).

        :param int|str tag: the tag for the requested repo
        :param list builds: require that the repo contain these builds
        :param bool wait: (misnamed) get a repo that is current as of our start time
        """

        if wait:
            # This option is now misnamed. Previously we would always wait to ensure a
            # current repo, but we have better options now
            min_event = "last"
        else:
            min_event = None

        watcher = koji.util.RepoWatcher(self.session, tag, nvrs=builds, min_event=min_event,
                                        logger=self.logger)
        repoinfo = watcher.getRepo()

        # Did we get a repo?
        if repoinfo:
            return repoinfo

        # otherwise, we create a subtask to continue waiting for us
        # this makes the process more visible to the user
        args = watcher.task_args()
        task_id = self.session.host.subtask(method='waitrepo', arglist=args, parent=self.id)
        repo_info = self.wait(task_id)[task_id]
        return repo_info

    def run_callbacks(self, plugin, *args, **kwargs):
        if 'taskinfo' not in kwargs:
            kwargs['taskinfo'] = self.taskinfo
        kwargs['session'] = self.session
        koji.plugin.run_callbacks(plugin, *args, **kwargs)

    @property
    def taskinfo(self):
        if not getattr(self, '_taskinfo', None):
            self._taskinfo = self.session.getTaskInfo(self.id, request=True, strict=True)
        return self._taskinfo

    @taskinfo.setter
    def taskinfo(self, taskinfo):
        self._taskinfo = taskinfo


class FakeTask(BaseTaskHandler):
    Methods = ['someMethod']
    Foreground = True

    def handler(self, *args):
        self.logger.info("This is a fake task.  Args: " + str(args))
        return 42


class SleepTask(BaseTaskHandler):
    Methods = ['sleep']
    _taskWeight = 0.25

    def handler(self, n):
        self.logger.info("Sleeping for %s seconds" % n)
        time.sleep(n)
        self.logger.info("Finished sleeping")


class ForkTask(BaseTaskHandler):
    Methods = ['fork']

    def handler(self, n=5, m=37):
        for i in range(n):
            os.spawnvp(os.P_NOWAIT, 'sleep', ['sleep', str(m)])


class WaitTestTask(BaseTaskHandler):
    """
    Tests self.wait()

    Starts few tasks which just sleeps. One of them will fail due to bad
    arguments. As it is listed as 'canfail' it shouldn't affect overall
    CLOSED status.
    """
    Methods = ['waittest']
    _taskWeight = 0.1

    def handler(self, count, seconds=10):
        tasks = []
        for i in range(count):
            task_id = self.subtask(method='sleep', arglist=[seconds], label=str(i))
            tasks.append(task_id)
        bad_task = self.subtask('sleep', ['BAD_ARG'], label='bad')
        tasks.append(bad_task)
        results = self.wait(subtasks=tasks, all=True, failany=True, canfail=[bad_task])
        self.logger.info(pprint.pformat(results))


class SubtaskTask(BaseTaskHandler):
    Methods = ['subtask']
    _taskWeight = 0.1

    def handler(self, n=4):
        if n > 0:
            task_id = self.session.host.subtask(method='subtask',
                                                arglist=[n - 1],
                                                label='foo',
                                                parent=self.id)
            self.wait(task_id)
        else:
            task_id = self.session.host.subtask(method='sleep',
                                                arglist=[15],
                                                label='bar',
                                                parent=self.id)
            self.wait(task_id)


class DefaultTask(BaseTaskHandler):
    """Used when no matching method is found"""
    Methods = ['default']
    _taskWeight = 0.1

    def handler(self, *args, **opts):
        raise koji.GenericError("Invalid method: %s" % self.method)


class ShutdownTask(BaseTaskHandler):
    Methods = ['shutdown']
    _taskWeight = 0.0
    Foreground = True

    def handler(self):
        # note: this is a foreground task
        raise ServerExit


class RestartTask(BaseTaskHandler):
    """Gracefully restart the daemon"""

    Methods = ['restart']
    _taskWeight = 0.1
    Foreground = True

    def handler(self, host):
        # note: this is a foreground task
        if host['id'] != self.session.host.getID():
            raise koji.GenericError("Host mismatch")
        self.manager.restart_pending = True
        return "graceful restart initiated"


class RestartVerifyTask(BaseTaskHandler):
    """Verify that the daemon has restarted"""

    Methods = ['restartVerify']
    _taskWeight = 0.1
    Foreground = True

    def handler(self, task_id, host):
        # note: this is a foreground task
        tinfo = self.session.getTaskInfo(task_id)
        state = koji.TASK_STATES[tinfo['state']]
        if state != 'CLOSED':
            raise koji.GenericError("Stage one restart task is %s" % state)
        if host['id'] != self.session.host.getID():
            raise koji.GenericError("Host mismatch")
        if self.manager.start_ts < tinfo['completion_ts']:
            start_time = time.asctime(time.localtime(self.manager.start_ts))
            raise koji.GenericError("Restart failed - start time is %s" % start_time)


class RestartHostsTask(BaseTaskHandler):
    """Gracefully restart the build hosts"""

    Methods = ['restartHosts']
    _taskWeight = 0.1

    def handler(self, options=None):
        if options is None:
            options = {}
        # figure out which hosts we're restarting
        hostquery = {'enabled': True}
        if 'channel' in options:
            chan = self.session.getChannel(options['channel'], strict=True)
            hostquery['channelID'] = chan['id']
        if 'arches' in options:
            hostquery['arches'] = options['arches']
        hosts = self.session.listHosts(**hostquery)
        if not hosts:
            raise koji.GenericError("No matching hosts")

        timeout = options.get('timeout', 3600 * 24)

        # fire off the subtasks
        this_host = self.session.host.getID()
        subtasks = []
        my_tasks = None
        for host in hosts:
            # note: currently task assignments bypass channel restrictions
            task1 = self.subtask('restart', [host],
                                 assign=host['id'], label="restart %i" % host['id'])
            task2 = self.subtask('restartVerify', [task1, host],
                                 assign=host['id'], label="sleep %i" % host['id'])
            subtasks.append(task1)
            subtasks.append(task2)
            if host['id'] == this_host:
                my_tasks = [task1, task2]

        # if we're being restarted, then we have to take extra steps
        if my_tasks:
            self.wait(my_tasks[0], timeout=timeout)
            # see if we've restarted
            if not self.session.taskFinished(my_tasks[1]):
                raise ServerRestart
                # raising this inside a task handler causes TaskManager.runTask
                # to free the task so that it will not block a pending restart

        # at this point the subtasks do the rest
        if subtasks:
            self.wait(subtasks, all=True, timeout=timeout)


class DependantTask(BaseTaskHandler):

    Methods = ['dependantTask']
    # mostly just waiting on other tasks
    _taskWeight = 0.2

    def handler(self, wait_list, task_list):
        for task in wait_list:
            if not isinstance(task, int) or not self.session.getTaskInfo(task):
                self.logger.debug("invalid task id %s, removing from wait_list" % task)
                wait_list.remove(task)

        # note, tasks in wait_list are not children of this task so we can't
        # just use self.wait()
        while wait_list:
            for task in wait_list[:]:
                if self.session.taskFinished(task):
                    info = self.session.getTaskInfo(task)
                    if info and koji.TASK_STATES[info['state']] in ['CANCELED', 'FAILED']:
                        raise koji.GenericError("Dependency %s failed to complete." % info['id'])
                    wait_list.remove(task)
            # let the system rest before polling again
            time.sleep(1)

        subtasks = []
        for task in task_list:
            # **((len(task)>2 and task[2]) or {}) expands task[2] into opts if it exists, allows
            # for things like 'priority=15'
            task_id = self.session.host.subtask(method=task[0], arglist=task[1], parent=self.id,
                                                **((len(task) > 2 and task[2]) or {}))
            if task_id:
                subtasks.append(task_id)
        if subtasks:
            self.wait(subtasks, all=True)


class MultiPlatformTask(BaseTaskHandler):
    def buildWrapperRPM(self, spec_url, build_task_id, build_target, build, repo_id, **opts):
        task = self.session.getTaskInfo(build_task_id)
        arglist = [spec_url, build_target, build, task, {'repo_id': repo_id}]

        rpm_task_id = self.session.host.subtask(method='wrapperRPM',
                                                arglist=arglist,
                                                label='rpm',
                                                parent=self.id,
                                                arch='noarch',
                                                **opts)
        results = self.wait(rpm_task_id)[rpm_task_id]
        results['task_id'] = rpm_task_id

        return results


class WaitrepoTask(BaseTaskHandler):

    Methods = ['waitrepo']
    # mostly just waiting
    _taskWeight = 0.2

    PAUSE = 60
    # time in minutes before we fail this task
    TIMEOUT = 120

    def handler(self, tag, newer_than=None, nvrs=None, min_event=None):
        """Wait for a repo for the tag, subject to given conditions

        tag: the tag for the repo
        newer_than: (legacy) create_event timestamp should be newer than this
        nvrs: repo should contain these nvrs (which may not exist at first)
        min_event: minimum event for the repo

        The newer_than arg is provided for backward compatibility. The min_event arg is preferred.

        Returns the repo info of the chosen repo
        """

        # handle legacy newer_than arg
        if newer_than is not None:
            if min_event is not None:
                raise koji.GenericError('newer_than and min_event args confict')
            if isinstance(newer_than, six.string_types) and newer_than.lower() == "now":
                min_event = "last"
            elif isinstance(newer_than, six.integer_types + (float,)):
                # here, we look for the first event where the tag changed after this time
                # or, if the tag has not changed since that time, we use its last change event
                base = self.session.getLastEvent(before=newer_than, strict=False)
                min_event = self.session.tagFirstChangeEvent(tag, after=base) or "last"
            else:
                raise koji.GenericError("Invalid value for newer_than: %s" % newer_than)

        watcher = koji.util.RepoWatcher(self.session, tag, nvrs=nvrs, min_event=min_event,
                                        logger=self.logger)
        watcher.PAUSE = self.PAUSE
        watcher.TIMEOUT = self.TIMEOUT
        # TODO config?
        repoinfo = watcher.waitrepo()
        return repoinfo


# the end
