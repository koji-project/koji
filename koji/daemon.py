# Code shared by various Koji daemons

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
#       Mike Bonnet <mikeb@redhat.com>

import koji
import koji.tasks
from koji.tasks import safe_rmtree
from koji.util import md5_constructor, parseStatus
import os
import signal
import logging
import urlparse
from fnmatch import fnmatch
import base64
import time
import sys
import traceback
import errno
import xmlrpclib


def incremental_upload(session, fname, fd, path, retries=5, logger=None):
    if not fd:
        return

    while True:
        offset = fd.tell()
        contents = fd.read(65536)
        size = len(contents)
        if size == 0:
            break

        data = base64.encodestring(contents)
        digest = md5_constructor(contents).hexdigest()
        del contents

        tries = 0
        while True:
            if session.uploadFile(path, fname, size, digest, offset, data):
                break

            if tries <= retries:
                tries += 1
                time.sleep(10)
                continue
            else:
                if logger:
                    logger.error("Error uploading file %s to %s at offset %d" % (fname, path, offset))
                else:
                    sys.stderr.write("Error uploading file %s to %s at offset %d\n" % (fname, path, offset))
                break

def log_output(session, path, args, outfile, uploadpath, cwd=None, logerror=0, append=0, chroot=None, env=None):
    """Run command with output redirected.  If chroot is not None, chroot to the directory specified
    before running the command."""
    pid = os.fork()
    fd = None
    if not pid:
        session._forget()
        try:
            if chroot:
                os.chroot(chroot)
            if cwd:
                os.chdir(cwd)
            flags = os.O_CREAT | os.O_WRONLY
            if append:
                flags |= os.O_APPEND
            fd = os.open(outfile, flags, 0666)
            os.dup2(fd, 1)
            if logerror:
                os.dup2(fd, 2)
            # echo the command we're running into the logfile
            os.write(fd, '$ %s\n' % ' '.join(args))
            environ = os.environ.copy()
            if env:
                environ.update(env)
            os.execvpe(path, args, environ)
        except:
            msg = ''.join(traceback.format_exception(*sys.exc_info()))
            if fd:
                try:
                    os.write(fd, msg)
                    os.close(fd)
                except:
                    pass
            print msg
            os._exit(1)
    else:
        if chroot:
            outfile = os.path.normpath(chroot + outfile)
        outfd = None
        remotename = os.path.basename(outfile)
        while True:
            status = os.waitpid(pid, os.WNOHANG)
            time.sleep(1)

            if not outfd:
                try:
                    outfd = file(outfile, 'r')
                except IOError:
                    # will happen if the forked process has not created the logfile yet
                    continue
                except:
                    print 'Error reading log file: %s' % outfile
                    print ''.join(traceback.format_exception(*sys.exc_info()))

            incremental_upload(session, remotename, outfd, uploadpath)

            if status[0] != 0:
                if outfd:
                    outfd.close()
                return status[1]


## BEGIN kojikamid dup

class SCM(object):
    "SCM abstraction class"

    types = { 'CVS': ('cvs://',),
              'CVS+SSH': ('cvs+ssh://',),
              'GIT': ('git://', 'git+http://', 'git+https://', 'git+rsync://'),
              'GIT+SSH': ('git+ssh://',),
              'SVN': ('svn://', 'svn+http://', 'svn+https://'),
              'SVN+SSH': ('svn+ssh://',) }

    def is_scm_url(url):
        """
        Return True if the url appears to be a valid, accessible source location, False otherwise
        """
        for schemes in SCM.types.values():
            for scheme in schemes:
                if url.startswith(scheme):
                    return True
        else:
            return False
    is_scm_url = staticmethod(is_scm_url)

    def __init__(self, url):
        """
        Initialize the SCM object using the specified url.
        The expected url format is:

        scheme://[user@]host/path/to/repo?path/to/module#revision_or_tag_identifier

        The initialized SCM object will have the following attributes:
        - url (the unmodified url)
        - scheme
        - user (may be null)
        - host
        - repository
        - module
        - revision
        - use_common (defaults to True, may be set by assert_allowed())
        - source_cmd (defaults to ['make', 'sources'], may be set by assert_allowed())
        - scmtype

        The exact format of each attribute is SCM-specific, but the structure of the url
        must conform to the template above, or an error will be raised.
        """
        self.logger = logging.getLogger('koji.build.SCM')

        if not SCM.is_scm_url(url):
            raise koji.GenericError, 'Invalid SCM URL: %s' % url

        self.url = url
        scheme, user, host, path, query, fragment = self._parse_url()

        self.scheme = scheme
        self.user = user
        self.host = host
        self.repository = path
        self.module = query
        self.revision = fragment
        self.use_common = True
        self.source_cmd = ['make', 'sources']

        for scmtype, schemes in SCM.types.items():
            if self.scheme in schemes:
                self.scmtype = scmtype
                break
        else:
            # should never happen
            raise koji.GenericError, 'Invalid SCM URL: %s' % url

    def _parse_url(self):
        """
        Parse the SCM url into usable components.
        Return the following tuple:

        (scheme, user, host, path, query, fragment)

        user may be None, everything else will have a value
        """
        # get the url's scheme
        scheme = self.url.split('://')[0] + '://'

        # replace the scheme with http:// so that the urlparse works in all cases
        dummyurl = self.url.replace(scheme, 'http://', 1)
        dummyscheme, netloc, path, params, query, fragment = urlparse.urlparse(dummyurl)

        user = None
        userhost = netloc.split('@')
        if len(userhost) == 2:
            user = userhost[0]
            if not user:
                # Don't return an empty string
                user = None
            elif ':' in user:
                raise koji.GenericError, 'username:password format not supported: %s' % user
            netloc = userhost[1]
        elif len(userhost) > 2:
            raise koji.GenericError, 'Invalid username@hostname specified: %s' % netloc

        # ensure that path and query do not end in /
        if path.endswith('/'):
            path = path[:-1]
        if query.endswith('/'):
            query = query[:-1]

        # check for validity: params should be empty, query may be empty, everything else should be populated
        if params or not (scheme and netloc and path and fragment):
            raise koji.GenericError, 'Unable to parse SCM URL: %s' % self.url

        # return parsed values
        return (scheme, user, netloc, path, query, fragment)

    def assert_allowed(self, allowed):
        """
        Verify that the host and repository of this SCM is in the provided list of
        allowed repositories.

        allowed is a space-separated list of host:repository[:use_common[:source_cmd]] tuples.  Incorrectly-formatted
        tuples will be ignored.

        If use_common is not present, kojid will attempt to checkout a common/ directory from the
        repository.  If use_common is set to no, off, false, or 0, it will not attempt to checkout a common/
        directory.

        source_cmd is a shell command (args separated with commas instead of spaces) to run before building the srpm.
        It is generally used to retrieve source files from a remote location.  If no source_cmd is specified,
        "make sources" is run by default.
        """
        for allowed_scm in allowed.split():
            scm_tuple = allowed_scm.split(':')
            if len(scm_tuple) >= 2:
                if fnmatch(self.host, scm_tuple[0]) and fnmatch(self.repository, scm_tuple[1]):
                    # SCM host:repository is in the allowed list
                    # check if we specify a value for use_common
                    if len(scm_tuple) >= 3:
                        if scm_tuple[2].lower() in ('no', 'off', 'false', '0'):
                            self.use_common = False
                    # check if we specify a custom source_cmd
                    if len(scm_tuple) >= 4:
                        if scm_tuple[3]:
                            self.source_cmd = scm_tuple[3].split(',')
                        else:
                            # there was nothing after the trailing :, so they don't want to run a source_cmd at all
                            self.source_cmd = None
                    break
            else:
                self.logger.warn('Ignoring incorrectly formatted SCM host:repository: %s' % allowed_scm)
        else:
            raise koji.BuildError, '%s:%s is not in the list of allowed SCMs' % (self.host, self.repository)

    def checkout(self, scmdir, session=None, uploadpath=None, logfile=None):
        """
        Checkout the module from SCM.  Accepts the following parameters:
         - scmdir: the working directory
         - session: a ClientSession object
         - uploadpath: the path on the server the logfile should be uploaded to
         - logfile: the file used for logging command output
        session, uploadpath, and logfile are not used when run within kojikamid,
        but are otherwise required.

        Returns the directory that the module was checked-out into (a subdirectory of scmdir)
        """
        # TODO: sanity check arguments
        sourcedir = '%s/%s' % (scmdir, self.module)

        update_checkout_cmd = None
        update_checkout_dir = None
        env = None
        def _run(cmd, chdir=None, fatal=False, log=True, _count=[0]):
            if globals().get('KOJIKAMID'):
                #we've been inserted into kojikamid, use its run()
                return run(cmd, chdir=chdir, fatal=fatal, log=log)
            else:
                append = (_count[0] > 0)
                _count[0] += 1
                if log_output(session, cmd[0], cmd, logfile, uploadpath,
                              cwd=chdir, logerror=1, append=append, env=env):
                    raise koji.BuildError, 'Error running %s command "%s", see %s for details' % \
                        (self.scmtype, ' '.join(cmd), os.path.basename(logfile))

        if self.scmtype == 'CVS':
            pserver = ':pserver:%s@%s:%s' % ((self.user or 'anonymous'), self.host, self.repository)
            module_checkout_cmd = ['cvs', '-d', pserver, 'checkout', '-r', self.revision, self.module]
            common_checkout_cmd = ['cvs', '-d', pserver, 'checkout', 'common']

        elif self.scmtype == 'CVS+SSH':
            if not self.user:
                raise koji.BuildError, 'No user specified for repository access scheme: %s' % self.scheme

            cvsserver = ':ext:%s@%s:%s' % (self.user, self.host, self.repository)
            module_checkout_cmd = ['cvs', '-d', cvsserver, 'checkout', '-r', self.revision, self.module]
            common_checkout_cmd = ['cvs', '-d', cvsserver, 'checkout', 'common']
            env = {'CVS_RSH': 'ssh'}

        elif self.scmtype == 'GIT':
            scheme = self.scheme
            if '+' in scheme:
                scheme = scheme.split('+')[1]
            gitrepo = '%s%s%s' % (scheme, self.host, self.repository)
            commonrepo = os.path.dirname(gitrepo) + '/common'
            checkout_path = os.path.basename(self.repository)
            if self.repository.endswith('/.git'):
                # If we're referring to the .git subdirectory of the main module,
                # assume we need to do the same for the common module
                checkout_path = os.path.basename(self.repository[:-5])
                commonrepo = os.path.dirname(gitrepo[:-5]) + '/common/.git'
            elif self.repository.endswith('.git'):
                # If we're referring to a bare repository for the main module,
                # assume we need to do the same for the common module
                checkout_path = os.path.basename(self.repository[:-4])
                commonrepo = os.path.dirname(gitrepo[:-4]) + '/common.git'

            sourcedir = '%s/%s' % (scmdir, checkout_path)
            module_checkout_cmd = ['git', 'clone', '-n', gitrepo, sourcedir]
            common_checkout_cmd = ['git', 'clone', commonrepo, 'common']
            update_checkout_cmd = ['git', 'reset', '--hard', self.revision]
            update_checkout_dir = sourcedir

            # self.module may be empty, in which case the specfile should be in the top-level directory
            if self.module:
                # Treat the module as a directory inside the git repository
                sourcedir = '%s/%s' % (sourcedir, self.module)

        elif self.scmtype == 'GIT+SSH':
            if not self.user:
                raise koji.BuildError, 'No user specified for repository access scheme: %s' % self.scheme
            gitrepo = 'git+ssh://%s@%s%s' % (self.user, self.host, self.repository)
            commonrepo = os.path.dirname(gitrepo) + '/common'
            checkout_path = os.path.basename(self.repository)
            if self.repository.endswith('/.git'):
                # If we're referring to the .git subdirectory of the main module,
                # assume we need to do the same for the common module
                checkout_path = os.path.basename(self.repository[:-5])
                commonrepo = os.path.dirname(gitrepo[:-5]) + '/common/.git'
            elif self.repository.endswith('.git'):
                # If we're referring to a bare repository for the main module,
                # assume we need to do the same for the common module
                checkout_path = os.path.basename(self.repository[:-4])
                commonrepo = os.path.dirname(gitrepo[:-4]) + '/common.git'

            sourcedir = '%s/%s' % (scmdir, checkout_path)
            module_checkout_cmd = ['git', 'clone', '-n', gitrepo, sourcedir]
            common_checkout_cmd = ['git', 'clone', commonrepo, 'common']
            update_checkout_cmd = ['git', 'reset', '--hard', self.revision]
            update_checkout_dir = sourcedir

            # self.module may be empty, in which case the specfile should be in the top-level directory
            if self.module:
                # Treat the module as a directory inside the git repository
                sourcedir = '%s/%s' % (sourcedir, self.module)

        elif self.scmtype == 'SVN':
            scheme = self.scheme
            if '+' in scheme:
                scheme = scheme.split('+')[1]

            svnserver = '%s%s%s' % (scheme, self.host, self.repository)
            module_checkout_cmd = ['svn', 'checkout', '-r', self.revision, '%s/%s' % (svnserver, self.module), self.module]
            common_checkout_cmd = ['svn', 'checkout', '%s/common' % svnserver]

        elif self.scmtype == 'SVN+SSH':
            if not self.user:
                raise koji.BuildError, 'No user specified for repository access scheme: %s' % self.scheme

            svnserver = 'svn+ssh://%s@%s%s' % (self.user, self.host, self.repository)
            module_checkout_cmd = ['svn', 'checkout', '-r', self.revision, '%s/%s' % (svnserver, self.module), self.module]
            common_checkout_cmd = ['svn', 'checkout', '%s/common' % svnserver]

        else:
            raise koji.BuildError, 'Unknown SCM type: %s' % self.scmtype

        # perform checkouts
        _run(module_checkout_cmd, chdir=scmdir, fatal=True)

        if update_checkout_cmd:
            # Currently only required for GIT checkouts
            # Run the command in the directory the source was checked out into
            if self.scmtype.startswith('GIT') and globals().get('KOJIKAMID'):
                _run(['git', 'config', 'core.autocrlf',  'true'], chdir=update_checkout_dir, fatal=True)
                _run(['git', 'config', 'core.safecrlf',  'true'], chdir=update_checkout_dir, fatal=True)
            _run(update_checkout_cmd, chdir=update_checkout_dir, fatal=True)

        if self.use_common and not globals().get('KOJIKAMID'):
            _run(common_checkout_cmd, chdir=scmdir, fatal=True)
            if not os.path.exists('%s/../common' % sourcedir):
                # find the relative distance from sourcedir/../common to scmdir/common
                destdir = os.path.split(sourcedir)[0]
                path_comps = destdir[len(scmdir) + 1:]
                rel_path = '../' * len(path_comps.split('/'))
                os.symlink(rel_path + 'common', '%s/../common' % sourcedir)

        return sourcedir

## END kojikamid dup


class TaskManager(object):

    def __init__(self, options, session):
        self.options = options
        self.session = session
        self.tasks = {}
        self.pids = {}
        self.subsessions = {}
        self.handlers = {}
        self.status = ''
        self.restart_pending = False
        self.ready = False
        self.hostdata = {}
        self.task_load = 0.0
        self.host_id = self.session.host.getID()
        self.start_time = self.session.getSessionInfo()['start_time']
        self.logger = logging.getLogger("koji.TaskManager")

    def findHandlers(self, vars):
        """Find and index task handlers"""
        for v in vars.values():
            if type(v) == type(koji.tasks.BaseTaskHandler) and issubclass(v,koji.tasks.BaseTaskHandler):
                for method in v.Methods:
                    self.handlers[method] = v

    def scanPlugin(self, plugin):
        """Find task handlers in a plugin"""
        self.findHandlers(vars(plugin))

    def shutdown(self):
        """Attempt to shut down cleanly"""
        for task_id in self.pids.keys():
            self.cleanupTask(task_id)
        self.session.host.freeTasks(self.tasks.keys())
        self.session.host.updateHost(task_load=0.0,ready=False)

    def updateBuildroots(self):
        """Handle buildroot cleanup/maintenance

        - examine current buildroots on system
        - compare with db
        - clean up as needed
            - /var/lib/mock
            - /etc/mock/koji
        """
        local_br = self._scanLocalBuildroots()
        #query buildroots in db that are not expired
        states = [ koji.BR_STATES[x] for x in ('INIT','WAITING','BUILDING') ]
        db_br = self.session.listBuildroots(hostID=self.host_id,state=tuple(states))
        # index by id
        db_br = dict([(row['id'],row) for row in db_br])
        st_expired = koji.BR_STATES['EXPIRED']
        for id, br in db_br.items():
            task_id = br['task_id']
            if task_id is None:
                # not associated with a task
                # this makes no sense now, but may in the future
                self.logger.warn("Expiring taskless buildroot: %(id)i/%(tag_name)s/%(arch)s" % br)
                self.session.host.setBuildRootState(id,st_expired)
            elif not self.tasks.has_key(task_id):
                #task not running - expire the buildroot
                #TODO - consider recycling hooks here (with strong sanity checks)
                self.logger.info("Expiring buildroot: %(id)i/%(tag_name)s/%(arch)s" % br)
                self.logger.debug("Buildroot task: %r, Current tasks: %r" % (task_id,self.tasks.keys()))
                self.session.host.setBuildRootState(id,st_expired)
                continue
        # get info on local_only buildroots (most likely expired)
        local_only = [id for id in local_br.iterkeys() if not db_br.has_key(id)]
        if local_only:
            missed_br = self.session.listBuildroots(buildrootID=tuple(local_only))
            #get all the task info in one call
            tasks = []
            for br in missed_br:
                task_id = br['task_id']
                if task_id:
                    tasks.append(task_id)
            #index
            missed_br = dict([(row['id'],row) for row in missed_br])
            tasks = dict([(row['id'],row) for row in self.session.getTaskInfo(tasks)])
            for id in local_only:
                # Cleaning options
                #   - wait til later
                #   - "soft" clean (leaving empty root/ dir)
                #   - full removal
                data = local_br[id]
                br = missed_br.get(id)
                if not br:
                    self.logger.warn("%(name)s: not in db" % data)
                    continue
                desc = "%(id)i/%(tag_name)s/%(arch)s" % br
                if not br['retire_ts']:
                    self.logger.warn("%s: no retire timestamp" % desc)
                    continue
                age = time.time() - br['retire_ts']
                self.logger.debug("Expired/stray buildroot: %s" % desc)
                if br and br['task_id']:
                    task = tasks.get(br['task_id'])
                    if not task:
                        self.logger.warn("%s: invalid task %s" % (desc, br['task_id']))
                        continue
                    if (task['state'] == koji.TASK_STATES['FAILED'] and age < 3600 * 4):
                        #XXX - this could be smarter
                        # keep buildroots for failed tasks around for a little while
                        self.logger.debug("Keeping failed buildroot: %s" % desc)
                        continue
                topdir = data['dir']
                rootdir = None
                if topdir:
                    rootdir = "%s/root" % topdir
                    try:
                        st = os.lstat(rootdir)
                    except OSError, e:
                        if e.errno == errno.ENOENT:
                            rootdir = None
                        else:
                            self.logger.warn("%s: %s" % (desc, e))
                            continue
                    else:
                        age = min(age, time.time() - st.st_mtime)
                #note: https://bugzilla.redhat.com/bugzilla/show_bug.cgi?id=192153)
                #If rpmlib is installing in this chroot, removing it entirely
                #can lead to a world of hurt.
                #We remove the rootdir contents but leave the rootdir unless it
                #is really old
                if age > 3600*24:
                    #dir untouched for a day
                    self.logger.info("Removing buildroot: %s" % desc)
                    if topdir and safe_rmtree(topdir, unmount=True, strict=False) != 0:
                        continue
                    #also remove the config
                    try:
                        os.unlink(data['cfg'])
                    except OSError, e:
                        self.logger.warn("%s: can't remove config: %s" % (desc, e))
                elif age > 120:
                    if rootdir:
                        try:
                            flist = os.listdir(rootdir)
                        except OSError, e:
                            self.logger.warn("%s: can't list rootdir: %s" % (desc, e))
                            continue
                        if flist:
                            self.logger.info("%s: clearing rootdir" % desc)
                        for fn in flist:
                            safe_rmtree("%s/%s" % (rootdir,fn), unmount=True, strict=False)
                        resultdir = "%s/result" % topdir
                        if os.path.isdir(resultdir):
                            self.logger.info("%s: clearing resultdir" % desc)
                            safe_rmtree(resultdir, unmount=True, strict=False)
                else:
                    self.logger.debug("Recent buildroot: %s: %i seconds" % (desc,age))
        self.logger.debug("Local buildroots: %d" % len(local_br))
        self.logger.debug("Active buildroots: %d" % len(db_br))
        self.logger.debug("Expired/stray buildroots: %d" % len(local_only))

    def _scanLocalBuildroots(self):
        #XXX
        configdir = '/etc/mock/koji'
        buildroots = {}
        for f in os.listdir(configdir):
            if not f.endswith('.cfg'):
                continue
            fn = "%s/%s" % (configdir,f)
            if not os.path.isfile(fn):
                continue
            fo = file(fn,'r')
            id = None
            name = None
            for n in xrange(10):
                # data should be in first few lines
                line = fo.readline()
                if line.startswith('# Koji buildroot id:'):
                    try:
                        id = int(line.split(':')[1])
                    except (ValueError, IndexError):
                        continue
                if line.startswith('# Koji buildroot name:'):
                    try:
                        name = line.split(':')[1].strip()
                    except (ValueError, IndexError):
                        continue
            if id is None or name is None:
                continue
            # see if there's a dir for the buildroot
            vardir = "/var/lib/mock/%s" % name
            #XXX
            buildroots[id] = {}
            buildroots[id]['name'] = name
            buildroots[id]['cfg'] = fn
            buildroots[id]['dir'] = None
            if os.path.isdir(vardir):
                buildroots[id]['dir'] = vardir
        return buildroots

    def updateTasks(self):
        """Read and process task statuses from server

        The processing we do is:
            1) clean up after tasks that are not longer active:
                * kill off processes
                * retire buildroots
                * remove buildroots
                    - with some possible exceptions
            2) wake waiting tasks if appropriate
        """
        tasks = {}
        stale = []
        task_load = 0.0
        if self.pids:
            self.logger.info("pids: %r" % self.pids)
        for task in self.session.host.getHostTasks():
            self.logger.info("open task: %r" % task)
            # the tasks returned are those that are open and locked
            # by this host.
            id = task['id']
            if not self.pids.has_key(id):
                #We don't have a process for this
                #Expected to happen after a restart, otherwise this is an error
                stale.append(id)
                continue
            tasks[id] = task
            if task.get('alert',False):
                #wake up the process
                self.logger.info("Waking up task: %r" % task)
                os.kill(self.pids[id],signal.SIGUSR2)
            if not task['waiting']:
                task_load += task['weight']
        self.logger.debug("Task Load: %s" % task_load)
        self.task_load = task_load
        self.tasks = tasks
        self.logger.debug("Current tasks: %r" % self.tasks)
        if len(stale) > 0:
            #A stale task is one which is opened to us, but we know nothing
            #about). This will happen after a daemon restart, for example.
            self.logger.info("freeing stale tasks: %r" % stale)
            self.session.host.freeTasks(stale)
        for id, pid in self.pids.items():
            if self._waitTask(id, pid):
                # the subprocess handles most everything, we just need to clear things out
                if self.cleanupTask(id, wait=False):
                    del self.pids[id]
                if self.tasks.has_key(id):
                    del self.tasks[id]
        for id, pid in self.pids.items():
            if not tasks.has_key(id):
                # expected to happen when:
                #  - we are in the narrow gap between the time the task
                #    records its result and the time the process actually
                #    exits.
                #  - task is canceled
                #  - task is forcibly reassigned/unassigned
                tinfo = self.session.getTaskInfo(id)
                if tinfo is None:
                    raise koji.GenericError, "Invalid task %r (pid %r)" % (id,pid)
                elif tinfo['state'] == koji.TASK_STATES['CANCELED']:
                    self.logger.info("Killing canceled task %r (pid %r)" % (id,pid))
                    if self.cleanupTask(id):
                        del self.pids[id]
                elif tinfo['host_id'] != self.host_id:
                    self.logger.info("Killing reassigned task %r (pid %r)" % (id,pid))
                    if self.cleanupTask(id):
                        del self.pids[id]
                else:
                    self.logger.info("Lingering task %r (pid %r)" % (id,pid))

    def getNextTask(self):
        self.ready = self.readyForTask()
        self.session.host.updateHost(self.task_load,self.ready)
        if not self.ready:
            self.logger.info("Not ready for task")
            return False
        hosts, tasks = self.session.host.getLoadData()
        self.logger.debug("Load Data:")
        self.logger.debug("  hosts: %r" % hosts)
        self.logger.debug("  tasks: %r" % tasks)
        #now we organize this data into channel-arch bins
        bin_hosts = {}  #hosts indexed by bin
        bins = {}       #bins for this host
        our_avail = None
        for host in hosts:
            host['bins'] = []
            if host['id'] == self.host_id:
                #note: task_load reported by server might differ from what we
                #sent due to precision variation
                our_avail = host['capacity'] - host['task_load']
            for chan in host['channels']:
                for arch in host['arches'].split() + ['noarch']:
                    bin = "%s:%s" % (chan,arch)
                    bin_hosts.setdefault(bin,[]).append(host)
                    if host['id'] == self.host_id:
                        bins[bin] = 1
        self.logger.debug("bins: %r" % bins)
        if our_avail is None:
            self.logger.info("Server did not report this host. Are we disabled?")
            return False
        elif not bins:
            self.logger.info("No bins for this host. Missing channel/arch config?")
            return False
        #sort available capacities for each of our bins
        avail = {}
        for bin in bins.iterkeys():
            avail[bin] = [host['capacity'] - host['task_load'] for host in bin_hosts[bin]]
            avail[bin].sort()
            avail[bin].reverse()
        for task in tasks:
            # note: tasks are in priority order
            self.logger.debug("task: %r" % task)
            if task['method'] not in self.handlers:
                self.logger.warn("Skipping task %(id)i, no handler for method %(method)s", task)
                continue
            if self.tasks.has_key(task['id']):
                # we were running this task, but it apparently has been
                # freed or reassigned. We can't do anything with it until
                # updateTasks notices this and cleans up.
                self.logger.debug("Task %(id)s freed or reassigned", task)
                continue
            if task['state'] == koji.TASK_STATES['ASSIGNED']:
                self.logger.debug("task is assigned")
                if self.host_id == task['host_id']:
                    #assigned to us, we can take it regardless
                    if self.takeTask(task):
                        return True
            elif task['state'] == koji.TASK_STATES['FREE']:
                bin = "%(channel_id)s:%(arch)s" % task
                self.logger.debug("task is free, bin=%r" % bin)
                if not bins.has_key(bin):
                    continue
                #see where our available capacity is compared to other hosts for this bin
                #(note: the hosts in this bin are exactly those that could
                #accept this task)
                bin_avail = avail.get(bin, [0])
                self.logger.debug("available capacities for bin: %r" % bin_avail)
                median = bin_avail[(len(bin_avail)-1)/2]
                self.logger.debug("ours: %.2f, median: %.2f" % (our_avail, median))
                if not self.checkRelAvail(bin_avail, our_avail):
                    #decline for now and give the upper half a chance
                    return False
                #otherwise, we attempt to open the task
                if self.takeTask(task):
                    return True
            else:
                #should not happen
                raise Exception, "Invalid task state reported by server"
        return False

    def checkRelAvail(self, bin_avail, avail):
        """
        Check our available capacity against the capacity of other hosts in this bin.
        Return True if we should take a task, False otherwise.
        """
        median = bin_avail[(len(bin_avail)-1)/2]
        self.logger.debug("ours: %.2f, median: %.2f" % (avail, median))
        if avail >= median:
            return True
        else:
            self.logger.debug("Skipping - available capacity in lower half")
            return False

    def _waitTask(self, task_id, pid=None):
        """Wait (nohang) on the task, return true if finished"""
        if pid is None:
            pid = self.pids.get(task_id)
            if not pid:
                raise koji.GenericError, "No pid for task %i" % task_id
        prefix = "Task %i (pid %i)" % (task_id, pid)
        try:
            (childpid, status) = os.waitpid(pid, os.WNOHANG)
        except OSError, e:
            #check errno
            if e.errno != errno.ECHILD:
                #should not happen
                raise
            #otherwise assume the process is gone
            self.logger.info("%s: %s" % (prefix, e))
            return True
        if childpid != 0:
            self.logger.info(parseStatus(status, prefix))
            return True
        return False

    def _doKill(self, task_id, pid, cmd, sig, timeout, pause):
        """
        Kill the process with the given process ID.
        Return True if the process is successfully killed in
        the given timeout, False otherwise.
        """
        self.logger.info('Checking "%s" (pid %i, taskID %i)...' % (cmd, pid, task_id))
        execname = cmd.split()[0]
        signaled = False
        t = 0.0
        while True:
            status = self._getStat(pid)
            if status and status[1] == cmd and status[2] != 'Z':
                self.logger.info('%s (pid %i, taskID %i) is running' % (execname, pid, task_id))
            else:
                if signaled:
                    self.logger.info('%s (pid %i, taskID %i) was killed by signal %i' % (execname, pid, task_id, sig))
                else:
                    self.logger.info('%s (pid %i, taskID %i) exited' % (execname, pid, task_id))
                return True

            if t >= timeout:
                self.logger.warn('Failed to kill %s (pid %i, taskID %i) with signal %i' %
                                 (execname, pid, task_id, sig))
                return False

            try:
                os.kill(pid, sig)
            except OSError, e:
                # process probably went away, we'll find out on the next iteration
                self.logger.info('Error sending signal %i to %s (pid %i, taskID %i): %s' %
                                 (sig, execname, pid, task_id, e))
            else:
                signaled = True
                self.logger.info('Sent signal %i to %s (pid %i, taskID %i)' %
                                 (sig, execname, pid, task_id))

            time.sleep(pause)
            t += pause

    def _getStat(self, pid):
        """
        Get the stat info for the given pid.
        Return a list of all the fields in /proc/<pid>/stat.
        The second entry will contain the full command-line instead of
        just the command name.
        If the process does not exist, return None.
        """
        try:
            proc_path = '/proc/%i/stat' % pid
            if not os.path.isfile(proc_path):
                return None
            proc_file = file(proc_path)
            procstats = [not field.isdigit() and field or int(field) for field in proc_file.read().split()]
            proc_file.close()

            cmd_path = '/proc/%i/cmdline' % pid
            if not os.path.isfile(cmd_path):
                return None
            cmd_file = file(cmd_path)
            procstats[1] = cmd_file.read().replace('\0', ' ').strip()
            cmd_file.close()
            if not procstats[1]:
                return None

            return procstats
        except IOError, e:
            # process may have already gone away
            return None

    def _childPIDs(self, pid):
        """Recursively get the children of the process with the given ID.
        Return a list containing the process IDs of the children
        in breadth-first order, without duplicates."""
        statsByPPID = {}
        pidcmd = None
        for procdir in os.listdir('/proc'):
            if not procdir.isdigit():
                continue
            procid = int(procdir)
            procstats = self._getStat(procid)
            if not procstats:
                continue
            statsByPPID.setdefault(procstats[3], []).append(procstats)
            if procid == pid:
                pidcmd = procstats[1]

        pids = []
        if pidcmd:
            # only append the pid if it still exists
            pids.append((pid, pidcmd))

        parents = [pid]
        while parents:
            for ppid in parents[:]:
                for procstats in statsByPPID.get(ppid, []):
                    # get the /proc entries with ppid as their parent, and append their pid to the list,
                    # then recheck for their children
                    # pid is the 0th field, ppid is the 3rd field
                    pids.append((procstats[0], procstats[1]))
                    parents.append(procstats[0])
                parents.remove(ppid)

        return pids

    def _killChildren(self, task_id, children, sig=signal.SIGTERM, timeout=2.0, pause=1.0):
        """
        Kill child processes of the given task, as specified in the children list,
        by sending sig.
        Retry every pause seconds, within timeout.
        Remove successfully killed processes from the "children" list.
        """
        for childpid, cmd in children[::-1]:
            # iterate in reverse order so processes whose children are killed might have
            # a chance to cleanup before they're killed
            if self._doKill(task_id, childpid, cmd, sig, timeout, pause):
                children.remove((childpid, cmd))

    def cleanupTask(self, task_id, wait=True):
        """Clean up after task

        - kill children
        - expire session

        Return True if all children were successfully killed, False otherwise.
        """
        pid = self.pids.get(task_id)
        if not pid:
            raise koji.GenericError, "No pid for task %i" % task_id
        children = self._childPIDs(pid)
        if children:
            # send SIGINT once to let mock mock try to clean up
            self._killChildren(task_id, children, sig=signal.SIGINT, pause=3.0)
        if children:
            self._killChildren(task_id, children)
        if children:
            self._killChildren(task_id, children, sig=signal.SIGKILL, timeout=3.0)

        #expire the task's subsession
        session_id = self.subsessions.get(task_id)
        if session_id:
            self.logger.info("Expiring subsession %i (task %i)" % (session_id, task_id))
            try:
                self.session.logoutChild(session_id)
                del self.subsessions[task_id]
            except:
                #not much we can do about it
                pass
        if wait:
            return self._waitTask(task_id, pid)
        else:
            # task has already been waited on, and we've cleaned
            # up as much as we can
            return True

    def checkSpace(self):
        """See if we have enough space to accept another job"""
        br_path = self.options.mockdir
        if not os.path.exists(br_path):
            self.logger.error("No such directory: %s" % br_path)
            raise IOError, "No such directory: %s" % br_path
        fs_stat = os.statvfs(br_path)
        available = fs_stat.f_bavail * fs_stat.f_bsize
        availableMB = available / 1024 / 1024
        self.logger.debug("disk space available in '%s': %i MB", br_path, availableMB)
        if availableMB < self.options.minspace:
            self.status = "Insufficient disk space: %i MB, %i MB required" % (availableMB, self.options.minspace)
            self.logger.warn(self.status)
            return False
        return True

    def readyForTask(self):
        """Determine if the system is ready to accept a new task.

        This function measures the system load and tries to determine
        if there is room to accept a new task."""
        #       key resources to track:
        #               disk_space
        #                       df -P path
        #                       df -iP path ?
        #               memory (meminfo/vmstat)
        #                       vmstat fields 3-6 (also 7-8 for swap)
        #                       http://www.redhat.com/advice/tips/meminfo.html
        #               cpu cycles (vmstat?)
        #                       vmstat fields 13-16 (and others?)
        #       others?:
        #               io (iostat/vmstat)
        #               network (netstat?)
        if self.restart_pending:
            if self.tasks:
                return False
            else:
                raise koji.tasks.ServerRestart
        self.hostdata = self.session.host.getHost()
        self.logger.debug('hostdata: %r' % self.hostdata)
        if not self.hostdata['enabled']:
            self.status = "Host is disabled"
            self.logger.info(self.status)
            return False
        if self.task_load > self.hostdata['capacity']:
            self.status = "Over capacity"
            self.logger.info("Task load (%.2f) exceeds capacity (%.2f)" % (self.task_load, self.hostdata['capacity']))
            return False
        if len(self.tasks) >= self.options.maxjobs:
            # This serves as a backup to the capacity check and prevents
            # a tremendous number of low weight jobs from piling up
            self.status = "Full queue"
            self.logger.info(self.status)
            return False
        if not self.checkSpace():
            # checkSpace() does its own logging
            return False
        loadavgs = os.getloadavg()
        # this likely treats HT processors the same as real ones
        # but that's fine, it's a conservative test
        maxload = 4.0 * os.sysconf('SC_NPROCESSORS_ONLN')
        if loadavgs[0] > maxload:
            self.status = "Load average %.2f > %.2f" % (loadavgs[0], maxload)
            self.logger.info(self.status)
            return False
        #XXX - add more checks
        return True

    def takeTask(self,task):
        """Attempt to open the specified task

        Returns True if successful, False otherwise
        """
        self.logger.info("Attempting to take task %s" % task['id'])
        if task['method'] in ('buildArch', 'buildSRPMFromSCM', 'buildMaven') and \
               task['arch'] == 'noarch':
            task_info = self.session.getTaskInfo(task['id'], request=True)
            if task['method'] == 'buildMaven':
                tag = task_info['request'][1]
            else:
                tag_id = task_info['request'][1]
                tag = self.session.getTag(tag_id)
            if tag and tag['arches']:
                tag_arches = [koji.canonArch(a) for a in tag['arches'].split()]
                host_arches = self.hostdata['arches'].split()
                if not set(tag_arches).intersection(host_arches):
                    self.logger.info('Skipping task %s (%s) because tag arches (%s) and ' \
                                     'host arches (%s) are disjoint' % \
                                     (task['id'], task['method'],
                                      ', '.join(tag_arches), ', '.join(host_arches)))
                    return False
        data = self.session.host.openTask(task['id'])
        if data is None:
            self.logger.warn("Could not open")
            return False
        if not data.has_key('request') or data['request'] is None:
            self.logger.warn("Task '%s' has no request" % task['id'])
            return False
        id = data['id']
        request = data['request']
        self.tasks[id] = data
        params, method = xmlrpclib.loads(request)
        if self.handlers.has_key(method):
            handlerClass = self.handlers[method]
        else:
            raise koji.GenericError, "No handler found for method '%s'" % method
        handler = handlerClass(id,method,params,self.session,self.options)
        # set weight
        self.session.host.setTaskWeight(id,handler.weight())
        if handler.Foreground:
            self.logger.info("running task in foreground")
            handler.setManager(self)
            self.runTask(handler)
        else:
            pid, session_id = self.forkTask(handler)
            self.pids[id] = pid
            self.subsessions[id] = session_id
        return True

    def forkTask(self,handler):
        #get the subsession before we fork
        newhub = self.session.subsession()
        session_id = newhub.sinfo['session-id']
        pid = os.fork()
        if pid:
            newhub._forget()
            return pid, session_id
        #in no circumstance should we return after the fork
        #nor should any exceptions propagate past here
        try:
            self.session._forget()
            #set process group
            os.setpgrp()
            #use the subsession
            self.session = newhub
            handler.session = self.session
            #set a do-nothing handler for sigusr2
            signal.signal(signal.SIGUSR2,lambda *args: None)
            self.runTask(handler)
        finally:
            #diediedie
            try:
                self.session.logout()
            finally:
                os._exit(0)

    def runTask(self,handler):
        fail = False
        try:
            response = (handler.run(),)
            # note that we wrap response in a singleton tuple
            response = xmlrpclib.dumps(response, methodresponse=1, allow_none=1)
            self.logger.info("RESPONSE: %r" % response)
        except xmlrpclib.Fault, fault:
            fail = True
            response = xmlrpclib.dumps(fault)
            tb = ''.join(traceback.format_exception(*sys.exc_info())).replace(r"\n", "\n")
            self.logger.warn("FAULT:\n%s" % tb)
        except (SystemExit,koji.tasks.ServerExit,KeyboardInterrupt):
            #we do not trap these
            raise
        except koji.tasks.ServerRestart:
            #freeing this task will allow the pending restart to take effect
            self.session.host.freeTasks([handler.id])
            return
        except:
            tb = ''.join(traceback.format_exception(*sys.exc_info()))
            self.logger.warn("TRACEBACK: %s" % tb)
            fail = True
            # report exception back to server
            e_class, e = sys.exc_info()[:2]
            faultCode = getattr(e_class,'faultCode',1)
            if issubclass(e_class, koji.GenericError):
                #just pass it through
                tb = str(e)
            response = xmlrpclib.dumps(xmlrpclib.Fault(faultCode, tb))

        if fail:
            self.session.host.failTask(handler.id, response)
        else:
            self.session.host.closeTask(handler.id, response)
