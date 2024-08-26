from optparse import OptionParser

from koji import canonArch

from koji.plugin import export_cli
from koji_cli.lib import (
    _running_in_bg,
    activate_session,
    watch_tasks,
    warn,
)


@export_cli
def handle_kiwi_build(goptions, session, args):
    "[build] Run a command in a buildroot"
    usage = "usage: %prog kiwi-build [options] <target> <description_scm> <description_path>"
    usage += "\n(Specify the --help global option for a list of other help options)"
    parser = OptionParser(usage=usage)
    parser.add_option("--scratch", action="store_true", default=False,
                      help="Perform a scratch build")
    parser.add_option("--version", help="Override default version of the output image")
    parser.add_option("--release", help="Release of the output image")
    parser.add_option("--repo", action="append",
                      help="Specify a repo that will override the repo used to install "
                           "RPMs in the image. May be used multiple times. The "
                           "build tag repo associated with the target is the default.")
    parser.add_option("--repo-releasever", help="Override default releasever of the output image")
    parser.add_option("--noprogress", action="store_true",
                      help="Do not display progress of the upload")
    parser.add_option("--kiwi-profile", action="store", default=None,
                      help="Select profile from description file")
    parser.add_option("--type", help="Override default build type from description")
    parser.add_option("--type-attr", action="append", default=[],
                      help="Override default attributes for the build type from description. "
                           "May be used multiple times.")
    parser.add_option("--result-bundle-name-format", help="Override default bundle name format")
    parser.add_option("--make-prep", action="store_true", default=False,
                      help="Run 'make prep' in checkout before starting the build")
    parser.add_option("--buildroot-repo", action="store_true",
                      dest="use_buildroot_repo", default=False,
                      help="Add buildroot repo to installation sources. This is off by default, "
                           "but if there is no --repo used, it will be turned on automatically.")
    parser.add_option("--can-fail", action="store", dest="optional_arches",
                      metavar="ARCH1,ARCH2,...", default="",
                      help="List of archs which are not blocking for build "
                           "(separated by commas.")
    parser.add_option("--arch", action="append", dest="arches", default=[],
                      help="Limit arches to this subset")
    parser.add_option("--nowait", action="store_false", dest="wait", default=True)
    parser.add_option("--wait", action="store_true",
                      help="Wait on the image creation, even if running in the background")
    (options, args) = parser.parse_args(args)

    if len(args) != 3:
        parser.error("Incorrect number of arguments")
        assert False  # pragma: no cover
    target, scm, path = args

    activate_session(session, goptions)
    kwargs = {
        'arches': [],
        'target': target,
        'desc_url': scm,
        'desc_path': path,
    }
    if options.scratch:
        kwargs['scratch'] = True
    if options.optional_arches:
        kwargs['optional_arches'] = [
            canonArch(arch)
            for arch in options.optional_arches.split(',')
            if arch]
    if options.kiwi_profile:
        kwargs['profile'] = options.kiwi_profile
    if options.version:
        kwargs['version'] = options.version
    if options.release:
        kwargs['release'] = options.release
    if options.make_prep:
        kwargs['make_prep'] = True
    if options.type:
        kwargs['type'] = options.type
    if options.type_attr:
        kwargs['type_attr'] = options.type_attr
    if options.result_bundle_name_format:
        kwargs['result_bundle_name_format'] = options.result_bundle_name_format
    if options.arches:
        kwargs['arches'] = [canonArch(arch) for arch in options.arches]
    if options.repo:
        kwargs['repos'] = options.repo
    if options.repo_releasever:
        kwargs['repo_releasever'] = options.repo_releasever

    if session.hub_version < (1, 35, 0):
        warn("hub version is < 1.35, buildroot repo is always used in addition to specified repos")
    elif options.use_buildroot_repo:
        kwargs['use_buildroot_repo'] = True
    elif not options.repo:
        warn("no repos given, using buildroot repo")
        kwargs['use_buildroot_repo'] = True

    task_id = session.kiwiBuild(**kwargs)

    if not goptions.quiet:
        print("Created task: %d" % task_id)
        print("Task info: %s/taskinfo?taskID=%s" % (goptions.weburl, task_id))
    if options.wait or (options.wait is None and not _running_in_bg()):
        session.logout()
        return watch_tasks(session, [task_id], quiet=goptions.quiet,
                           poll_interval=goptions.poll_interval, topurl=goptions.topurl)
