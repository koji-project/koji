#!/usr/bin/python

# Koji daemon that runs in a Windows VM and executes commands associated
# with a task.
# Copyright (c) 2010 Red Hat
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
#       Mike Bonnet <mikeb@redhat.com>
#       Jay Greguske <jgregusk@redhat.com>
#
# To register this script as a service on Windows 2008 (with Cygwin 1.7.5 installed) run:
#   kojiwind --install
# in a cygwin shell.

from optparse import OptionParser
from ConfigParser import ConfigParser
import os
import subprocess
import sys
import tempfile
import time
import urlparse
import xmlrpclib
import base64
import hashlib
import logging
import traceback
import threading
import re
import glob

MANAGER_PORT = 7000

KOJIKAMID = True

## INSERT kojikamid dup

class fakemodule(object):
    pass

#make parts of the above insert accessible as koji.X
koji = fakemodule()
koji.GenericError = GenericError
koji.BuildError = BuildError


class WindowsBuild(object):

    LEADING_CHAR = re.compile('^[^A-Za-z_]')
    VAR_CHARS = re.compile('[^A-Za-z0-9_]')

    def __init__(self, server):
        """constructor: check ini spec file syntax, set build properties"""
        self.logger = logging.getLogger('koji.vm')
        self.server = server
        info = server.getTaskInfo()
        self.source_url = info[0]
        self.build_tag = info[1]
        if len(info) > 2:
            self.task_opts = info[2]
        else:
            self.task_opts = {}
        self.workdir = '/tmp/build'
        ensuredir(self.workdir)
        self.buildreq_dir = os.path.join(self.workdir, 'buildreqs')
        ensuredir(self.buildreq_dir)
        self.source_dir = None
        self.spec_dir = None

        # we initialize these here for clarity, but they are populated in loadConfig()
        self.name = None
        self.version = None
        self.release = None
        self.description = None
        self.platform = None
        self.preinstalled = []
        self.buildrequires = []
        self.provides = []
        self.shell = None
        self.execute = []
        self.postbuild = []
        self.output = {}
        self.logs = []

    def checkTools(self):
        """Is this environment fit to build in, based on the spec file?"""
        errors = []
        for entry in self.preinstalled:
            checkdir = False
            if entry.startswith('/'):
                # Cygwin path
                if entry.endswith('/'):
                    # directory
                    checkdir = True
            elif entry[1:3] == ':\\':
                # Windows path
                if entry.endswith('\\'):
                    # directory
                    checkdir = True
            else:
                # Check in the path
                ret, output = run(['which', entry], log=False, fatal=False)
                output = output.strip()
                if ret:
                    errors.append(output)
                else:
                    self.logger.info('command %s is available at %s', entry, output)
                continue
            if checkdir:
                if not os.path.isdir(entry):
                    errors.append('directory %s does not exist' % entry)
                else:
                    self.logger.info('directory %s exists', entry)
            else:
                # file
                if not os.path.isfile(entry):
                    errors.append('file %s does not exist' % entry)
                else:
                    self.logger.info('file %s exists', entry)
        if errors:
            raise BuildError, 'error validating build environment: %s' % \
                  ', '.join(errors)

    def updateClam(self):
        """update ClamAV virus definitions"""
        ret, output = run(['freshclam'])
        if ret and ret == 1:
            self.logger.info('ClamAV database is already up to date')
        elif ret:
            raise BuildError, 'could not update ClamAV database: %s' % output

    def checkEnv(self):
        """make the environment is fit for building in"""
        # right now we just check for ClamAV executables
        for clam_tool in ('freshclam', 'clamscan'):
            ret, output = run(['which', clam_tool], log=False, fatal=False)
            if ret:
                raise BuildError, '%s appears to be missing, is ClamAV installed?' % clam_tool

    def checkout(self):
        """Checkout sources, winspec, and patches, and apply patches"""
        src_scm = SCM(self.source_url)
        self.source_dir = src_scm.checkout(ensuredir(os.path.join(self.workdir, 'source')))
        if 'winspec' in self.task_opts:
            spec_scm = SCM(self.task_opts['winspec'])
            self.spec_dir = spec_scm.checkout(ensuredir(os.path.join(self.workdir, 'spec')))
        else:
            self.spec_dir = self.source_dir
        if 'patches' in self.task_opts:
            patch_scm = SCM(self.task_opts['patches'])
            patch_dir = patch_scm.checkout(ensuredir(os.path.join(self.workdir, 'patches')))
            self.applyPatches(self.source_dir, patch_dir)
        self.virusCheck(self.workdir)

    def applyPatches(self, sourcedir, patchdir):
        """Apply patches in patchdir to files in sourcedir)"""
        patches = [patch for patch in os.listdir(patchdir) if \
                   os.path.isfile(os.path.join(patchdir, patch)) and \
                   not patch.startswith('.')]
        if not patches:
            raise BuildError, 'no patches found at %s' % patchdir
        patches.sort()
        for patch in patches:
            cmd = ['/usr/bin/patch', '--verbose', '-d', sourcedir, '-p1', '-i', os.path.join(patchdir, patch)]
            run(cmd, fatal=True)

    def loadConfig(self):
        """Load build configuration from the spec file."""
        specfiles = [spec for spec in os.listdir(self.spec_dir) if spec.endswith('.ini')]
        if len(specfiles) == 0:
            raise BuildError, 'No .ini file found'
        elif len(specfiles) > 1:
            raise BuildError, 'Multiple .ini files found'

        conf = ConfigParser()
        conf.read(os.path.join(self.spec_dir, specfiles[0]))

        # [naming] section
        for entry in ('name', 'version', 'release', 'description'):
            setattr(self, entry, conf.get('naming', entry))
        if conf.has_option('naming', 'epoch'):
            self.epoch = conf.get('naming', 'epoch')
        else:
            self.epoch = None

        # [building] section
        self.platform = conf.get('building', 'platform')

        # preinstalled are paths to files or directories that must exist
        # in the VM for it to execute the build.
        # If the path ends in / or \ it must be a directory, otherwise it must
        # be a file.
        # They may be specified as Cygwin (/cygdrive/c/...) or Windows (C:\...)
        # absolute paths, or without a path in which case it is searched for
        # on the PATH.
        if conf.has_option('building', 'preinstalled'):
            self.preinstalled.extend([e.strip() for e in conf.get('building', 'preinstalled').split('\n') if e])

        # buildrequires and provides are multi-valued (space-separated)
        for br in conf.get('building', 'buildrequires').split():
            # buildrequires is a space-separated list
            # each item in the list is in the format:
            # pkgname[:opt1:opt2=val2:...]
            # the options are put into a dict
            # if the option has no =val, the value in the dict will be None
            if br:
                br = br.split(':')
                bropts = {}
                for opt in br[1:]:
                    if '=' in opt:
                        key, val = opt.split('=', 1)
                    else:
                        key = opt
                        val = None
                    bropts[key] = val
                self.buildrequires.append((br[0], bropts))
        for prov in conf.get('building', 'provides').split():
            if prov:
                self.provides.append(prov)
        # optionally specify a shell to use (defaults to bash)
        # valid values are: cmd, cmd.exe (alias for cmd), and bash
        if conf.has_option('building', 'shell'):
            self.shell = conf.get('building', 'shell')
        else:
            self.shell = 'bash'
        # execute is multi-valued (newline-separated)
        self.execute.extend([e.strip() for e in conf.get('building', 'execute').split('\n') if e])

        # postbuild are files or directories that must exist after the build is
        # complete, but are not included in the build output
        # they are specified as paths relative the source directory, and may be
        # in Unix or Windows format
        # each entry may contain shell-style globs, and one or more files
        # matching the glob is considered valid
        if conf.has_option('building', 'postbuild'):
            self.postbuild.extend([e.strip() for e in conf.get('building', 'postbuild').split('\n') if e])

        # [files] section
        for entry in conf.get('files', 'output').split('\n'):
            if not entry:
                continue
            tokens = entry.strip().split(':')
            filename = tokens[0]
            for var in ('name', 'version', 'release'): 
                filename = filename.replace('$' + var, getattr(self, var))
            metadata = {}
            metadata['platforms'] = tokens[1].split(',')
            if len(tokens) > 2:
                metadata['flags'] = tokens[2].split(',')
            else:
                metadata['flags'] = []
            self.output[filename] = metadata
        self.logs.extend([e.strip() for e in conf.get('files', 'logs').split('\n') if e])

    def fetchFile(self, basedir, buildinfo, fileinfo, type):
        """Download the file from buildreq, at filepath, into the basedir"""
        destpath = os.path.join(basedir, fileinfo['localpath'])
        ensuredir(os.path.dirname(destpath))
        destfile = file(destpath, 'w')
        offset = 0
        checksum = hashlib.md5()
        while True:
            encoded = self.server.getFile(buildinfo, fileinfo, encode_int(offset), 1048576, type)
            if not encoded:
                break
            data = base64.b64decode(encoded)
            del encoded
            destfile.write(data)
            offset += len(data)
            checksum.update(data)
        destfile.close()
        digest = checksum.hexdigest()
        # rpms don't have a md5sum in the fileinfo, but check it for everything else
        if ('md5sum' in fileinfo) and (digest != fileinfo['md5sum']):
            raise BuildError, 'md5 checksum validation failed for %s, %s (computed) != %s (provided)' % \
                  (destpath, digest, fileinfo['md5sum'])
        self.logger.info('Retrieved %s (%s bytes, md5: %s)', destpath, offset, digest)

    def fetchBuildReqs(self):
        """Retrieve buildrequires listed in the spec file"""
        for buildreq, brinfo in self.buildrequires:
            # if no type is specified in the options, default to win
            brtype = brinfo.get('type', 'win')
            buildinfo = self.server.getLatestBuild(self.build_tag, buildreq,
                                                   self.task_opts.get('repo_id'))
            br_dir = os.path.join(self.buildreq_dir, buildreq, brtype)
            ensuredir(br_dir)
            brinfo['dir'] = br_dir
            brfiles = []
            brinfo['files'] = brfiles
            buildfiles = self.server.getFileList(buildinfo['id'], brtype, brinfo)
            for fileinfo in buildfiles:
                self.fetchFile(br_dir, buildinfo, fileinfo, brtype)
                brfiles.append(fileinfo['localpath'])
        self.virusCheck(self.buildreq_dir)

    def build(self):
        if self.shell in ('cmd', 'cmd.exe'):
            self.cmdBuild()
        else:
            self.bashBuild()

    def varname(self, name):
        """
        Convert name to a valid shell variable name.
        Converts leading characters that aren't letters or underscores
        to underscores.
        Converts any other characters that aren't letters, numbers,
        or underscores to underscores.
        """
        name = self.LEADING_CHAR.sub('_', name)
        name = self.VAR_CHARS.sub('_', name)
        return name

    def cmdBuild(self):
        """Do the build: run the execute line(s) with cmd.exe"""
        tmpfd, tmpname = tempfile.mkstemp(prefix='koji-tmp', suffix='.bat', dir='/cygdrive/c/Windows/Temp')
        script = os.fdopen(tmpfd, 'w')
        for buildreq, brinfo in self.buildrequires:
            buildreq = self.varname(buildreq)
            ret, output = run(['cygpath', '-wa', brinfo['dir']], log=False, fatal=True)
            br_dir = output.strip()
            files = ' '.join(brinfo['files'])
            files.replace('/', '\\')
            if brinfo.get('type'):
                # if the spec file qualifies the buildreq with a type,
                # the env. var is named buildreq_type_{dir,files}
                script.write('set %s_%s_dir=%s\r\n' % (buildreq, brinfo['type'], br_dir))
                script.write('set %s_%s_files=%s\r\n' % (buildreq, brinfo['type'], files))
            else:
                # otherwise it's just buildreq_{dir,files}
                script.write('set %s_dir=%s\r\n' % (buildreq, br_dir))
                script.write('set %s_files=%s\r\n' % (buildreq, files))
            script.write('\r\n')
        script.write('set name=%s\r\n' % self.name)
        script.write('set version=%s\r\n' % self.version)
        script.write('set release=%s\r\n' % self.release)
        for cmd in self.execute:
            script.write(cmd)
            script.write('\r\n')
        script.close()
        cmd = ['cmd.exe', '/C', 'C:\\Windows\\Temp\\' + os.path.basename(tmpname)]
        ret, output = run(cmd, chdir=self.source_dir)
        if ret:
            raise BuildError, 'build command failed, see build.log for details'

    def bashBuild(self):
        """Do the build: run the execute line(s) with bash"""
        tmpfd, tmpname = tempfile.mkstemp(prefix='koji-tmp.', dir='/tmp')
        script = os.fdopen(tmpfd, 'w')
        for buildreq, brinfo in self.buildrequires:
            buildreq = self.varname(buildreq)
            if brinfo.get('type'):
                script.write("export %s_%s_dir='%s'\n" % (buildreq, brinfo['type'], brinfo['dir']))
                script.write("export %s_%s_files='" % (buildreq, brinfo['type']))
            else:
                script.write("export %s_dir='%s'\n" % (buildreq, brinfo['dir']))
                script.write("export %s_files='" % buildreq)
            for filename in brinfo['files']:
                script.write(filename)
                script.write('\n')
            script.write("'\n\n")
        script.write('export name=%s\n' % self.name)
        script.write('export version=%s\n' % self.version)
        script.write('export release=%s\n' % self.release)
        for cmd in self.execute:
            script.write(cmd)
            script.write('\n')
        script.close()
        cmd = ['/bin/bash', '-e', '-x', tmpname]
        ret, output = run(cmd, chdir=self.source_dir)
        if ret:
            raise BuildError, 'build command failed, see build.log for details'

    def checkBuild(self):
        """Verify that the build completed successfully."""
        errors = []
        for entry in self.postbuild:
            relpath = entry
            if '\\' in relpath:
                relpath = relpath.replace('\\', '/')
            fullpath = os.path.join(self.source_dir, relpath)
            results = glob.glob(fullpath)
            if fullpath.endswith('/'):
                for result in results:
                    if os.path.isdir(result):
                        self.logger.info('found directory %s at %s', entry, result)
                        break
                else:
                    errors.append('directory %s does not exist' % entry)
            else:
                for result in results:
                    if os.path.isfile(result):
                        self.logger.info('found file %s at %s', entry, result)
                        break
                else:
                    errors.append('file %s does not exist' % entry)
        self.virusCheck(self.workdir)
        if errors:
            raise BuildError, 'error validating build output: %s' % \
                  ', '.join(errors)

    def virusCheck(self, path):
        """ensure a path is virus free with ClamAV. path should be absolute"""
        if not path.startswith('/'):
            raise BuildError, 'Invalid path to scan for viruses: ' + path
        run(['clamscan', '--quiet', '--recursive', path], fatal=True)

    def gatherResults(self):
        """Gather information about the output from the build, return it"""
        return {'name': self.name, 'version': self.version, 'release': self.release,
                'epoch': self.epoch,
                'description': self.description, 'platform': self.platform,
                'provides': self.provides,
                'output': self.output, 'logs': self.logs}

    def run(self):
        """Run the entire build process"""
        self.checkEnv()
        self.updateClam()
        self.checkout()
        self.loadConfig()
        self.checkTools()
        self.fetchBuildReqs()
        self.build()
        self.checkBuild()
        return self.gatherResults()

def run(cmd, chdir=None, fatal=False, log=True):
    global logfd
    output = ''
    olddir = None
    if chdir:
        olddir = os.getcwd()
        os.chdir(chdir)
    if log:
        logger = logging.getLogger('koji.vm')
        logger.info('$ %s', ' '.join(cmd))
        proc = subprocess.Popen(cmd, stdout=logfd, stderr=subprocess.STDOUT,
                                close_fds=True)
        ret = proc.wait()
    else:
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                close_fds=True)
        output, dummy = proc.communicate()
        ret = proc.returncode
    if olddir:
        os.chdir(olddir)
    if ret and fatal:
        msg = 'error running: %s, return code was %s' % (' '.join(cmd), ret)
        if log:
            msg += ', see %s for details' % (os.path.basename(logfd.name))
        else:
            msg += ', output: %s' % output
        raise BuildError, msg
    return ret, output

def find_net_info():
    """
    Find the network gateway configured for this VM.
    """
    ret, output = run(['ipconfig', '/all'], log=False)
    if ret:
        raise RuntimeError, 'error running ipconfig, output was: %s' % output
    macaddr = None
    gateway = None
    for line in output.splitlines():
        line = line.strip()
        # take the first values we find
        if line.startswith('Physical Address'):
            if not macaddr:
                macaddr = line.split()[-1]
                # format it to be consistent with the libvirt MAC address
                macaddr = macaddr.replace('-', ':').lower()
        elif line.startswith('Default Gateway'):
            if not gateway:
                gateway = line.split()[-1]

    # check that we have valid values
    if macaddr and len(macaddr) != 17:
        macaddr = None
    if gateway and (len(gateway) < 7 or len(gateway) > 15):
        gateway = None
    return macaddr, gateway

def upload_file(server, prefix, path):
    """upload a single file to the vmd"""
    logger = logging.getLogger('koji.vm')
    destpath = os.path.join(prefix, path)
    fobj = file(destpath, 'r')
    offset = 0
    sum = hashlib.md5()
    while True:
        data = fobj.read(131072)
        if not data:
            break
        encoded = base64.b64encode(data)
        server.upload(path, encode_int(offset), encoded)
        offset += len(data)
        sum.update(data)
    fobj.close()
    digest = sum.hexdigest()
    server.verifyChecksum(path, digest, 'md5')
    logger.info('Uploaded %s (%s bytes, md5: %s)', destpath, offset, digest)

def get_mgmt_server():
    """Get a ServerProxy object we can use to retrieve task info"""
    logger = logging.getLogger('koji.vm')
    macaddr, gateway = find_net_info()
    while not (macaddr and gateway):
        # wait for the network connection to come up and get an address
        time.sleep(5)
        macaddr, gateway = find_net_info()
    logger.debug('found MAC address %s, connecting to %s:%s',
                 macaddr, gateway, MANAGER_PORT)
    server = xmlrpclib.ServerProxy('http://%s:%s/' %
                                   (gateway, MANAGER_PORT), allow_none=True)
    # we would set a timeout on the socket here, but that is apparently not 
    # supported by python/cygwin/Windows
    task_port = server.getPort(macaddr)
    logger.debug('found task-specific port %s', task_port)
    return xmlrpclib.ServerProxy('http://%s:%s/' % (gateway, task_port), allow_none=True)

def get_options():
    """handle usage and parse options"""
    usage = """%prog [options]
    Run Koji tasks assigned to a VM.
    Run without any arguments to start this daemon.
    """
    parser = OptionParser(usage=usage)
    parser.add_option('-d', '--debug', action='store_true', help='Log debug statements')
    parser.add_option('-i', '--install', action='store_true', help='Install this daemon as a service', default=False)
    parser.add_option('-u', '--uninstall', action='store_true', help='Uninstall this daemon if it was installed previously as a service', default=False)
    (options, args) = parser.parse_args()
    return options

def setup_logging(opts):
    global logfile, logfd
    logger = logging.getLogger('koji.vm')
    level = logging.INFO
    if opts.debug:
        level = logging.DEBUG
    logger.setLevel(level)
    logfd = file(logfile, 'w')
    handler = logging.StreamHandler(logfd)
    handler.setLevel(level)
    handler.setFormatter(logging.Formatter('%(asctime)s [%(levelname)s] %(name)s: %(message)s'))
    logger.addHandler(handler)
    return handler

def log_local(msg):
    tb = ''.join(traceback.format_exception(*sys.exc_info()))
    sys.stderr.write('%s: %s\n' % (time.ctime(), msg))
    sys.stderr.write(tb)

def incremental_upload(server, handler):
    global logfile
    fd = file(logfile, 'r')
    while handler.active:
        offset = fd.tell()
        contents = fd.read(65536)
        if contents:
            size = len(contents)
            data = base64.b64encode(contents)
            digest = hashlib.md5(contents).hexdigest()
            del contents
            while handler.active:
                try:
                    server.uploadDirect(os.path.basename(logfile),
                                        offset, size, digest, data)
                    break
                except:
                    # upload failed (possibly a timeout), log and retry
                    log_local('error calling server.uploadDirect()')
        else:
            time.sleep(1)

def fail(server, handler):
    """do the right thing when a build fails"""
    global logfile, logfd
    logging.getLogger('koji.vm').error('error running build', exc_info=True)
    tb = ''.join(traceback.format_exception(*sys.exc_info()))
    handler.active = False
    if server is not None:
        try:
            logfd.flush()
            upload_file(server, os.path.dirname(logfile),
                        os.path.basename(logfile))
        except:
            log_local('error calling upload_file()')
        while True:
            try:
                # this is the very last thing we do, keep trying as long as we can
                server.failTask(tb)
                break
            except:
                log_local('error calling server.failTask()')
    sys.exit(1)


logfile = '/tmp/build.log'
logfd = None

def main():
    prog = os.path.basename(sys.argv[0])
    opts = get_options()
    if opts.install:
        ret, output = run(['cygrunsrv', '--install', prog,
                           '--path', sys.executable, '--args', os.path.abspath(prog),
                           '--type', 'auto', '--dep', 'Dhcp',
                           '--disp', 'Koji Windows Daemon',
                           '--desc', 'Runs Koji tasks assigned to a VM'],
                          log=False)
        if ret:
            print 'Error installing %s service, output was: %s' % (prog, output)
            sys.exit(1)
        else:
            print 'Successfully installed the %s service' % prog
            sys.exit(0)
    elif opts.uninstall:
        ret, output = run(['cygrunsrv', '--remove', prog], log=False)
        if ret:
            print 'Error removing the %s service, output was: %s' % (prog, output)
            sys.exit(1)
        else:
            print 'Successfully removed the %s service' % prog
            sys.exit(0)

    handler = setup_logging(opts)
    handler.active = True
    server = None
    try:
        server = get_mgmt_server()

        thread = threading.Thread(target=incremental_upload,
                                  args=(server, handler))
        thread.daemon = True
        thread.start()

        build = WindowsBuild(server)
        results = build.run()

        for filename in results['output'].keys() + results['logs']:
            upload_file(server, build.source_dir, filename)

        handler.active = False
        thread.join()

        upload_file(server, os.path.dirname(logfile),
                    os.path.basename(logfile))
        results['logs'].append(os.path.basename(logfile))

        server.closeTask(results)
    except:
        fail(server, handler)
    sys.exit(0)


if __name__ == '__main__':
    main()
