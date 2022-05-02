import os
import koji
from fnmatch import fnmatch
from koji.util import to_list
from koji.tasks import ServerExit
from __main__ import BaseBuildTask, BuildImageTask, BuildRoot, SCM

# /usr/lib/koji-builder-plugins/


class DudBuildTask(BuildImageTask):
    Methods = ['dudBuild']
    _taskWeight = 1.0

    def handler(self, dud_name, dud_version, arches, target, pkg_list, opts=None):
        target_info = self.session.getBuildTarget(target, strict=True)
        build_tag = target_info['build_tag']
        repo_info = self.getRepo(build_tag)
        # check requested arches against build tag
        buildconfig = self.session.getBuildConfig(build_tag)
        if not buildconfig['arches']:
            raise koji.BuildError("No arches for tag %(name)s [%(id)s]" % buildconfig)
        tag_archlist = [koji.canonArch(a) for a in buildconfig['arches'].split()]
        if arches:
            for arch in arches:
                if koji.canonArch(arch) not in tag_archlist:
                    raise koji.BuildError("Invalid arch for build tag: %s" % arch)
        else:
            arches = tag_archlist

        if not opts:
            opts = {}
        if not opts.get('scratch'):
            opts['scratch'] = False
        if not opts.get('alldeps'):
            opts['alldeps'] = False
        if not opts.get('scmurl'):
            opts['scmurl'] = None
        if not opts.get('optional_arches'):
            opts['optional_arches'] = []
        self.opts = opts

        name, version, release = dud_name, dud_version, None

        bld_info = None
        if opts.get('release'):
            release = opts['release']
        else:
            release = self.session.getNextRelease({'name': name, 'version': version})
        if '-' in version:
            raise koji.ApplianceError('The Version may not have a hyphen')
        if not opts['scratch']:
            bld_info = self.initImageBuild(name, version, release, target_info, opts)
            release = bld_info['release']

        try:
            subtasks = {}
            canfail = []
            self.logger.info("Spawning jobs for image arches: %r" % (arches))
            for arch in arches:
                subtasks[arch] = self.session.host.subtask(
                    method='createDudIso',
                    arglist=[name, version, release, arch,
                             target_info, build_tag, repo_info,
                             pkg_list, opts], label=arch, parent=self.id, arch=arch)
                if arch in self.opts['optional_arches']:
                    canfail.append(subtasks[arch])
            self.logger.info("Got image subtasks: %r" % (subtasks))
            self.logger.info("Waiting on image subtasks (%s can fail)..." % canfail)
            results = self.wait(to_list(subtasks.values()), all=True, failany=True,
                                canfail=canfail)

            # if everything failed, fail even if all subtasks are in canfail
            self.logger.info('subtask results: %r', results)
            all_failed = True
            for result in results.values():
                if not isinstance(result, dict) or 'faultCode' not in result:
                    all_failed = False
                    break
            if all_failed:
                raise koji.GenericError("all subtasks failed")

            # determine ignored arch failures
            ignored_arches = set()
            for arch in arches:
                if arch in self.opts['optional_arches']:
                    task_id = subtasks[arch]
                    result = results[task_id]
                    if isinstance(result, dict) and 'faultCode' in result:
                        ignored_arches.add(arch)

            self.logger.info('Image Results for hub: %s' % results)
            results = {str(k): v for k, v in results.items()}
            if opts['scratch']:
                self.session.host.moveImageBuildToScratch(self.id, results)
            else:
                self.session.host.completeImageBuild(self.id, bld_info['id'], results)
        except (SystemExit, ServerExit, KeyboardInterrupt):
            # we do not trap these
            raise
        except Exception:
            if not opts['scratch']:
                if bld_info:
                    self.session.host.failBuild(self.id, bld_info['id'])
            raise

        # tag it
        if not opts['scratch'] and not opts.get('skip_tag'):
            tag_task_id = self.session.host.subtask(method='tagBuild',
                                                    arglist=[target_info['dest_tag'],
                                                             bld_info['id'], False, None, True],
                                                    label='tag', parent=self.id, arch='noarch')
            self.wait(tag_task_id)

        # report results
        report = ''

        if opts['scratch']:
            respath = ', '.join(
                [os.path.join(koji.pathinfo.work(),
                              koji.pathinfo.taskrelpath(tid)) for tid in subtasks.values()])
            report += 'Scratch '

        else:
            respath = koji.pathinfo.imagebuild(bld_info)
        report += 'image build results in: %s' % respath
        return report


class DudCreateImageTask(BaseBuildTask):
    Methods = ['createDudIso']
    _taskWeight = 1.0

    def getImagePackagesFromPath(self, path):
        """
        Read RPM header information from the yum cache available in the
        given path. Returns a list of dictionaries for each RPM included.
        """
        found = False
        hdrlist = {}
        # For non scratch builds this is a must or it will not work
        fields = ['name', 'version', 'release', 'epoch', 'arch',
                  'buildtime', 'sigmd5']
        for root, dirs, files in os.walk(path):
            for f in files:
                if fnmatch(f, '*.rpm'):
                    pkgfile = os.path.join(root, f)
                    hdr = koji.get_header_fields(pkgfile, fields)
                    hdr['size'] = os.path.getsize(pkgfile)
                    hdr['payloadhash'] = koji.hex_string(hdr['sigmd5'])
                    del hdr['sigmd5']
                    hdrlist[os.path.basename(pkgfile)] = hdr
                    found = True
        if not found:
            raise koji.LiveCDError('No rpms found in root dir!')
        return list(hdrlist.values())

    def handler(self, dud_name, dud_version, dud_release, arch,
                target_info, build_tag, repo_info,
                pkg_list, opts=None):
        self.opts = opts
        self.logger.info("Running my dud task...")
        build_tag = target_info['build_tag']
        broot = BuildRoot(self.session, self.options,
                          tag=build_tag,
                          arch=arch,
                          task_id=self.id,
                          repo_id=repo_info['id'],
                          # Replace with a group that includes createrepo and xorrisofs
                          install_group='dud-build',
                          setup_dns=True,
                          bind_opts={'dirs': {'/dev': '/dev', }})
        broot.workdir = self.workdir

        # create the mock chroot
        self.logger.info("Initializing dud buildroot")
        broot.init()
        self.logger.info("dud buildroot ready: " + broot.rootdir())

        # user repos
        repos = self.opts.get('repos', [])
        # buildroot repo
        path_info = koji.PathInfo(topdir=self.options.topurl)
        repopath = path_info.repo(repo_info['id'], target_info['build_tag_name'])
        baseurl = '%s/%s' % (repopath, arch)
        self.logger.info('BASEURL: %s' % baseurl)
        repos.append(baseurl)

        imgdata = {
            'arch': arch,
            'task_id': self.id,
            'name': dud_name,
            'version': dud_version,
            'release': dud_release,
            'logs': [],
            'rpmlist': [],
            'files': [],
        }

        # Donwload each and every one of the packages on the list. We allow more than one
        # rpms per DUD ISO. Do them one by one to report which one may fail
        for rpm in pkg_list:
            cmd = ['/usr/bin/dnf']
            if self.opts.get('alldeps'):
                cmd.extend([
                    'download', '--resolve', '--alldeps', rpm,
                ])
            else:
                cmd.extend([
                    'download', rpm,
                ])

            rv = broot.mock(['--cwd', broot.tmpdir(within=True), '--chroot', '--'] + cmd)
            if rv:
                raise koji.GenericError("DUD build failed while getting the involved rpm '{}': {}"
                      .format(rpm, str(rv)))

        # Create the dd directory structure.
        cmd = ['/usr/bin/mkdir']
        cmd.extend([
            '-p', './dd/rpms/{arch}/repodata/'.format(arch=arch),
            '-p', './dd/src/',
        ])
        rv = broot.mock(['--cwd', broot.tmpdir(within=True), '--chroot', '--'] + cmd)
        if rv:
            raise koji.GenericError("DUD build failed while preparing the dir struct for "
                                    "the ISO: " + str(rv))

        # Inspiration from https://pagure.io/koji/blob/master/f/plugins/builder/runroot.py#_201
        # for this dirty hack
        cmd = ['/usr/bin/sh', '-c']
        cmd.extend([
            '/usr/bin/echo -e "Driver Update Disk version 3\\c" > ./dd/rhdd3',
        ])
        rv = broot.mock(['--cwd', broot.tmpdir(within=True), '--chroot', '--'] + cmd)
        if rv:
            raise koji.GenericError("DUD build failed while writing the rhdd3 file in "
                                    "the ISO: " + str(rv))

        # Get the SCM content into the ISO root
        # Retrieve SCM content if it exists
        if self.opts.get('scmurl'):
            # get configuration
            scm = SCM(self.opts.get('scmurl'))
            scm.assert_allowed(allowed=self.options.allowed_scms,
                               session=self.session,
                               by_config=self.options.allowed_scms_use_config,
                               by_policy=self.options.allowed_scms_use_policy,
                               policy_data={
                                   'user_id': self.taskinfo['owner'],
                                   'channel': self.session.getChannel(self.taskinfo['channel_id'],
                                                                      strict=True)['name'],
                                   'scratch': self.opts.get('scratch')
                               })
            logfile = os.path.join(self.workdir, 'checkout-%s.log' % arch)
            self.run_callbacks('preSCMCheckout', scminfo=scm.get_info(),
                               build_tag=build_tag, scratch=self.opts.get('scratch'))
            scmdir = broot.tmpdir()
            koji.ensuredir(scmdir)
            scmsrcdir = scm.checkout(scmdir, self.session,
                                     self.getUploadDir(), logfile)
            self.run_callbacks("postSCMCheckout",
                               scminfo=scm.get_info(),
                               build_tag=build_tag,
                               scratch=self.opts.get('scratch'),
                               srcdir=scmsrcdir)
            cmd = ['/usr/bin/cp']
            cmd.extend([
                '-aR', os.path.basename(scmsrcdir), './dd/',
            ])
            rv = broot.mock(['--cwd', broot.tmpdir(within=True), '--chroot', '--'] + cmd)
            if rv:
                raise koji.GenericError("DUD build failed while copying SCM repo content into dir"
                                        "struct: " + str(rv))

        # Get the RPMs inside the corresponding dir struct for the ISO
        cmd = ['/usr/bin/sh', '-c']
        # Could not get it to work with a more elegant syntax, as it would not find the *.rpm
        # files otherwise
        cmd.extend([
            '/usr/bin/cp *.rpm ./dd/rpms/{arch}/'.format(arch=arch),
        ])
        rv = broot.mock(['--cwd', broot.tmpdir(within=True), '--chroot', '--'] + cmd)
        if rv:
            raise koji.GenericError("DUD build failed while copying RPMs into dir struct: " +
                                    str(rv))

        cmd = ['/usr/bin/createrepo']
        cmd.extend([
            '-q', '--workers=1', './dd/rpms/{arch}/'.format(arch=arch),
        ])
        rv = broot.mock(['--cwd', broot.tmpdir(within=True), '--chroot', '--'] + cmd)
        if rv:
            raise koji.GenericError("DUD build failed while creating ISO repodata: " + str(rv))

        # xorrisofs -quiet -lR -V OEMDRV -input-charset utf8 -o $PACKNAME ./dd
        cmd = ['/usr/bin/sh', '-c']
        iso_name = 'dd-{name}-{version}-{release}.{arch}.iso'.format(name=dud_name,
                                                                     version=dud_version,
                                                                     release=dud_release,
                                                                     arch=arch)
        cmd.extend([
            "/usr/bin/xorrisofs -quiet -lR -V OEMDRV -input-charset utf8 -o {} ".format(iso_name) +
            "./dd -v"
        ])
        rv = broot.mock(['--cwd', broot.tmpdir(within=True), '--chroot', '--'] + cmd)
        if rv:
            raise koji.GenericError("DUD build failed while xorrisofs: " + str(rv))

        fpath = os.path.join(broot.tmpdir(), iso_name)
        img_file = os.path.basename(fpath)
        self.uploadFile(fpath, remoteName=os.path.basename(img_file))
        imgdata['files'].append(img_file)

        if not self.opts.get('scratch'):
            hdrlist = self.getImagePackagesFromPath(broot.tmpdir())
            broot.markExternalRPMs(hdrlist)
            imgdata['rpmlist'] = hdrlist

        broot.expire()
        self.logger.error("Uploading image data: %s", imgdata)
        return imgdata
