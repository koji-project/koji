from __future__ import absolute_import

from optparse import OptionParser

import koji
from koji.plugin import export_cli
from koji_cli.lib import _, activate_session, watch_tasks


@export_cli
def handle_save_failed_tree(options, session, args):
    "Create tarball with whole buildtree"
    usage = _("usage: %prog save-failed-tree [options] ID")
    usage += _("\n(Specify the --help global option for a list of other help options)")
    parser = OptionParser(usage=usage)
    parser.add_option("-f", "--full", action="store_true", default=False,
                      help=_("Download whole tree, if not specified, "
                             "only builddir will be downloaded"))
    parser.add_option("-t", "--task", action="store_const", dest="mode",
                      const="task", default="task",
                      help=_("Treat ID as a task ID (the default)"))
    parser.add_option("-r", "--buildroot", action="store_const", dest="mode",
                      const="buildroot",
                      help=_("Treat ID as a buildroot ID"))
    parser.add_option("--quiet", action="store_true", default=options.quiet,
                      help=_("Do not print the task information"))
    parser.add_option("--nowait", action="store_true",
                      help=_("Don't wait on build"))

    (opts, args) = parser.parse_args(args)

    if len(args) != 1:
        parser.error(_("List exactly one task or buildroot ID"))

    try:
        id_val = int(args[0])
    except ValueError:
        parser.error(_("ID must be an integer"))

    activate_session(session, options)

    if opts.mode == "buildroot":
        br_id = id_val
    else:
        brs = [b['id'] for b in session.listBuildroots(taskID=id_val)]
        if not brs:
            print(_("No buildroots for task %s") % id_val)
            return 1
        br_id = max(brs)
        if len(brs) > 1:
            print(_("Multiple buildroots for task. Choosing last one (%s)") % br_id)

    try:
        task_id = session.saveFailedTree(br_id, opts.full)
    except koji.GenericError as e:
        m = str(e)
        if 'Invalid method' in m:
            print(_("* The save_failed_tree plugin appears to not be "
                    "installed on the koji hub.  Please contact the "
                    "administrator."))
            return 1
        raise

    if not opts.quiet:
        print(_("Created task %s for buildroot %s") % (task_id, br_id))
        print("Task info: %s/taskinfo?taskID=%s"
              % (options.weburl, task_id))

    if opts.nowait:
        return
    else:
        session.logout()
        return watch_tasks(session, [task_id],
                           quiet=opts.quiet, poll_interval=options.poll_interval,
                           topurl=options.topurl)
