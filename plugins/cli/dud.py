from optparse import OptionParser

from koji import canonArch

from koji.plugin import export_cli
from koji_cli.lib import (
    _running_in_bg,
    activate_session,
    watch_tasks,
)

# All client related stuff, to be located in ~/.koji/plugins/dud.py


@export_cli
def handle_dud_build(goptions, session, args):
    "[build] Run a command in a buildroot"
    usage = ("usage: %prog dud-build [options] <koji_target> --scmurl=<git_repo> <dud_name>"
             "<version> <pkg(nvr optional)> [<pkg> ...]")
    usage += "\n(Specify the --help global option for a list of other help options)"
    parser = OptionParser(usage=usage)
    parser.add_option("--scratch", action="store_true", default=False,
                      help="Perform a scratch build")
    parser.add_option("--scmurl", metavar="SCMURL", default=None,
                      help="SCM repository URL for non-rpm related content to be included "
                      "in the ISO")
    parser.add_option("--alldeps", action="store_true", default=False,
                      help="Download all involved rpm dependencies and put them inside "
                      "the DUD ISO as well")
    parser.add_option("--arch", action="append", dest="arches", default=[],
                      help="Limit arches to this subset")
    parser.add_option("--can-fail", action="store", dest="optional_arches",
                      metavar="ARCH1,ARCH2,...", default="",
                      help="List of archs which are not blocking for build "
                           "(separated by commas.")
    parser.add_option("--nowait", action="store_false", dest="wait", default=True)
    parser.add_option("--wait", action="store_true",
                      help="Wait on the image creation, even if running in the background")
    (options, args) = parser.parse_args(args)

    if len(args) < 4:
        parser.error("Incorrect number of arguments")
        assert False  # pragma: no cover
    pkg_list = []

    # Can't use * operator with unpacking in Python 2.7, but this works for both Python 2 and 3
    target, dud_name, dud_version, pkg_list = args[0], args[1], args[2], args[3:]

    activate_session(session, goptions)

    kwargs = {
        'scratch': options.scratch,
        'alldeps': options.alldeps,
        'scmurl': options.scmurl,
        'optional_arches': [canonArch(arch)
                            for arch in options.optional_arches.split(',')
                            if arch],
    }

    arches = []
    if options.arches:
        arches = [canonArch(arch) for arch in options.arches]

    task_id = session.dudBuild(
        target=target,
        arches=arches,
        dud_version=dud_version,
        dud_name=dud_name,
        pkg_list=pkg_list,
        **kwargs)

    if not goptions.quiet:
        print("Created task: %d" % task_id)
        print("Task info: %s/taskinfo?taskID=%s" % (goptions.weburl, task_id))
    if options.wait or (options.wait is None and not _running_in_bg()):
        session.logout()
        return watch_tasks(session, [task_id], quiet=goptions.quiet,
                           poll_interval=goptions.poll_interval, topurl=goptions.topurl)
