import os
import xml.dom.minidom
from fnmatch import fnmatch

import koji
import koji.util
from koji.tasks import ServerExit
from __main__ import BaseBuildTask, BuildImageTask, BuildRoot, SCM


class KiwiBuildTask(BuildImageTask):
    Methods = ['kiwiBuild']
    _taskWeight = 4.0

    def get_nvrp(self, cfg):
        try:
            newxml = xml.dom.minidom.parse(cfg)  # nosec
        except Exception:
            raise koji.GenericError(
                f"Kiwi description {os.path.basename(cfg)} can't be parsed as XML.")
        try:
            image = newxml.getElementsByTagName('image')[0]
        except IndexError:
            raise koji.GenericError(
                f"Kiwi description {os.path.basename(cfg)} doesn't contain <image> tag.")

        name = image.getAttribute('name')
        version = None
        for preferences in image.getElementsByTagName('preferences'):
            try:
                version = preferences.getElementsByTagName('version')[0].childNodes[0].data
            except Exception:
                pass
        profile = None
        try:
            for p in image.getElementsByTagName('profiles')[0].getElementsByTagName('profile'):
                if p.getAttribute('image') == 'true':
                    profile = p.getAttribute('name')
        except IndexError:
            # missing profiles section
            pass
        if not version:
            raise koji.BuildError("Description file doesn't contain preferences/version")
        return name, version, profile

    def handler(self, target, arches, desc_url, desc_path, opts=None):
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
        if not opts.get('optional_arches'):
            opts['optional_arches'] = []
        self.opts = opts

        # get configuration
        scm = SCM(desc_url)
        scm.assert_allowed(allowed=self.options.allowed_scms,
                           session=self.session,
                           by_config=self.options.allowed_scms_use_config,
                           by_policy=self.options.allowed_scms_use_policy,
                           policy_data={
                               'user_id': self.taskinfo['owner'],
                               'channel': self.session.getChannel(self.taskinfo['channel_id'],
                                                                  strict=True)['name'],
                               'scratch': opts['scratch'],
                           })
        logfile = os.path.join(self.workdir, 'checkout.log')
        self.run_callbacks('preSCMCheckout', scminfo=scm.get_info(),
                           build_tag=build_tag, scratch=opts['scratch'])
        scmdir = self.workdir
        koji.ensuredir(scmdir)
        scmsrcdir = scm.checkout(scmdir, self.session,
                                 self.getUploadDir(), logfile)
        self.run_callbacks("postSCMCheckout",
                           scminfo=scm.get_info(),
                           build_tag=build_tag,
                           scratch=opts['scratch'],
                           srcdir=scmsrcdir)

        path = os.path.join(scmsrcdir, desc_path)

        name, version, default_profile = self.get_nvrp(path)
        if opts.get('profile') or default_profile:
            # package name is a combination of name + profile
            # in case profiles are not used, let's use the standalone name
            name = "%s-%s" % (name, opts.get('profile', default_profile))

        bld_info = {}
        if opts.get('release'):
            release = opts['release']
        else:
            release = self.session.getNextRelease({'name': name, 'version': version})
        if not opts['scratch']:
            bld_info = self.initImageBuild(name, version, release, target_info, opts)
            release = bld_info['release']

        try:
            subtasks = {}
            canfail = []
            self.logger.debug("Spawning jobs for image arches: %r" % (arches))
            for arch in arches:
                subtasks[arch] = self.session.host.subtask(
                    method='createKiwiImage',
                    arglist=[name, version, release, arch,
                             target_info, build_tag, repo_info,
                             desc_url, desc_path, opts],
                    label=arch, parent=self.id, arch=arch)
                if arch in self.opts['optional_arches']:
                    canfail.append(subtasks[arch])
            self.logger.debug("Got image subtasks: %r" % (subtasks))
            self.logger.debug("Waiting on image subtasks (%s can fail)..." % canfail)
            results = self.wait(list(subtasks.values()), all=True,
                                failany=True, canfail=canfail)

            # if everything failed, fail even if all subtasks are in canfail
            self.logger.debug('subtask results: %r', results)
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

            self.logger.debug('Image Results for hub: %s' % results)
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


class KiwiCreateImageTask(BaseBuildTask):
    Methods = ['createKiwiImage']
    _taskWeight = 2.0

    def prepareDescription(self, desc_path, name, version, repos, arch):
        # XML errors should have already been caught by parent task
        newxml = xml.dom.minidom.parse(desc_path)  # nosec
        image = newxml.getElementsByTagName('image')[0]

        # apply includes - kiwi can include only top-level nodes, so we can simply
        # go through "include" elements and replace them with referred content (without
        # doing it recursively)
        for inc_node in image.getElementsByTagName('include'):
            path = inc_node.getAttribute('from')
            if path.startswith('this://'):
                path = koji.util.joinpath(os.path.dirname(desc_path), path[7:])
            else:
                # we want to reject other protocols, e.g. file://, https://
                # reachingoutside of repo
                raise koji.GenericError(f"Unhandled include protocol in include path: {path}.")
            inc = xml.dom.minidom.parse(path)  # nosec
            # every included xml has image root element again
            for node in list(inc.getElementsByTagName('image')[0].childNodes):
                if node.nodeName != 'repository':
                    image.appendChild(node)
            image.removeChild(inc_node)

        # remove remaining old repos
        for old_repo in image.getElementsByTagName('repository'):
            image.removeChild(old_repo)

        # add koji ones
        for repo in sorted(set(repos)):
            repo_node = newxml.createElement('repository')
            repo_node.setAttribute('type', 'rpm-md')
            source = newxml.createElement('source')
            source.setAttribute('path', repo)
            repo_node.appendChild(source)
            image.appendChild(repo_node)

        image.setAttribute('name', name)
        preferences = image.getElementsByTagName('preferences')[0]
        try:
            preferences.getElementsByTagName('release-version')[0].childNodes[0].data = version
        except IndexError:
            releasever_node = newxml.createElement('release-version')
            text = newxml.createTextNode(version)
            releasever_node.appendChild(text)
            preferences.appendChild(releasever_node)

        types = []
        for pref in image.getElementsByTagName('preferences'):
            for type in pref.getElementsByTagName('type'):
                # TODO: if type.getAttribute('primary') == 'true':
                types.append(type.getAttribute('image'))

        # write new file
        newcfg = os.path.splitext(desc_path)[0] + f'.{arch}.kiwi'
        with open(newcfg, 'wt') as f:
            s = newxml.toprettyxml()
            # toprettyxml adds too many whitespaces/newlines
            s = '\n'.join([x for x in s.splitlines() if x.strip()])
            f.write(s)
        os.unlink(desc_path)

        return newcfg, types

    def getImagePackagesFromCache(self, cachepath):
        """
        Read RPM header information from the yum cache available in the
        given path. Returns a list of dictionaries for each RPM included.
        """
        found = False
        hdrlist = {}
        fields = ['name', 'version', 'release', 'epoch', 'arch',
                  'buildtime', 'sigmd5']
        for root, dirs, files in os.walk(cachepath):
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
            raise koji.LiveCDError('No repos found in yum cache!')
        return list(hdrlist.values())

    def getImagePackages(self, result):
        """Proper handler for getting rpminfo from result list,
        it need result list to contain payloadhash, etc. to work correctly"""
        hdrlist = []
        for line in open(result, 'rt'):
            line = line.strip()
            name, epoch, version, release, arch, disturl, license = line.split('|')
            if epoch == '(none)':
                epoch = None
            else:
                epoch = int(epoch)
            hdrlist.append({
                'name': name,
                'epoch': epoch,
                'version': version,
                'release': release,
                'arch': arch,
                'payloadhash': '',
                'size': 0,
                'buildtime': 0,
            })

        return hdrlist

    def handler(self, name, version, release, arch,
                target_info, build_tag, repo_info,
                desc_url, desc_path, opts=None):
        self.opts = opts
        build_tag = target_info['build_tag']
        if opts.get('bind_dev'):
            bind_opts = {'dirs': {'/dev': '/dev'}}
        else:
            bind_opts = None
        broot = BuildRoot(self.session, self.options,
                          tag=build_tag,
                          arch=arch,
                          task_id=self.id,
                          repo_id=repo_info['id'],
                          install_group='kiwi-build',
                          setup_dns=True,
                          bind_opts=bind_opts)
        broot.workdir = self.workdir

        # create the mock chroot
        self.logger.debug("Initializing kiwi buildroot")
        broot.init()
        self.logger.debug("Kiwi buildroot ready: " + broot.rootdir())

        # get configuration
        scm = SCM(desc_url)
        scm.assert_allowed(allowed=self.options.allowed_scms,
                           session=self.session,
                           by_config=self.options.allowed_scms_use_config,
                           by_policy=self.options.allowed_scms_use_policy,
                           policy_data={
                               'user_id': self.taskinfo['owner'],
                               'channel': self.session.getChannel(self.taskinfo['channel_id'],
                                                                  strict=True)['name'],
                               'scratch': self.opts.get('scratch', False)
                           })
        logfile = os.path.join(self.workdir, 'checkout-%s.log' % arch)
        self.run_callbacks('preSCMCheckout', scminfo=scm.get_info(),
                           build_tag=build_tag, scratch=self.opts.get('scratch', False))
        scmdir = broot.tmpdir()
        koji.ensuredir(scmdir)
        scmsrcdir = scm.checkout(scmdir, self.session,
                                 self.getUploadDir(), logfile)
        self.run_callbacks("postSCMCheckout",
                           scminfo=scm.get_info(),
                           build_tag=build_tag,
                           scratch=self.opts.get('scratch', False),
                           srcdir=scmsrcdir)

        # user repos
        repos = self.opts.get('repos', [])
        # buildroot repo
        path_info = koji.PathInfo(topdir=self.options.topurl)
        repopath = path_info.repo(repo_info['id'], target_info['build_tag_name'])
        baseurl = '%s/%s' % (repopath, arch)
        self.logger.debug('BASEURL: %s' % baseurl)
        repos.append(baseurl)

        base_path = os.path.dirname(desc_path)
        if opts.get('make_prep'):
            cmd = ['make', 'prep']
            rv = broot.mock(['--cwd', os.path.join(broot.tmpdir(within=True),
                                                   os.path.basename(scmsrcdir), base_path),
                             '--chroot', '--'] + cmd)
            if rv:
                raise koji.GenericError("Preparation step failed")

        path = os.path.join(scmsrcdir, desc_path)
        desc, types = self.prepareDescription(path, name, version, repos, arch)
        self.uploadFile(desc)

        cmd = ['kiwi-ng']
        if self.opts.get('profile'):
            cmd.extend(['--profile', self.opts['profile']])
        if self.opts.get('type'):
            cmd.extend(['--type', self.opts['type']])
        target_dir = '/builddir/result/image'
        cmd.extend([
            '--kiwi-file', os.path.basename(desc),  # global option for image/system commands
            'system', 'build',
            '--description', os.path.join(os.path.basename(scmsrcdir), base_path),
            '--target-dir', target_dir,
        ])
        rv = broot.mock(['--cwd', broot.tmpdir(within=True), '--chroot', '--'] + cmd)
        if rv:
            raise koji.GenericError("Kiwi failed")

        # rename artifacts accordingly to release
        bundle_dir = '/builddir/result/bundle'
        cmd = ['kiwi-ng', 'result', 'bundle',
               '--target-dir', target_dir,
               '--bundle-dir', bundle_dir,
               '--id', release]
        rv = broot.mock(['--cwd', broot.tmpdir(within=True), '--chroot', '--'] + cmd)
        if rv:
            raise koji.GenericError("Kiwi failed")

        imgdata = {
            'arch': arch,
            'task_id': self.id,
            'logs': [
                os.path.basename(desc),
            ],
            'name': name,
            'version': version,
            'release': release,
            'rpmlist': [],
            'files': [],
        }

        # TODO: upload detailed log?
        # build/image-root.log
        root_log_path = os.path.join(broot.tmpdir(), target_dir[1:], "build/image-root.log")
        if os.path.exists(root_log_path):
            self.uploadFile(root_log_path, remoteName=f"image-root.{arch}.log")

        bundle_path = os.path.join(broot.rootdir(), bundle_dir[1:])
        for fname in os.listdir(bundle_path):
            self.uploadFile(os.path.join(bundle_path, fname), remoteName=fname)
            imgdata['files'].append(fname)

        if not self.opts.get('scratch'):
            if False:
                # should be used after kiwi update
                fpath = os.path.join(
                    bundle_path,
                    next(f for f in imgdata['files'] if f.endswith('.packages')),
                )
                hdrlist = self.getImagePackages(fpath)
            else:
                cachepath = os.path.join(broot.rootdir(), 'var/cache/kiwi/dnf')
                hdrlist = self.getImagePackagesFromCache(cachepath)
            broot.markExternalRPMs(hdrlist)
            imgdata['rpmlist'] = hdrlist

        broot.expire()

        self.logger.error("Uploading image data: %s", imgdata)
        return imgdata
