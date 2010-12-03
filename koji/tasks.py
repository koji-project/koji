# Task definitions used by various Koji daemons

# Copyright (c) 2010 Red Hat, Inc.
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

import koji
import os
import logging
import xmlrpclib
import signal
import urllib2
import shutil
import random
import time
import pprint

def scan_mounts(topdir):
    """Search path for mountpoints"""
    mplist = []
    topdir = os.path.normpath(topdir)
    fo = file('/proc/mounts','r')
    for line in fo.readlines():
        path = line.split()[1]
        if path.startswith(topdir):
            mplist.append(path)
    fo.close()
    #reverse sort so deeper dirs come first
    mplist.sort()
    mplist.reverse()
    return mplist

def umount_all(topdir):
    "Unmount every mount under topdir"
    logger = logging.getLogger("koji.build")
    for path in scan_mounts(topdir):
        logger.debug('Unmounting %s' % path)
        cmd = ['umount', '-l', path]
        rv = os.spawnvp(os.P_WAIT,cmd[0],cmd)
        if rv != 0:
            raise koji.GenericError, 'umount failed (exit code %r) for %s' % (rv,path)
    #check mounts again
    remain = scan_mounts(topdir)
    if remain:
        raise koji.GenericError, "Unmounting incomplete: %r" % remain

def safe_rmtree(path, unmount=False, strict=True):
    logger = logging.getLogger("koji.build")
    #safe remove: with -xdev the find cmd will not cross filesystems
    #             (though it will cross bind mounts from the same filesystem)
    if not os.path.exists(path):
        logger.debug("No such path: %s" % path)
        return
    if unmount:
        umount_all(path)
    #first rm -f non-directories
    logger.debug('Scrubbing files in %s' % path)
    rv = os.system("find '%s' -xdev \\! -type d -print0 |xargs -0 rm -f" % path)
    msg = 'file removal failed (code %r) for %s' % (rv,path)
    if rv != 0:
        logger.warn(msg)
        if strict:
            raise koji.GenericError, msg
        else:
            return rv
    #them rmdir directories
    #with -depth, we start at the bottom and work up
    logger.debug('Scrubbing directories in %s' % path)
    rv = os.system("find '%s' -xdev -depth -type d -print0 |xargs -0 rmdir" % path)
    msg = 'dir removal failed (code %r) for %s' % (rv,path)
    if rv != 0:
        logger.warn(msg)
        if strict:
            raise koji.GenericError, msg
    return rv

class ServerExit(Exception):
    """Raised to shutdown the server"""
    pass

class ServerRestart(Exception):
    """Raised to restart the server"""
    pass

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
        self.id = id   #task id
        if method not in self.Methods:
            raise koji.GenericError, 'method "%s" is not supported' % method
        self.method = method
        # handle named parameters
        self.params,self.opts = koji.decode_args(*params)
        self.session = session
        self.options = options
        if workdir is None:
            workdir = "%s/%s" % (self.options.workdir, koji.pathinfo.taskrelpath(id))
        self.workdir = workdir
        self.logger = logging.getLogger("koji.build.BaseTaskHandler")
        self.manager = None

    def setManager(self,manager):
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
            return self.handler(*self.params,**self.opts)
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
        return getattr(self,'_taskWeight',1.0)

    def createWorkdir(self):
        if self.workdir is None:
            return
        self.removeWorkdir()
        os.makedirs(self.workdir)

    def removeWorkdir(self):
        if self.workdir is None:
            return
        safe_rmtree(self.workdir, unmount=False, strict=True)
        #os.spawnvp(os.P_WAIT, 'rm', ['rm', '-rf', self.workdir])

    def wait(self, subtasks=None, all=False, failany=False):
        """Wait on subtasks

        subtasks is a list of integers (or an integer). If more than one subtask
        is specified, then the default behavior is to return when any of those
        tasks complete. However, if all is set to True, then it waits for all of
        them to complete.  If all and failany are both set to True, then each
        finished task will be checked for failure, and a failure will cause all
        of the unfinished tasks to be cancelled.

        special values:
            subtasks = None     specify all subtasks

        Implementation notes:
            The build daemon forks all tasks as separate processes. This function
            uses signal.pause to sleep. The main process watches subtasks in
            the database and will send the subprocess corresponding to the
            subtask a SIGUSR2 to wake it up when subtasks complete.
        """
        if isinstance(subtasks,int):
            # allow single integer w/o enclosing list
            subtasks = [subtasks]
        self.session.host.taskSetWait(self.id,subtasks)
        self.logger.debug("Waiting on %r" % subtasks)
        while True:
            finished, unfinished = self.session.host.taskWait(self.id)
            if len(unfinished) == 0:
                #all done
                break
            elif len(finished) > 0:
                if all:
                    if failany:
                        failed = False
                        for task in finished:
                            try:
                                result = self.session.getTaskResult(task)
                            except (koji.GenericError, xmlrpclib.Fault), task_error:
                                self.logger.info("task %s failed or was canceled" % task)
                                failed = True
                                break
                        if failed:
                            self.logger.info("at least one task failed or was canceled, cancelling unfinished tasks")
                            self.session.cancelTaskChildren(self.id)
                            # reraise the original error now, rather than waiting for
                            # an error in taskWaitResults()
                            raise task_error
                else:
                    # at least one done
                    break
            # signal handler set by TaskManager.forkTask
            self.logger.debug("Pausing...")
            signal.pause()
            # main process will wake us up with SIGUSR2
            self.logger.debug("...waking up")
        self.logger.debug("Finished waiting")
        return dict(self.session.host.taskWaitResults(self.id,subtasks))

    def getUploadDir(self):
        return koji.pathinfo.taskrelpath(self.id)

    def uploadFile(self, filename, relPath=None, remoteName=None):
        """Upload the file with the given name to the task output directory
        on the hub."""
        uploadPath = self.getUploadDir()
        if relPath:
            relPath = relPath.strip('/')
            uploadPath += '/' + relPath
        # Only upload files with content
        if os.path.isfile(filename) and os.stat(filename).st_size > 0:
            self.session.uploadWrapper(filename, uploadPath, remoteName)

    def uploadTree(self, dirpath, flatten=False):
        """Upload the directory tree at dirpath to the task directory on the
        hub, preserving the directory structure"""
        dirpath = dirpath.rstrip('/')
        for path, dirs, files in os.walk(dirpath):
            if flatten:
                relpath = None
            else:
                relpath = path[len(dirpath) + 1:]
            for filename in files:
                self.uploadFile(os.path.join(path, filename), relpath)

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
            fsrc = urllib2.urlopen(url)
            if not os.path.exists(os.path.dirname(fn)):
                os.makedirs(os.path.dirname(fn))
            fdst = file(fn, 'w')
            shutil.copyfileobj(fsrc, fdst)
            fsrc.close()
            fdst.close()
        else:
            fn = "%s/%s" % (self.options.topdir, relpath)
        return fn

    def subtask(self, method, arglist, **opts):
        return self.session.host.subtask(method, arglist, self.id, **opts)

    def subtask2(self, __taskopts, __method, *args, **kwargs):
        return self.session.host.subtask2(self.id, __taskopts, __method, *args, **kwargs)

    def find_arch(self, arch, host, tag):
        """
        For noarch tasks, find a canonical arch that is supported by both the host and tag.
        If the arch is anything other than noarch, return it unmodified.
        """
        if arch != "noarch":
            return arch

        # We need a concrete arch. Pick one that:
        #  a) this host can handle
        #  b) the build tag can support
        #  c) is canonical
        host_arches = host['arches']
        if not host_arches:
            raise koji.BuildError, "No arch list for this host: %s" % host['name']
        tag_arches = tag['arches']
        if not tag_arches:
            raise koji.BuildError, "No arch list for tag: %s" % tag['name']
        # index canonical host arches
        host_arches = set([koji.canonArch(a) for a in host_arches.split()])
        # index canonical tag arches
        tag_arches = set([koji.canonArch(a) for a in tag_arches.split()])
        # find the intersection of host and tag arches
        common_arches = list(host_arches & tag_arches)
        if common_arches:
            # pick one of the common arches randomly
            # need to re-seed the prng or we'll get the same arch every time,
            # because we just forked from a common parent
            random.seed()
            arch = random.choice(common_arches)
            self.logger.info('Valid arches: %s, using: %s' % (' '.join(common_arches), arch))
            return arch
        else:
            # no overlap
            raise koji.BuildError, "host %s (%s) does not support any arches of tag %s (%s)" % \
                (host['name'], ', '.join(host_arches), tag['name'], ', '.join(tag_arches))

    def getRepo(self, tag):
        """
        Get the active repo for the given tag.  If there is no repo available,
        wait for a repo to be created.
        """
        repo_info = self.session.getRepo(tag)
        if not repo_info:
            #wait for it
            task_id = self.session.host.subtask(method='waitrepo',
                                                arglist=[tag, None, None],
                                                parent=self.id)
            repo_info = self.wait(task_id)[task_id]
        return repo_info


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
        for i in xrange(n):
            os.spawnvp(os.P_NOWAIT, 'sleep', ['sleep',str(m)])

class WaitTestTask(BaseTaskHandler):
    Methods = ['waittest']
    _taskWeight = 0.1
    def handler(self,count,seconds=10):
        tasks = []
        for i in xrange(count):
            task_id = self.session.host.subtask(method='sleep',
                                                arglist=[seconds],
                                                label=str(i),
                                                parent=self.id)
            tasks.append(task_id)
        results = self.wait(all=True)
        self.logger.info(pprint.pformat(results))


class SubtaskTask(BaseTaskHandler):
    Methods = ['subtask']
    _taskWeight = 0.1
    def handler(self,n=4):
        if n > 0:
            task_id = self.session.host.subtask(method='subtask',
                                                arglist=[n-1],
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
    def handler(self,*args,**opts):
        raise koji.GenericError, "Invalid method: %s" % self.method


class ShutdownTask(BaseTaskHandler):
    Methods = ['shutdown']
    _taskWeight = 0.0
    Foreground = True
    def handler(self):
        #note: this is a foreground task
        raise ServerExit


class RestartTask(BaseTaskHandler):
    """Gracefully restart the daemon"""

    Methods = ['restart']
    _taskWeight = 0.1
    Foreground = True
    def handler(self, host):
        #note: this is a foreground task
        if host['id'] != self.session.host.getID():
            raise koji.GenericError, "Host mismatch"
        self.manager.restart_pending = True
        return "graceful restart initiated"


class RestartVerifyTask(BaseTaskHandler):
    """Verify that the daemon has restarted"""

    Methods = ['restartVerify']
    _taskWeight = 0.1
    Foreground = True
    def handler(self, task_id, host):
        #note: this is a foreground task
        tinfo = self.session.getTaskInfo(task_id)
        state = koji.TASK_STATES[tinfo['state']]
        if state != 'CLOSED':
            raise koji.GenericError, "Stage one restart task is %s" % state
        if host['id'] != self.session.host.getID():
            raise koji.GenericError, "Host mismatch"
        if self.manager.start_time < tinfo['completion_ts']:
            start_time = time.asctime(time.localtime(self.manager.start_time))
            raise koji.GenericError, "Restart failed - start time is %s" % start_time


class RestartHostsTask(BaseTaskHandler):
    """Gracefully restart the daemon"""

    Methods = ['restartHosts']
    _taskWeight = 0.1
    def handler(self):
        hosts = self.session.listHosts(enabled=True)
        if not hosts:
            raise koji.GenericError, "No hosts enabled"
        this_host = self.session.host.getID()
        subtasks = []
        my_tasks = None
        for host in hosts:
            #note: currently task assignments bypass channel restrictions
            task1 = self.subtask('restart', [host], assign=host['id'], label="restart %i" % host['id'])
            task2 = self.subtask('restartVerify', [task1, host], assign=host['id'], label="sleep %i" % host['id'])
            subtasks.append(task1)
            subtasks.append(task2)
            if host['id'] == this_host:
                my_tasks = [task1, task2]
        if not my_tasks:
            raise koji.GenericError, 'This host is not enabled'
        self.wait(my_tasks[0])
        #see if we've restarted
        if not self.session.taskFinished(my_tasks[1]):
            raise ServerRestart
            #raising this inside a task handler causes TaskManager.runTask
            #to free the task so that it will not block a pending restart
        if subtasks:
            self.wait(subtasks, all=True)
        return


class DependantTask(BaseTaskHandler):

    Methods = ['dependantTask']
    #mostly just waiting on other tasks
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
                    if info and koji.TASK_STATES[info['state']] in ['CANCELED','FAILED']:
                        raise koji.GenericError, "Dependency %s failed to complete." % info['id']
                    wait_list.remove(task)
            # let the system rest before polling again
            time.sleep(1)

        subtasks = []
        for task in task_list:
            # **((len(task)>2 and task[2]) or {}) expands task[2] into opts if it exists, allows for things like 'priority=15'
            task_id = self.session.host.subtask(method=task[0], arglist=task[1], parent=self.id, **((len(task)>2 and task[2]) or {}))
            if task_id:
                subtasks.append(task_id)
        if subtasks:
            self.wait(subtasks, all=True)

class MultiPlatformTask(BaseTaskHandler):
    def buildWrapperRPM(self, spec_url, build_task_id, build_tag, build, repo_id, **opts):
        task = self.session.getTaskInfo(build_task_id)
        arglist = [spec_url, build_tag, build, task, {'repo_id': repo_id}]

        rpm_task_id = self.session.host.subtask(method='wrapperRPM',
                                                arglist=arglist,
                                                label='rpm',
                                                parent=self.id,
                                                arch='noarch',
                                                **opts)
        results = self.wait(rpm_task_id)[rpm_task_id]
        results['task_id'] = rpm_task_id

        return results
