# Python module
# tasks handlers for the koji build daemon

# Copyright (c) 2008 Red Hat
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
#
# Authors:
#       Mike McLean <mikem@redhat.com>

import koji
import logging
import os
import signal
import urllib2


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
            workdir = "%s/%s" % (options.workdir, koji.pathinfo.taskrelpath(id))
        self.workdir = workdir
        self.logger = logging.getLogger("koji.build.BaseTaskHandler")

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
                            except (koji.GenericError, Fault), task_error:
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

    def uploadFile(self, filename, remoteName=None):
        """Upload the file with the given name to the task output directory
        on the hub."""
        # Only upload files with content
        if os.path.isfile(filename) and os.stat(filename).st_size > 0:
            self.session.uploadWrapper(filename, self.getUploadDir(), remoteName)

    def localPath(self, relpath):
        """Return a local path to a remote file.

        If the file is on an nfs mount, use that, otherwise download a copy"""
        if self.options.topurl:
            self.logger.debug("Downloading %s", relpath)
            url = "%s/%s" % (self.options.topurl, relpath)
            fsrc = urllib2.urlopen(url)
            fn = "%s/local/%s" % (self.workdir, relpath)
            os.makedirs(os.path.dirname(fn))
            fdst = file(fn, 'w')
            shutil.copyfileobj(fsrc, fdst)
            fsrc.close()
            fdst.close()
        else:
            fn = "%s/%s" % (self.options.topdir, relpath)
        return fn


#XXX - not the right place for this
#XXX - not as safe as we want
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

