# Code shared by various Koji daemons

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

from __future__ import absolute_import, division

import errno
import hashlib
import logging
import os
import re
import signal
import subprocess
import sys
import time
import traceback
from fnmatch import fnmatch

import six
from six.moves import range, urllib

import koji
import koji.tasks
import koji.xmlrpcplus
from koji.tasks import safe_rmtree
from koji.util import (
    adler32_constructor,
    base64encode,
    dslice,
    parseStatus,
    to_list,
    joinpath,
)


def incremental_upload(session, fname, fd, path, retries=5, logger=None):
    if not fd:
        return

    if logger is None:
        logger = logging.getLogger('koji.daemon')

    if session.opts.get('use_fast_upload'):
        fast_incremental_upload(session, fname, fd, path, retries, logger)
        return

    while True:
        offset = fd.tell()
        contents = fd.read(65536)
        size = len(contents)
        if size == 0:
            break

        data = base64encode(contents)
        digest = hashlib.sha256(contents).hexdigest()
        del contents

        tries = 0
        while True:
            if session.uploadFile(path, fname, size, ("sha256", digest), offset, data):
                break

            if tries <= retries:
                tries += 1
                time.sleep(10)
                continue
            else:
                logger.error("Error uploading file %s to %s at offset %d" % (fname, path, offset))
                break


def fast_incremental_upload(session, fname, fd, path, retries, logger):
    """Like incremental_upload, but use the fast upload mechanism"""

    while True:
        offset = fd.tell()
        contents = fd.read(65536)
        if not contents:
            break
        hexdigest = adler32_constructor(contents).hexdigest()

        tries = 0
        while True:
            result = session.rawUpload(contents, offset, path, fname, overwrite=True)
            if result['hexdigest'] == hexdigest:
                break

            if tries <= retries:
                tries += 1
                time.sleep(10)
                continue
            else:
                logger.error("Error uploading file %s to %s at offset %d" % (fname, path, offset))
                break


def log_output(session, path, args, outfile, uploadpath, cwd=None, logerror=0, append=0,
               chroot=None, env=None):
    """Run command with output redirected. If chroot is not None, chroot to the directory specified
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
            fd = os.open(outfile, flags, 0o666)
            os.dup2(fd, 1)
            if logerror:
                os.dup2(fd, 2)
            # echo the command we're running into the logfile
            msg = '$ %s\n' % ' '.join(args)
            if six.PY3:
                msg = msg.encode('utf-8')
            os.write(fd, msg)
            environ = os.environ.copy()
            if env:
                environ.update(env)
            os.execvpe(path, args, environ)
        except BaseException:
            msg = ''.join(traceback.format_exception(*sys.exc_info()))
            if fd:
                try:
                    if six.PY3:
                        os.write(fd, msg.encode('utf-8'))
                    else:
                        os.write(fd, msg)
                    os.close(fd)
                except Exception:
                    pass
            print(msg)
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
                    outfd = open(outfile, 'rb')
                except IOError:
                    # will happen if the forked process has not created the logfile yet
                    continue
                except Exception:
                    print('Error reading log file: %s' % outfile)
                    print(''.join(traceback.format_exception(*sys.exc_info())))

            incremental_upload(session, remotename, outfd, uploadpath)

            if status[0] != 0:
                if outfd:
                    outfd.close()
                return status[1]


# BEGIN kojikamid dup #

class SCM(object):
    "SCM abstraction class"

    types = {'CVS': ('cvs://',),
             'CVS+SSH': ('cvs+ssh://',),
             'GIT': ('git://', 'git+http://', 'git+https://', 'git+rsync://'),
             'GIT+SSH': ('git+ssh://',),
             'SVN': ('svn://', 'svn+http://', 'svn+https://'),
             'SVN+SSH': ('svn+ssh://',)}

    @classmethod
    def is_scm_url(cls, url, strict=False):
        """
        Return True if the url appears to be a valid, accessible source location, False otherwise
        """
        schemes = [s for t in cls.types for s in cls.types[t]]
        for scheme in schemes:
            if url.startswith(scheme):
                return True
        # otherwise not valid
        if strict:
            raise koji.GenericError('Invalid scheme in scm url. Valid schemes '
                                    'are: %s' % ' '.join(sorted(schemes)))
        else:
            return False

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

        if not SCM.is_scm_url(url, strict=True):
            raise koji.GenericError('Invalid SCM URL: %s' % url)

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
        else:   # pragma: no cover
            # should never happen
            raise koji.GenericError('Invalid SCM URL: %s' % url)

    def get_info(self, keys=None):
        if keys is None:
            keys = ["url", "scheme", "user", "host", "repository", "module", "revision", "scmtype"]
        return dslice(vars(self), keys)

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
        dummyscheme, netloc, path, params, query, fragment = urllib.parse.urlparse(dummyurl)

        user = None
        userhost = netloc.split('@')
        if len(userhost) == 2:
            user = userhost[0]
            if not user:
                # Don't return an empty string
                user = None
            elif ':' in user:
                raise koji.GenericError('username:password format not supported: %s' % user)
            netloc = userhost[1]
        elif len(userhost) > 2:
            raise koji.GenericError('Invalid username@hostname specified: %s' % netloc)
        if not netloc:
            raise koji.GenericError(
                'Unable to parse SCM URL: %s . Could not find the netloc element.' % self.url)

        # check for empty path before we apply normpath
        if not path:
            raise koji.GenericError(
                'Unable to parse SCM URL: %s . Could not find the path element.' % self.url)

        path = os.path.normpath(path)

        # path and query should not end with /
        path = path.rstrip('/')
        query = query.rstrip('/')
        # normpath might not strip // at start of path
        if path.startswith('//'):
            path = '/' + path.strip('/')
        # path should start with /
        if not path.startswith('/'):  # pragma: no cover
            # any such url should have already been caught by is_scm_url
            raise koji.GenericError('Invalid SCM URL. Path should begin with /: %s) ')

        # check for validity: params should be empty, query may be empty, everything else should be
        # populated
        if params:
            raise koji.GenericError(
                'Unable to parse SCM URL: %s . Params element %s should be empty.' %
                (self.url, params))
        if not scheme:  # pragma: no cover
            # should not happen because of is_scm_url check earlier
            raise koji.GenericError(
                'Unable to parse SCM URL: %s . Could not find the scheme element.' % self.url)
        if not fragment:
            raise koji.GenericError(
                'Unable to parse SCM URL: %s . Could not find the fragment element.' % self.url)

        # return parsed values
        return (scheme, user, netloc, path, query, fragment)

    def assert_allowed(self, allowed='', session=None, by_config=True, by_policy=False,
                       policy_data=None):
        """
        Check whether this scm is allowed and apply options by either/both approach below:

            - "allowed_scms" from config file, see
              :func:`~koji.daemon.SCM.assert_allowed_by_config`
            - "build_from_scm" hub policy, see :func:`~koji.daemon.SCM.assert_allowed_by_policy`

        When both approaches are applied, the config one will be applied, then the policy one.

        :param str allowed: The allowed_scms config content which is used for by-config approach
        :param koji.ClientSession session: The allowed_scms config content which is used for
                                           by-policy approach
        :param bool by_config: Using config or not, Default: True
        :param bool by_policy: Using policy or not, Default: False
        :param dict policy_data: The policy data which will be merged with the generated scm info,
                                 then will be passed to hub call for policy assertion when using
                                 policy.
        :raises koji.BuildError: if the scm is denied.
        """
        if by_config:
            self.assert_allowed_by_config(allowed or '')
        if by_policy:
            if session is None:
                raise koji.ConfigurationError(
                    'When allowed SCM assertion is by policy, session must be passed in.')
            self.assert_allowed_by_policy(session, **(policy_data or {}))

    def assert_allowed_by_config(self, allowed):
        """
        Check this scm against allowed list and apply options

        allowed is a space-separated list of entries in one of the following
        forms:

            host:repository[:use_common[:source_cmd]]
            !host:repository

        Incorrectly-formatted entries will be skipped with a warning.

        The first form allows a host:repository pattern and optionally sets a
        few options for it.

        The second form explicitly blocks a host:repository pattern

        Both host and repository are treated as glob patterns

        If there is a matching entry, then the optional fields, if given, will
        be applied to the instance.

        If there is no matching entry, or if the host:repository is blocked
        then BuildError is raised.

        The use_common option defaults to on.  If it is set to no, off, false
        or 0, it will be disabled.  If the option is on, then kojid will
        attempt to checkout a common/ directory from the repository.

        The source_command is a shell command to be run before building the
        srpm.  It defaults to "make sources".  This can be overridden by the
        matching allowed entry.  The command must be encoded with commas
        instead of spaces (e.g. "make,sources").
        """
        is_allowed = False
        for allowed_scm in allowed.split():
            scm_tuple = allowed_scm.split(':')
            if len(scm_tuple) < 2:
                self.logger.warning('Ignoring incorrectly formatted SCM host:repository: %s' %
                                    allowed_scm)
                continue
            host_pat = scm_tuple[0]
            repo_pat = scm_tuple[1]
            invert = False
            if host_pat.startswith('!'):
                invert = True
                host_pat = host_pat[1:]
            if fnmatch(self.host, host_pat) and fnmatch(self.repository, repo_pat):
                # match
                if invert:
                    break
                is_allowed = True
                # check if we specify a value for use_common
                if len(scm_tuple) >= 3:
                    if scm_tuple[2].lower() in ('no', 'off', 'false', '0'):
                        self.use_common = False
                # check if we specify a custom source_cmd
                if len(scm_tuple) >= 4:
                    if scm_tuple[3]:
                        self.source_cmd = scm_tuple[3].split(',')
                    else:
                        # there was nothing after the trailing :,
                        # so they don't want to run a source_cmd at all
                        self.source_cmd = None
                break
        if not is_allowed:
            raise koji.BuildError(
                '%s:%s is not in the list of allowed SCMs' % (self.host, self.repository))

    def assert_allowed_by_policy(self, session, **extra_data):
        """
        Check this scm against hub policy: build_from_scm and apply options

        The policy data is the combination of scminfo with scm_ prefix and kwargs.
        It should at least contain following keys:

            - scm_url
            - scm_scheme
            - scm_user
            - scm_host
            - scm_repository
            - scm_module
            - scm_revision
            - scm_type

        More keys could be added as kwargs(extra_data). You can pass any reasonable data which
        could be handled by policy tests, like:

            - scratch (if the task is scratch)
            - channel (which channel the task is assigned)
            - user_id (the task owner)

        If the key in extra_data is one of scm_* listed above, it will override the one generated
        from scminfo.

        The format of the action returned from build_from_scm could be one of following forms::

            allow [use_common] [<source_cmd>]
            deny [<reason>]

        If use_common is not set, use_common property is False.
        If source_cmd is none, it will be parsed as None. If it not set, the default value:
        ['make', 'sources'], or the value set by :func:`~koji.daemon.SCM.assert_allowed_by_config`
        will be set.

        Policy example:

            build_from_scm =
                bool scratch :: allow none
                match scm_host scm.example.com :: allow use_common make sources
                match scm_host scm2.example.com :: allow
                all :: deny


        :param koji.ClientSession session: the session object to call hub xmlrpc APIs.
                                           It should be a host session.

        :raises koji.BuildError: if the scm is denied.
        """
        policy_data = {}
        for k, v in six.iteritems(self.get_info()):
            policy_data[re.sub(r'^(scm_?)?', 'scm_', k)] = v
        policy_data.update(extra_data)
        result = (session.evalPolicy('build_from_scm', policy_data) or '').split()
        is_allowed = result and result[0].lower() in ('yes', 'true', 'allow', 'allowed')
        if not is_allowed:
            raise koji.BuildError(
                'SCM: %s:%s is not allowed, reason: %s' % (self.host, self.repository,
                                                           ' '.join(result[1:]) or None))
        # Apply options when it's allowed
        applied = result[1:]
        self.use_common = len(applied) != 0 and applied[0].lower() == 'use_common'
        idx = 1 if self.use_common else 0
        self.source_cmd = applied[idx:] or self.source_cmd
        if self.source_cmd is not None and len(self.source_cmd) > 0 \
           and self.source_cmd[0].lower() == 'none':
            self.source_cmd = None

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
                # we've been inserted into kojikamid, use its run()
                return run(cmd, chdir=chdir, fatal=fatal, log=log)  # noqa: F821
            else:
                append = (_count[0] > 0)
                _count[0] += 1
                if log_output(session, cmd[0], cmd, logfile, uploadpath,
                              cwd=chdir, logerror=1, append=append, env=env):
                    raise koji.BuildError('Error running %s command "%s", see %s for details' %
                                          (self.scmtype, ' '.join(cmd), os.path.basename(logfile)))

        if self.scmtype == 'CVS':
            pserver = ':pserver:%s@%s:%s' % ((self.user or 'anonymous'), self.host,
                                             self.repository)
            module_checkout_cmd = ['cvs', '-d', pserver, 'checkout', '-r', self.revision,
                                   self.module]
            common_checkout_cmd = ['cvs', '-d', pserver, 'checkout', 'common']

        elif self.scmtype == 'CVS+SSH':
            if not self.user:
                raise koji.BuildError(
                    'No user specified for repository access scheme: %s' % self.scheme)

            cvsserver = ':ext:%s@%s:%s' % (self.user, self.host, self.repository)
            module_checkout_cmd = ['cvs', '-d', cvsserver, 'checkout', '-r', self.revision,
                                   self.module]
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

            # self.module may be empty, in which case the specfile should be in the top-level
            # directory
            if self.module:
                # Treat the module as a directory inside the git repository
                sourcedir = '%s/%s' % (sourcedir, self.module)

        elif self.scmtype == 'GIT+SSH':
            if not self.user:
                raise koji.BuildError(
                    'No user specified for repository access scheme: %s' % self.scheme)
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

            # self.module may be empty, in which case the specfile should be in the top-level
            # directory
            if self.module:
                # Treat the module as a directory inside the git repository
                sourcedir = '%s/%s' % (sourcedir, self.module)

        elif self.scmtype == 'SVN':
            scheme = self.scheme
            if '+' in scheme:
                scheme = scheme.split('+')[1]

            svnserver = '%s%s%s' % (scheme, self.host, self.repository)
            module_checkout_cmd = ['svn', 'checkout', '-r', self.revision,
                                   '%s/%s' % (svnserver, self.module), self.module]
            common_checkout_cmd = ['svn', 'checkout', '%s/common' % svnserver]

        elif self.scmtype == 'SVN+SSH':
            if not self.user:
                raise koji.BuildError(
                    'No user specified for repository access scheme: %s' % self.scheme)

            svnserver = 'svn+ssh://%s@%s%s' % (self.user, self.host, self.repository)
            module_checkout_cmd = ['svn', 'checkout', '-r', self.revision,
                                   '%s/%s' % (svnserver, self.module), self.module]
            common_checkout_cmd = ['svn', 'checkout', '%s/common' % svnserver]

        else:
            raise koji.BuildError('Unknown SCM type: %s' % self.scmtype)

        # perform checkouts
        _run(module_checkout_cmd, chdir=scmdir, fatal=True)

        if update_checkout_cmd:
            # Currently only required for GIT checkouts
            # Run the command in the directory the source was checked out into
            if self.scmtype.startswith('GIT') and globals().get('KOJIKAMID'):
                _run(['git', 'config', 'core.autocrlf', 'true'],
                     chdir=update_checkout_dir, fatal=True)
                _run(['git', 'config', 'core.safecrlf', 'true'],
                     chdir=update_checkout_dir, fatal=True)
            _run(update_checkout_cmd, chdir=update_checkout_dir, fatal=True)

        if self.use_common and not globals().get('KOJIKAMID'):
            _run(common_checkout_cmd, chdir=scmdir, fatal=True)
            if not os.path.exists('%s/../common' % sourcedir):
                # find the relative distance from sourcedir/../common to scmdir/common
                destdir = os.path.split(sourcedir)[0]
                path_comps = destdir[len(scmdir) + 1:]
                rel_path = '../' * len(path_comps.split('/'))
                os.symlink(rel_path + 'common', '%s/../common' % sourcedir)

        self.sourcedir = sourcedir
        return sourcedir

    def get_source(self):
        r = {
            'url': self.url,
            'source': '',
        }
        if self.scmtype.startswith('GIT'):
            cmd = ['git', 'rev-parse', 'HEAD']
            proc = subprocess.Popen(cmd, stdout=subprocess.PIPE,
                                    cwd=self.sourcedir,)
            out, _ = proc.communicate()
            status = proc.wait()
            if status != 0:
                raise koji.GenericError('Error getting commit hash for git')
            fragment = out.strip()
            if six.PY3:
                fragment = fragment.decode()
            scheme = self.scheme[:-3]
            netloc = self.host
            path = self.repository
            query = self.module
            r['source'] = urllib.parse.urlunsplit([scheme, netloc, path, query, fragment])
        else:
            # just use the same url
            r['source'] = self.url
        return r
# END kojikamid dup #


class TaskManager(object):

    def __init__(self, options, session):
        self.options = options
        self.session = session
        self.tasks = {}
        self.skipped_tasks = {}
        self.pids = {}
        self.subsessions = {}
        self.handlers = {}
        self.status = ''
        self.restart_pending = False
        self.ready = False
        self.hostdata = {}
        self.task_load = 0.0
        self.host_id = self.session.host.getID()
        self.start_ts = self.session.getSessionInfo()['start_ts']
        self.logger = logging.getLogger("koji.TaskManager")

    def findHandlers(self, vars):
        """Find and index task handlers"""
        for v in vars.values():
            self.registerHandler(v)

    def registerHandler(self, entry):
        """register and index task handler"""
        if isinstance(entry, type(koji.tasks.BaseTaskHandler)) and \
                issubclass(entry, koji.tasks.BaseTaskHandler):
            for method in entry.Methods:
                self.handlers[method] = entry

    def registerCallback(self, entry):
        """register and index callback plugins"""
        if callable(entry) and getattr(entry, 'callbacks', None):
            for cbtype in entry.callbacks:
                koji.plugin.register_callback(cbtype, entry)

    def registerEntries(self, vars):
        """Register task handlers and other plugins"""
        for v in vars.values():
            self.registerHandler(v)
            self.registerCallback(v)

    def scanPlugin(self, plugin):
        """Find task handlers in a plugin"""
        self.registerEntries(vars(plugin))

    def shutdown(self):
        """Attempt to shut down cleanly"""
        for task_id in self.pids:
            self.cleanupTask(task_id)
        self.session.host.freeTasks(to_list(self.tasks.keys()))
        self.session.host.updateHost(task_load=0.0, ready=False)

    def updateBuildroots(self, nolocal=False):
        """Handle buildroot cleanup/maintenance

        - examine current buildroots on system
        - compare with db
        - clean up as needed
            - /var/lib/mock
            - /etc/mock/koji

        If nolocal is True, do not try to scan local buildroots.
        """
        # query buildroots in db that are not expired
        states = [koji.BR_STATES[x] for x in ('INIT', 'WAITING', 'BUILDING')]
        db_br = self.session.listBuildroots(hostID=self.host_id, state=tuple(states))
        # index by id
        db_br = dict([(row['id'], row) for row in db_br])
        st_expired = koji.BR_STATES['EXPIRED']
        for id, br in db_br.items():
            task_id = br['task_id']
            if task_id is None:
                # not associated with a task
                # this makes no sense now, but may in the future
                self.logger.warning("Expiring taskless buildroot: %(id)i/%(tag_name)s/%(arch)s" %
                                    br)
                self.session.host.setBuildRootState(id, st_expired)
            elif task_id not in self.tasks:
                # task not running - expire the buildroot
                # TODO - consider recycling hooks here (with strong sanity checks)
                self.logger.info("Expiring buildroot: %(id)i/%(tag_name)s/%(arch)s" % br)
                self.logger.debug(
                    "Buildroot task: %r, Current tasks: %r" %
                    (task_id, to_list(self.tasks.keys())))
                self.session.host.setBuildRootState(id, st_expired)
                continue
        if nolocal:
            return
        local_br = self._scanLocalBuildroots()
        # get info on local_only buildroots (most likely expired)
        local_only = [id for id in local_br if id not in db_br]
        if local_only:
            missed_br = self.session.listBuildroots(buildrootID=tuple(local_only))
            # get all the task info in one call
            tasks = []
            for br in missed_br:
                task_id = br['task_id']
                if task_id:
                    tasks.append(task_id)
            # index
            missed_br = dict([(row['id'], row) for row in missed_br])
            tasks = dict([(row['id'], row) for row in self.session.getTaskInfo(tasks)])
            # go from +- oldest
            for id in sorted(local_only):
                # Cleaning options
                #   - wait til later
                #   - "soft" clean (leaving empty root/ dir)
                #   - full removal
                data = local_br[id]
                br = missed_br.get(id)
                if not br:
                    self.logger.warning("%(name)s: not in db" % data)
                    continue
                desc = "%(id)i/%(tag_name)s/%(arch)s" % br
                if not br['retire_ts']:
                    self.logger.warning("%s: no retire timestamp" % desc)
                    continue
                age = time.time() - br['retire_ts']
                self.logger.debug("Expired/stray buildroot: %s" % desc)
                if br and br['task_id']:
                    task = tasks.get(br['task_id'])
                    if not task:
                        self.logger.warning("%s: invalid task %s" % (desc, br['task_id']))
                        continue
                    if task['state'] == koji.TASK_STATES['FAILED'] and \
                            age < self.options.failed_buildroot_lifetime:
                        # XXX - this could be smarter
                        # keep buildroots for failed tasks around for a little while
                        if self.checkSpace():
                            # we can leave it in place, otherwise delete it
                            self.logger.debug("Keeping failed buildroot: %s" % desc)
                            continue
                topdir = data['dir']
                rootdir = None
                if topdir:
                    rootdir = "%s/root" % topdir
                    try:
                        st = os.lstat(rootdir)
                    except OSError as e:
                        if e.errno == errno.ENOENT:
                            rootdir = None
                        else:
                            self.logger.warning("%s: %s" % (desc, e))
                            continue
                    else:
                        age = min(age, time.time() - st.st_mtime)
                topdir_bootstrap = "%s-bootstrap" % topdir
                if not os.path.exists(topdir_bootstrap):
                    topdir_bootstrap = None
                # note: https://bugzilla.redhat.com/bugzilla/show_bug.cgi?id=192153)
                # If rpmlib is installing in this chroot, removing it entirely
                # can lead to a world of hurt.
                # We remove the rootdir contents but leave the rootdir unless it
                # is really old
                if age > self.options.buildroot_final_cleanup_delay:
                    # dir untouched for a day
                    self.logger.info("Removing buildroot: %s" % desc)
                    if ((topdir and safe_rmtree(topdir, unmount=True, strict=False) != 0) or
                        (topdir_bootstrap and
                            safe_rmtree(topdir_bootstrap, unmount=True, strict=False) != 0)):
                        continue
                    # also remove the config
                    try:
                        os.unlink(data['cfg'])
                    except OSError as e:
                        self.logger.warning("%s: can't remove config: %s" % (desc, e))
                elif age > self.options.buildroot_basic_cleanup_delay and rootdir:
                    for d in (topdir, topdir_bootstrap):
                        if not d:
                            continue
                        if d == topdir_bootstrap:
                            desc2 = "%s [bootstrap]" % desc
                        else:
                            desc2 = desc
                        rootdir = joinpath(d, 'root')
                        try:
                            flist = os.listdir(rootdir)
                        except OSError as e:
                            self.logger.warning("%s: can't list rootdir: %s" % (desc2, e))
                            continue
                        if flist:
                            self.logger.info("%s: clearing rootdir" % desc2)
                        for fn in flist:
                            safe_rmtree("%s/%s" % (rootdir, fn), unmount=True, strict=False)
                        # bootstrap's resultdir is 'results', so we try the best to remove both
                        # 'result(s)' dirs
                        for r in ('result', 'results'):
                            resultdir = "%s/%s" % (d, r)
                            if os.path.isdir(resultdir):
                                self.logger.info("%s: clearing resultdir: %s" % (desc2, resultdir))
                                safe_rmtree(resultdir, unmount=True, strict=False)
                else:
                    self.logger.debug("Recent buildroot: %s: %i seconds" % (desc, age))
        self.logger.debug("Local buildroots: %d" % len(local_br))
        self.logger.debug("Active buildroots: %d" % len(db_br))
        self.logger.debug("Expired/stray buildroots: %d" % len(local_only))

    def _scanLocalBuildroots(self):
        # XXX
        configdir = '/etc/mock/koji'
        buildroots = {}
        for f in os.listdir(configdir):
            if not f.endswith('.cfg'):
                continue
            fn = "%s/%s" % (configdir, f)
            if not os.path.isfile(fn):
                continue
            fo = koji._open_text_file(fn)
            id = None
            name = None
            for n in range(10):
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
            vardir = os.path.join(self.options.mockdir, name)
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
            if id not in self.pids:
                # We don't have a process for this
                # Expected to happen after a restart, otherwise this is an error
                stale.append(id)
                continue
            tasks[id] = task
            if task.get('alert', False):
                # wake up the process
                self.logger.info("Waking up task: %r" % task)
                os.kill(self.pids[id], signal.SIGUSR2)
            if not task['waiting']:
                task_load += task['weight']
        self.logger.debug("Task Load: %s" % task_load)
        self.task_load = task_load
        self.tasks = tasks
        self.logger.debug("Current tasks: %r" % self.tasks)
        if len(stale) > 0:
            # A stale task is one which is opened to us, but we know nothing
            # about). This will happen after a daemon restart, for example.
            self.logger.info("freeing stale tasks: %r" % stale)
            self.session.host.freeTasks(stale)
        for id, pid in list(self.pids.items()):
            if self._waitTask(id, pid):
                # the subprocess handles most everything, we just need to clear things out
                if self.cleanupTask(id, wait=False):
                    del self.pids[id]
                if id in self.tasks:
                    del self.tasks[id]
        for id, pid in list(self.pids.items()):
            if id not in tasks:
                # expected to happen when:
                #  - we are in the narrow gap between the time the task
                #    records its result and the time the process actually
                #    exits.
                #  - task is canceled
                #  - task is forcibly reassigned/unassigned
                tinfo = self.session.getTaskInfo(id)
                if tinfo is None:
                    raise koji.GenericError("Invalid task %r (pid %r)" % (id, pid))
                elif tinfo['state'] == koji.TASK_STATES['CANCELED']:
                    self.logger.info("Killing canceled task %r (pid %r)" % (id, pid))
                    if self.cleanupTask(id):
                        del self.pids[id]
                elif tinfo['host_id'] != self.host_id:
                    self.logger.info("Killing reassigned task %r (pid %r)" % (id, pid))
                    if self.cleanupTask(id):
                        del self.pids[id]
                else:
                    self.logger.info("Lingering task %r (pid %r)" % (id, pid))

    def getNextTask(self):
        self.ready = self.readyForTask()
        self.session.host.updateHost(self.task_load, self.ready)
        if not self.ready:
            self.logger.info("Not ready for task")
            return False
        hosts, tasks = self.session.host.getLoadData()
        self.logger.debug("Load Data:")
        self.logger.debug("  hosts: %r" % hosts)
        self.logger.debug("  tasks: %r" % tasks)
        # now we organize this data into channel-arch bins
        bin_hosts = {}  # hosts indexed by bin
        bins = {}  # bins for this host
        our_avail = None
        for host in hosts:
            host['bins'] = []
            if host['id'] == self.host_id:
                # note: task_load reported by server might differ from what we
                # sent due to precision variation
                our_avail = host['capacity'] - host['task_load']
            for chan in host['channels']:
                for arch in host['arches'].split() + ['noarch']:
                    bin = "%s:%s" % (chan, arch)
                    bin_hosts.setdefault(bin, []).append(host)
                    if host['id'] == self.host_id:
                        bins[bin] = 1
        self.logger.debug("bins: %r" % bins)
        if our_avail is None:
            self.logger.info("Server did not report this host. Are we disabled?")
            return False
        elif not bins:
            self.logger.info("No bins for this host. Missing channel/arch config?")
            # Note: we may still take an assigned task below
        # sort available capacities for each of our bins
        avail = {}
        for bin in bins:
            avail[bin] = [host['capacity'] - host['task_load'] for host in bin_hosts[bin]]
            avail[bin].sort()
            avail[bin].reverse()
        self.cleanDelayTimes()
        for task in tasks:
            # note: tasks are in priority order
            self.logger.debug("task: %r" % task)
            if task['method'] not in self.handlers:
                self.logger.warning("Skipping task %(id)i, no handler for method %(method)s", task)
                continue
            if task['id'] in self.tasks:
                # we were running this task, but it apparently has been
                # freed or reassigned. We can't do anything with it until
                # updateTasks notices this and cleans up.
                self.logger.debug("Task %(id)s freed or reassigned", task)
                continue
            if task['state'] == koji.TASK_STATES['ASSIGNED']:
                self.logger.debug("task is assigned")
                if self.host_id == task['host_id']:
                    # assigned to us, we can take it regardless
                    if self.takeTask(task):
                        return True
            elif task['state'] == koji.TASK_STATES['FREE']:
                bin = "%(channel_id)s:%(arch)s" % task
                self.logger.debug("task is free, bin=%r" % bin)
                if bin not in bins:
                    continue
                # see where our available capacity is compared to other hosts for this bin
                # (note: the hosts in this bin are exactly those that could
                # accept this task)
                bin_avail = avail.get(bin, [0])
                if self.checkAvailDelay(task, bin_avail, our_avail):
                    # decline for now and give the upper half a chance
                    continue
                # otherwise, we attempt to open the task
                if self.takeTask(task):
                    return True
            else:
                # should not happen
                raise Exception("Invalid task state reported by server")
        return False

    def checkAvailDelay(self, task, bin_avail, our_avail):
        """Check to see if we should still delay taking a task

        Returns True if we are still in the delay period and should skip the
        task. Otherwise False (delay has expired).
        """

        now = time.time()
        ts = self.skipped_tasks.get(task['id'])
        if not ts:
            ts = self.skipped_tasks[task['id']] = now

        # determine our normalized bin rank
        for pos, cap in enumerate(bin_avail):
            if our_avail >= cap:
                break
        if len(bin_avail) > 1:
            rank = float(pos) / (len(bin_avail) - 1)
        else:
            rank = 0.0
        # so, 0.0 for highest available capacity, 1.0 for lowest

        delay = getattr(self.options, 'task_avail_delay', 180)
        delay *= rank

        # return True if we should delay
        if now - ts < delay:
            self.logger.debug("skipping task %i, age=%s rank=%s"
                              % (task['id'], int(now - ts), rank))
            return True
        # otherwise
        del self.skipped_tasks[task['id']]
        return False

    def cleanDelayTimes(self):
        """Remove old entries from skipped_tasks"""
        now = time.time()
        delay = getattr(self.options, 'task_avail_delay', 180)
        cutoff = now - delay * 10
        # After 10x the delay, we've had plenty of opportunity to take the
        # task, so either it has already been taken or we can't take it.
        for task_id in list(self.skipped_tasks):
            ts = self.skipped_tasks[task_id]
            if ts < cutoff:
                del self.skipped_tasks[task_id]

    def _waitTask(self, task_id, pid=None):
        """Wait (nohang) on the task, return true if finished"""
        if pid is None:
            pid = self.pids.get(task_id)
            if not pid:
                raise koji.GenericError("No pid for task %i" % task_id)
        prefix = "Task %i (pid %i)" % (task_id, pid)
        try:
            (childpid, status) = os.waitpid(pid, os.WNOHANG)
        except OSError as e:
            # check errno
            if e.errno != errno.ECHILD:
                # should not happen
                raise
            # otherwise assume the process is gone
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
                    self.logger.info(
                        '%s (pid %i, taskID %i) was killed by signal %i' %
                        (execname, pid, task_id, sig))
                else:
                    self.logger.info('%s (pid %i, taskID %i) exited' % (execname, pid, task_id))
                return True

            if t >= timeout:
                self.logger.warning('Failed to kill %s (pid %i, taskID %i) with signal %i' %
                                    (execname, pid, task_id, sig))
                return False

            try:
                os.kill(pid, sig)
            except OSError as e:
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
            proc_file = koji._open_text_file(proc_path)
            procstats = [not field.isdigit() and field or int(field)
                         for field in proc_file.read().split()]
            proc_file.close()

            cmd_path = '/proc/%i/cmdline' % pid
            if not os.path.isfile(cmd_path):
                return None
            cmd_file = koji._open_text_file(cmd_path)
            procstats[1] = cmd_file.read().replace('\0', ' ').strip()
            cmd_file.close()
            if not procstats[1]:
                return None

            return procstats
        except IOError:
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
                    # get the /proc entries with ppid as their parent, and append their pid to the
                    # list, then recheck for their children pid is the 0th field, ppid is the 3rd
                    # field
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
            raise koji.GenericError("No pid for task %i" % task_id)
        children = self._childPIDs(pid)
        if children:
            # send SIGINT once to let mock mock try to clean up
            self._killChildren(task_id, children, sig=signal.SIGINT, pause=3.0)
        if children:
            self._killChildren(task_id, children)
        if children:
            self._killChildren(task_id, children, sig=signal.SIGKILL, timeout=3.0)

        # expire the task's subsession
        session_id = self.subsessions.get(task_id)
        if session_id:
            self.logger.info("Expiring subsession %i (task %i)" % (session_id, task_id))
            try:
                self.session.logoutChild(session_id)
                del self.subsessions[task_id]
            except Exception:
                # not much we can do about it
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
            raise IOError("No such directory: %s" % br_path)
        fs_stat = os.statvfs(br_path)
        available = fs_stat.f_bavail * fs_stat.f_bsize
        availableMB = available // 1024 // 1024
        self.logger.debug("disk space available in '%s': %i MB", br_path, availableMB)
        if availableMB < self.options.minspace:
            self.status = "Insufficient disk space at %s: %i MB, %i MB required" % \
                          (br_path, availableMB, self.options.minspace)
            self.logger.warning(self.status)
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
        #                       https://www.redhat.com/advice/tips/meminfo.html
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
            self.logger.info(
                "Task load (%.2f) exceeds capacity (%.2f)" %
                (self.task_load, self.hostdata['capacity']))
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
        # XXX - add more checks
        return True

    def takeTask(self, task):
        """Attempt to open the specified task

        Returns True if successful, False otherwise
        """
        self.logger.info("Attempting to take task %s" % task['id'])
        method = task['method']
        if method in self.handlers:
            handlerClass = self.handlers[method]
        else:
            raise koji.GenericError("No handler found for method '%s'" % method)
        task_info = self.session.getTaskInfo(task['id'], request=True)
        if task_info.get('request') is None:
            self.logger.warning("Task '%s' has no request" % task['id'])
            return False
        params = task_info['request']
        handler = handlerClass(task_info['id'], method, params, self.session, self.options)
        if hasattr(handler, 'checkHost'):
            try:
                valid_host = handler.checkHost(self.hostdata)
            except (SystemExit, KeyboardInterrupt):
                raise
            except Exception:
                valid_host = False
                self.logger.warning('Error during host check')
                self.logger.warning(''.join(traceback.format_exception(*sys.exc_info())))
            if not valid_host:
                self.logger.info(
                    'Skipping task %s (%s) due to host check', task['id'], task['method'])
                return False
        data = self.session.host.openTask(task['id'])
        if data is None:
            self.logger.warning("Could not open")
            return False
        task_id = data['id']
        self.tasks[task_id] = data
        # set weight
        try:
            self.session.host.setTaskWeight(task_id, handler.weight())
        except koji.ActionNotAllowed:
            info2 = self.session.getTaskInfo(task['id'])
            if info2['host_id'] != self.host_id:
                self.logger.warning("Task %i was reassigned", task_id)
                return False
            state = koji.TASK_STATES[info2['state']]
            if state != 'OPEN':
                self.logger.warning("Task %i changed is %s", task_id, state)
                return False
            # otherwise...
            raise
        if handler.Foreground:
            self.logger.info("running task in foreground")
            handler.setManager(self)
            self.runTask(handler)
        else:
            pid, session_id = self.forkTask(handler)
            self.pids[task_id] = pid
            self.subsessions[task_id] = session_id
        return True

    def forkTask(self, handler):
        # get the subsession before we fork
        newhub = self.session.subsession()
        session_id = newhub.sinfo['session-id']
        pid = os.fork()
        if pid:
            newhub._forget()
            return pid, session_id
        # in no circumstance should we return after the fork
        # nor should any exceptions propagate past here
        try:
            self.session._forget()
            # set process group
            os.setpgrp()
            # use the subsession
            self.session = newhub
            handler.session = self.session
            # set a do-nothing handler for sigusr2
            signal.signal(signal.SIGUSR2, lambda *args: None)
            self.runTask(handler)
        finally:
            # diediedie
            try:
                self.session.logout()
            finally:
                os._exit(0)

    def runTask(self, handler):
        try:
            response = (handler.run(),)
            # note that we wrap response in a singleton tuple
            response = koji.xmlrpcplus.dumps(response, methodresponse=1, allow_none=1)
            self.logger.info("RESPONSE: %r" % response)
            self.session.host.closeTask(handler.id, response)
            return
        except koji.xmlrpcplus.Fault as fault:
            response = koji.xmlrpcplus.dumps(fault)
            tb = ''.join(traceback.format_exception(*sys.exc_info())).replace(r"\n", "\n")
            self.logger.warning("FAULT:\n%s" % tb)
        except (SystemExit, koji.tasks.ServerExit, KeyboardInterrupt):
            # we do not trap these
            raise
        except koji.tasks.ServerRestart:
            # freeing this task will allow the pending restart to take effect
            self.session.host.freeTasks([handler.id])
            return
        except Exception:
            tb = ''.join(traceback.format_exception(*sys.exc_info()))
            self.logger.warning("TRACEBACK: %s" % tb)
            # report exception back to server
            e_class, e = sys.exc_info()[:2]
            faultCode = getattr(e_class, 'faultCode', 1)
            if issubclass(e_class, koji.GenericError):
                # just pass it through
                tb = str(e)
            response = koji.xmlrpcplus.dumps(koji.xmlrpcplus.Fault(faultCode, tb))

        # if we get here, then we're handling an exception, so fail the task
        self.session.host.failTask(handler.id, response)
