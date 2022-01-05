import glob
import json
from json.decoder import JSONDecodeError
import os
import xml.dom.minidom
from fnmatch import fnmatch

import koji
from koji.util import joinpath, to_list
from koji.tasks import ServerExit
from __main__ import BaseBuildTask, BuildImageTask, BuildRoot, SCM


class KiwiBuildTask(BuildImageTask):
    Methods = ['kiwiBuild']
    _taskWeight = 4.0

    def get_nvrp(self, desc_path):
        # TODO: update release in desc
        kiwi_files = glob.glob('%s/*.kiwi' % desc_path)
        if len(kiwi_files) != 1:
            raise koji.GenericError("Repo must contain only one .kiwi file.")

        cfg = kiwi_files[0]

        newxml = xml.dom.minidom.parse(cfg)  # nosec
        image = newxml.getElementsByTagName('image')[0]

        name = image.getAttribute('name')
        version = None
        release = None
        for preferences in image.getElementsByTagName('preferences'):
            try:
                version = preferences.getElementsByTagName('version')[0].childNodes[0].data
            except Exception:
                pass
            try:
                release = preferences.getElementsByTagName('release')[0].childNodes[0].data
            except Exception:
                release = None
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
        return name, version, release, profile

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

        name, version, release, default_profile = self.get_nvrp(path)
        if opts.get('profile') or default_profile:
            # package name is a combination of name + profile
            # in case profiles are not used, let's use the standalone name
            name = "%s-%s" % (name, opts.get('profile', default_profile))

        bld_info = {}
        if not opts['scratch']:
            bld_info = self.initImageBuild(name, version, release, target_info, opts)
            release = bld_info['release']
        elif not release:
            release = self.session.getNextRelease({'name': name, 'version': version})

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
            results = self.wait(to_list(subtasks.values()), all=True,
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

    def prepareDescription(self, desc_path, name, version, release, repos):
        # TODO: update release in desc
        kiwi_files = glob.glob('%s/*.kiwi' % desc_path)
        if len(kiwi_files) != 1:
            raise koji.GenericError("Repo must contain only one .kiwi file.")

        cfg = kiwi_files[0]

        newxml = xml.dom.minidom.parse(cfg)  # nosec
        image = newxml.getElementsByTagName('image')[0]

        # apply includes - kiwi can include only top-level nodes, so we can simply
        # go through "include" elements and replace them with referred content (without
        # doing it recursively)
        for inc_node in image.getElementsByTagName('include'):
            path = inc_node.getAttribute('from')
            inc = xml.dom.minidom.parse(path)  # nosec
            # every included xml has image root element again
            for node in inc.getElementsByTagName('image').childNodes:
                if node.nodeName != 'repository':
                    image.appendChild(node)

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

        # TODO: release is part of version (major.minor.release)
        # try:
        #    preferences.getElementsByTagName('release')[0].childNodes[0].data = release
        # except Exception:
        #    rel_node = newxml.createElement('release')
        #    text = newxml.createTextNode(release)
        #    rel_node.appendChild(rel_node)
        #    preferences.appendChild(rel_node)

        types = []
        for pref in image.getElementsByTagName('preferences'):
            for type in pref.getElementsByTagName('type'):
                # TODO: if type.getAttribute('primary') == 'true':
                types.append(type.getAttribute('image'))

        # write file back
        with open(cfg, 'wt') as f:
            s = newxml.toprettyxml()
            # toprettyxml adds too many whitespaces/newlines
            s = '\n'.join([x for x in s.splitlines() if x.strip()])
            f.write(s)

        return cfg, types

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
        broot = BuildRoot(self.session, self.options,
                          tag=build_tag,
                          arch=arch,
                          task_id=self.id,
                          repo_id=repo_info['id'],
                          install_group='kiwi',
                          setup_dns=True,
                          bind_opts={'dirs': {'/dev': '/dev', }})
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

        # user repos
        repos = self.opts.get('repos', [])
        # buildroot repo
        path_info = koji.PathInfo(topdir=self.options.topurl)
        repopath = path_info.repo(repo_info['id'], target_info['build_tag_name'])
        baseurl = '%s/%s' % (repopath, arch)
        self.logger.debug('BASEURL: %s' % baseurl)
        repos.append(baseurl)

        path = os.path.join(scmsrcdir, desc_path)
        desc, types = self.prepareDescription(path, name, version, release, repos)
        self.uploadFile(desc)

        cmd = ['kiwi-ng']
        if self.opts.get('profile'):
            cmd.extend(['--profile', self.opts['profile']])
        target_dir = '/builddir/result/image'
        cmd.extend([
            'system', 'build',
            '--description', os.path.join(os.path.basename(scmsrcdir), desc_path),
            '--target-dir', target_dir,
        ])
        rv = broot.mock(['--cwd', broot.tmpdir(within=True), '--chroot', '--'] + cmd)
        if rv:
            raise koji.GenericError("Kiwi failed")

        resultdir = joinpath(broot.rootdir(), target_dir[1:])
        try:
            # new version has json format, older pickle (needs python3-kiwi installed)
            result_files = json.load(open(joinpath(resultdir, 'kiwi.result.json')))
        except (FileNotFoundError, JSONDecodeError):
            # try old variant
            import pickle
            result = pickle.load(open(joinpath(resultdir, 'kiwi.result'), 'rb')) # nosec
            # convert from namedtuple's to normal dict
            result_files = {k: v._asdict() for k, v in result.result_files.items()}

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
            self.uploadFile(root_log_path, remoteName="image-root.log")

        # for type in types:
        #     img_file = '%s.%s-%s.%s' % (name, version, arch, type)
        #     self.uploadFile(os.path.join(broot.rootdir()), remoteName=img_file)
        #     imgdata['files'].append(img_file)
        for ftype in ('disk_image', 'disk_format_image', 'installation_image'):
            fdata = result_files.get(ftype)
            if not fdata:
                continue
            fpath = os.path.join(broot.rootdir(), fdata['filename'][1:])
            img_file = os.path.basename(fpath)
            self.uploadFile(fpath, remoteName=os.path.basename(img_file))
            imgdata['files'].append(img_file)

        if not self.opts.get('scratch'):
            if False:
                # should be used after kiwi update
                fpath = os.path.join(broot.rootdir(),
                                     result_files['image_packages'].filename[1:])
                hdrlist = self.getImagePackages(fpath)
            else:
                cachepath = os.path.join(broot.rootdir(), 'var/cache/kiwi/dnf')
                hdrlist = self.getImagePackagesFromCache(cachepath)
            broot.markExternalRPMs(hdrlist)
            imgdata['rpmlist'] = hdrlist

        broot.expire()

        self.logger.error("Uploading image data: %s", imgdata)
        return imgdata
