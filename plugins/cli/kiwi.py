from optparse import OptionParser

from koji import canonArch

from koji.plugin import export_cli
from koji_cli.lib import (
    _running_in_bg,
    activate_session,
    watch_tasks,
)


@export_cli
def handle_kiwi_build(goptions, session, args):
    "[build] Run a command in a buildroot"
    usage = "usage: %prog kiwi-build [options] <target> <description_scm> <description_path>"
    usage += "\n(Specify the --help global option for a list of other help options)"
    parser = OptionParser(usage=usage)
    parser.add_option("--scratch", action="store_true", default=False,
                      help="Perform a scratch build")
    parser.add_option("--repo", action="append",
                      help="Specify a repo that will override the repo used to install "
                           "RPMs in the image. May be used multiple times. The "
                           "build tag repo associated with the target is the default.")
    parser.add_option("--noprogress", action="store_true",
                      help="Do not display progress of the upload")
    parser.add_option("--kiwi-profile", action="store", default=None,
                      help="Select profile from description file")
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
        'scratch': options.scratch,
        'optional_arches': [canonArch(arch)
                            for arch in options.optional_arches.split(',')
                            if arch],
        'profile': options.kiwi_profile,
    }

    arches = []
    if options.arches:
        arches = [canonArch(arch) for arch in options.arches]

    task_id = session.kiwiBuild(
        target=target,
        arches=arches,
        desc_url=scm,
        desc_path=path,
        **kwargs)

    if not goptions.quiet:
        print("Created task: %d" % task_id)
        print("Task info: %s/taskinfo?taskID=%s" % (goptions.weburl, task_id))
    if options.wait or (options.wait is None and not _running_in_bg()):
        session.logout()
        return watch_tasks(session, [task_id], quiet=goptions.quiet,
                           poll_interval=goptions.poll_interval, topurl=goptions.topurl)
