# Koji callback for extracting Maven artifacts (.pom and .jar files)
# from an rpm and making them available via the Koji-managed Maven repo.
# Copyright (c) 2010 Red Hat, Inc.
#
# Authors:
#     Mike Bonnet <mikeb@redhat.com>

import koji
from koji.context import context
from koji.plugin import callback
import ConfigParser
import fnmatch
import os
import shutil
import subprocess

CONFIG_FILE = '/etc/koji-hub/plugins/rpm2maven.conf'

config = None

@callback('postImport')
def maven_import(cbtype, *args, **kws):
    global config
    if not context.opts.get('EnableMaven', False):
        return
    if kws.get('type') != 'rpm':
        return
    buildinfo = kws['build']
    rpminfo = kws['rpm']
    filepath = kws['filepath']

    if not config:
        config = ConfigParser.SafeConfigParser()
        config.read(CONFIG_FILE)
    name_patterns = config.get('patterns', 'rpm_names').split()
    for pattern in name_patterns:
        if fnmatch.fnmatch(rpminfo['name'], pattern):
            break
    else:
        return

    tmpdir = os.path.join(koji.pathinfo.work(), 'rpm2maven', koji.buildLabel(buildinfo))
    try:
        if os.path.exists(tmpdir):
            shutil.rmtree(tmpdir)
        koji.ensuredir(tmpdir)
        expand_rpm(filepath, tmpdir)
        scan_and_import(buildinfo, rpminfo, tmpdir)
    finally:
        if os.path.exists(tmpdir):
            shutil.rmtree(tmpdir)

def expand_rpm(filepath, tmpdir):
    devnull = file('/dev/null', 'r+')
    rpm2cpio = subprocess.Popen(['/usr/bin/rpm2cpio', filepath],
                                stdout=subprocess.PIPE,
                                stdin=devnull, stderr=devnull,
                                close_fds=True)
    cpio = subprocess.Popen(['/bin/cpio', '-id'],
                            stdin=rpm2cpio.stdout,
                            cwd=tmpdir,
                            stdout=devnull, stderr=devnull,
                            close_fds=True)
    if rpm2cpio.wait() != 0 or cpio.wait() != 0:
        raise koji.CallbackError, 'error extracting files from %s, ' \
              'rpm2cpio returned %s, cpio returned %s' % \
              (filepath, rpm2cpio.wait(), cpio.wait())
    devnull.close()

def scan_and_import(buildinfo, rpminfo, tmpdir):
    global config
    path_patterns = config.get('patterns', 'artifact_paths').split()

    maven_archives = []
    for dirpath, dirnames, filenames in os.walk(tmpdir):
        relpath = dirpath[len(tmpdir):]
        for pattern in path_patterns:
            if fnmatch.fnmatch(relpath, pattern):
                break
        else:
            continue

        poms = [f for f in filenames if f.endswith('.pom')]
        if len(poms) != 1:
            continue

        pom_info = koji.parse_pom(os.path.join(dirpath, poms[0]))
        maven_info = koji.pom_to_maven_info(pom_info)
        maven_archives.append({'maven_info': maven_info,
                               'files': [os.path.join(dirpath, f) for f in filenames]})

    if not maven_archives:
        return

    # We don't know which pom is the top-level pom, so we don't know what Maven
    # metadata to associate with the build.  So we make something up.
    maven_build = {'group_id': buildinfo['name'], 'artifact_id': rpminfo['name'],
                   'version': '%(version)s-%(release)s' % buildinfo}
    context.handlers.call('host.createMavenBuild', buildinfo, maven_build)

    for entry in maven_archives:
        maven_info = entry['maven_info']
        for filepath in entry['files']:
            if not context.handlers.call('getArchiveType', filename=filepath):
                # unsupported archive type, skip it
                continue
            context.handlers.call('host.importArchive', filepath, buildinfo, 'maven', maven_info)
