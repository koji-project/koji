from __future__ import absolute_import, division

import ast
import dateutil.parser
import fnmatch
import itertools
import json
import logging
import os
import pprint
import random
import re
import stat
import sys
import textwrap
import time
import traceback
from datetime import datetime
from dateutil.tz import tzutc
from optparse import SUPPRESS_HELP, OptionParser

import six
import six.moves.xmlrpc_client
from six.moves import filter, map, range, zip

import koji
from koji.util import base64encode, extract_build_task, md5_constructor, to_list
from koji_cli.lib import (
    TimeOption,
    DatetimeJSONEncoder,
    _list_tasks,
    _progress_callback,
    _running_in_bg,
    activate_session,
    arg_filter,
    download_archive,
    download_file,
    download_rpm,
    ensure_connection,
    error,
    format_inheritance_flags,
    get_usage_str,
    greetings,
    linked_upload,
    list_task_output_all_volumes,
    print_task_headers,
    print_task_recurse,
    unique_path,
    warn,
    wait_repo,
    watch_logs,
    watch_tasks,
    truncate_string
)

try:
    import libcomps
except ImportError:  # pragma: no cover
    libcomps = None
    try:
        import yum.comps as yumcomps
    except ImportError:
        yumcomps = None


def _printable_unicode(s):
    if six.PY2:
        return s.encode('utf-8')
    else:  # no cover: 2.x
        return s


def handle_add_group(goptions, session, args):
    "[admin] Add a group to a tag"
    usage = "usage: %prog add-group <tag> <group>"
    parser = OptionParser(usage=get_usage_str(usage))
    (options, args) = parser.parse_args(args)
    if len(args) != 2:
        parser.error("Please specify a tag name and a group name")
    tag = args[0]
    group = args[1]

    activate_session(session, goptions)
    if not (session.hasPerm('admin') or session.hasPerm('tag')):
        parser.error("This action requires tag or admin privileges")

    dsttag = session.getTag(tag)
    if not dsttag:
        error("No such tag: %s" % tag)

    groups = dict([(p['name'], p['group_id']) for p in session.getTagGroups(tag, inherit=False)])
    group_id = groups.get(group, None)
    if group_id is not None:
        error("Group %s already exists for tag %s" % (group, tag))

    session.groupListAdd(tag, group)


def handle_block_group(goptions, session, args):
    "[admin] Block group in tag"
    usage = "usage: %prog block-group <tag> <group>"
    parser = OptionParser(usage=get_usage_str(usage))
    (options, args) = parser.parse_args(args)
    if len(args) != 2:
        parser.error("Please specify a tag name and a group name")
    tag = args[0]
    group = args[1]

    activate_session(session, goptions)
    if not (session.hasPerm('admin') or session.hasPerm('tag')):
        parser.error("This action requires tag or admin privileges")

    dsttag = session.getTag(tag)
    if not dsttag:
        error("No such tag: %s" % tag)

    groups = dict([(p['name'], p['group_id']) for p in session.getTagGroups(tag, inherit=False)])
    group_id = groups.get(group, None)
    if group_id is None:
        error("Group %s doesn't exist within tag %s" % (group, tag))

    session.groupListBlock(tag, group)


def handle_remove_group(goptions, session, args):
    "[admin] Remove group from tag"
    usage = "usage: %prog remove-group <tag> <group>"
    parser = OptionParser(usage=get_usage_str(usage))
    (options, args) = parser.parse_args(args)
    if len(args) != 2:
        parser.error("Please specify a tag name and a group name")
    tag = args[0]
    group = args[1]

    activate_session(session, goptions)
    if not (session.hasPerm('admin') or session.hasPerm('tag')):
        parser.error("This action requires tag or admin privileges")

    dsttag = session.getTag(tag)
    if not dsttag:
        error("No such tag: %s" % tag)

    groups = dict([(p['name'], p['group_id']) for p in session.getTagGroups(tag, inherit=False)])
    group_id = groups.get(group, None)
    if group_id is None:
        error("Group %s doesn't exist within tag %s" % (group, tag))

    session.groupListRemove(tag, group)


def handle_assign_task(goptions, session, args):
    "[admin] Assign a task to a host"
    usage = 'usage: %prog assign-task <task_id> <hostname>'
    parser = OptionParser(usage=get_usage_str(usage))
    parser.add_option('-f', '--force', action='store_true', default=False,
                      help='force to assign a non-free task')
    (options, args) = parser.parse_args(args)

    if len(args) != 2:
        parser.error('please specify a task id and a hostname')
    else:
        task_id = int(args[0])
        hostname = args[1]

    taskinfo = session.getTaskInfo(task_id, request=False)
    if taskinfo is None:
        raise koji.GenericError("No such task: %s" % task_id)

    hostinfo = session.getHost(hostname)
    if hostinfo is None:
        raise koji.GenericError("No such host: %s" % hostname)

    force = False
    if options.force:
        force = True

    activate_session(session, goptions)
    if not session.hasPerm('admin'):
        parser.error("This action requires admin privileges")

    ret = session.assignTask(task_id, hostname, force)
    if ret:
        print('assigned task %d to host %s' % (task_id, hostname))
    else:
        print('failed to assign task %d to host %s' % (task_id, hostname))


def handle_add_host(goptions, session, args):
    "[admin] Add a host"
    usage = "usage: %prog add-host [options] <hostname> <arch> [<arch> ...]"
    parser = OptionParser(usage=get_usage_str(usage))
    parser.add_option("--krb-principal",
                      help="set a non-default kerberos principal for the host")
    parser.add_option("--force", default=False, action="store_true",
                      help="if existing used is a regular user, convert it to a host")
    (options, args) = parser.parse_args(args)
    if len(args) < 2:
        parser.error("Please specify a hostname and at least one arch")
    host = args[0]
    activate_session(session, goptions)
    id = session.getHost(host)
    if id:
        error("%s is already in the database" % host)
    else:
        kwargs = {'force': options.force}
        if options.krb_principal is not None:
            kwargs['krb_principal'] = options.krb_principal
        id = session.addHost(host, args[1:], **kwargs)
        print("%s added: id %d" % (host, id))


def handle_edit_host(options, session, args):
    "[admin] Edit a host"
    usage = "usage: %prog edit-host <hostname> [<hostname> ...] [options]"
    parser = OptionParser(usage=get_usage_str(usage))
    parser.add_option("--arches",
                      help="Space or comma-separated list of supported architectures")
    parser.add_option("--capacity", type="float", help="Capacity of this host")
    parser.add_option("--description", metavar="DESC", help="Description of this host")
    parser.add_option("--comment", help="A brief comment about this host")
    (subopts, args) = parser.parse_args(args)
    if not args:
        parser.error("Please specify a hostname")

    activate_session(session, options)

    vals = {}
    for key, val in subopts.__dict__.items():
        if val is not None:
            vals[key] = val
    if 'arches' in vals:
        vals['arches'] = koji.parse_arches(vals['arches'])

    session.multicall = True
    for host in args:
        session.getHost(host)
    error_hit = False
    for host, [info] in zip(args, session.multiCall(strict=True)):
        if not info:
            warn("No such host: %s" % host)
            error_hit = True

    if error_hit:
        error("No changes made, please correct the command line")

    session.multicall = True
    for host in args:
        session.editHost(host, **vals)
    for host, [result] in zip(args, session.multiCall(strict=True)):
        if result:
            print("Edited %s" % host)
        else:
            print("No changes made to %s" % host)


def handle_add_host_to_channel(goptions, session, args):
    "[admin] Add a host to a channel"
    usage = "usage: %prog add-host-to-channel [options] <hostname> <channel>"
    parser = OptionParser(usage=get_usage_str(usage))
    parser.add_option("--list", action="store_true", help=SUPPRESS_HELP)
    parser.add_option("--new", action="store_true", help="Create channel if needed")
    parser.add_option("--force", action="store_true", help="force added, if possible")
    (options, args) = parser.parse_args(args)
    if not options.list and len(args) != 2:
        parser.error("Please specify a hostname and a channel")
    activate_session(session, goptions)
    if options.list:
        for channel in session.listChannels():
            print(channel['name'])
        return
    channel = args[1]
    if not options.new:
        channelinfo = session.getChannel(channel)
        if not channelinfo:
            error("No such channel: %s" % channel)

    host = args[0]
    hostinfo = session.getHost(host)
    if not hostinfo:
        error("No such host: %s" % host)
    kwargs = {}
    if options.new:
        kwargs['create'] = True
    if options.force:
        kwargs['force'] = True
    session.addHostToChannel(host, channel, **kwargs)


def handle_remove_host_from_channel(goptions, session, args):
    "[admin] Remove a host from a channel"
    usage = "usage: %prog remove-host-from-channel [options] <hostname> <channel>"
    parser = OptionParser(usage=get_usage_str(usage))
    (options, args) = parser.parse_args(args)
    if len(args) != 2:
        parser.error("Please specify a hostname and a channel")
    host = args[0]
    activate_session(session, goptions)
    hostinfo = session.getHost(host)
    if not hostinfo:
        error("No such host: %s" % host)
    hostchannels = [c['name'] for c in session.listChannels(hostinfo['id'])]

    channel = args[1]
    if channel not in hostchannels:
        error("Host %s is not a member of channel %s" % (host, channel))

    session.removeHostFromChannel(host, channel)


def handle_add_channel(goptions, session, args):
    "[admin] Add a channel"
    usage = "usage: %prog add-channel [options] <channel_name>"
    parser = OptionParser(usage=get_usage_str(usage))
    parser.add_option("--description", help="Description of channel")
    (options, args) = parser.parse_args(args)
    if len(args) != 1:
        parser.error("Please specify one channel name")
    activate_session(session, goptions)
    channel_name = args[0]
    try:
        channel_id = session.addChannel(channel_name, description=options.description)
    except koji.GenericError as ex:
        msg = str(ex)
        if 'channel %s already exists' % channel_name in msg:
            error("channel %s already exists" % channel_name)
        elif 'Invalid method:' in msg:
            error("addChannel is available on hub from Koji 1.26 version, your version is %s" %
                  session.hub_version_str)
        else:
            error(msg)
    print("%s added: id %d" % (args[0], channel_id))


def handle_edit_channel(goptions, session, args):
    "[admin] Edit a channel"
    usage = "usage: %prog edit-channel [options] <old-name>"
    parser = OptionParser(usage=get_usage_str(usage))
    parser.add_option("--name", help="New channel name")
    parser.add_option("--description", help="Description of channel")
    parser.add_option("--comment", help="Comment of channel")
    (options, args) = parser.parse_args(args)
    if len(args) != 1:
        parser.error("Incorrect number of arguments")
    activate_session(session, goptions)
    vals = {}
    for key, val in options.__dict__.items():
        if val is not None:
            vals[key] = val
    cinfo = session.getChannel(args[0])
    if not cinfo:
        error("No such channel: %s" % args[0])
    result = None
    try:
        result = session.editChannel(args[0], **vals)
    except koji.GenericError as ex:
        msg = str(ex)
        if 'Invalid method:' in msg:
            error("editChannel is available on hub from Koji 1.26 version, your version is %s" %
                  session.hub_version_str)
        else:
            warn(msg)
    if not result:
        error("No changes made, please correct the command line")


def handle_enable_channel(goptions, session, args):
    "[admin] Mark one or more channels as enabled"
    usage = "usage: %prog enable-channel [options] <channelname> [<channelname> ...]"
    parser = OptionParser(usage=get_usage_str(usage))
    parser.add_option("--comment", help="Comment indicating why the channel(s) are being enabled")
    (options, args) = parser.parse_args(args)

    if not args:
        parser.error("At least one channel must be specified")

    activate_session(session, goptions)
    with session.multicall() as m:
        result = [m.getChannel(channel, strict=False) for channel in args]
    error_hit = False
    for channel, id in zip(args, result):
        if not id.result:
            print("No such channel: %s" % channel)
            error_hit = True
    if error_hit:
        error("No changes made. Please correct the command line.")

    with session.multicall() as m:
        [m.enableChannel(channel, comment=options.comment) for channel in args]


def handle_disable_channel(goptions, session, args):
    "[admin] Mark one or more channels as disabled"
    usage = "usage: %prog disable-channel [options] <channelname> [<channelname> ...]"
    parser = OptionParser(usage=get_usage_str(usage))
    parser.add_option("--comment", help="Comment indicating why the channel(s) are being disabled")
    (options, args) = parser.parse_args(args)

    if not args:
        parser.error("At least one channel must be specified")

    activate_session(session, goptions)

    with session.multicall() as m:
        result = [m.getChannel(channel, strict=False) for channel in args]
    error_hit = False
    for channel, id in zip(args, result):
        if not id.result:
            print("No such channel: %s" % channel)
            error_hit = True
    if error_hit:
        error("No changes made. Please correct the command line.")
    with session.multicall() as m:
        [m.disableChannel(channel, comment=options.comment) for channel in args]


def handle_add_pkg(goptions, session, args):
    "[admin] Add a package to the listing for tag"
    usage = "usage: %prog add-pkg [options] --owner <owner> <tag> <package> [<package> ...]"
    parser = OptionParser(usage=get_usage_str(usage))
    parser.add_option("--force", action='store_true', help="Override blocks if necessary")
    parser.add_option("--owner", help="Specify owner")
    parser.add_option("--extra-arches", help="Specify extra arches")
    (options, args) = parser.parse_args(args)
    if len(args) < 2:
        parser.error("Please specify a tag and at least one package")
    if not options.owner:
        parser.error("Please specify an owner for the package(s)")
    if not session.getUser(options.owner):
        error("No such user: %s" % options.owner)
    activate_session(session, goptions)
    tag = args[0]
    opts = {}
    opts['force'] = options.force
    opts['block'] = False
    # check if list of packages exists for that tag already
    dsttag = session.getTag(tag)
    if dsttag is None:
        error("No such tag: %s" % tag)
    try:
        pkglist = session.listPackages(tagID=dsttag['id'], with_owners=False)
    except koji.ParameterError:
        # performance option added in 1.25
        pkglist = session.listPackages(tagID=dsttag['id'])
    pkglist = dict([(p['package_name'], p['package_id']) for p in pkglist])
    to_add = []
    for package in args[1:]:
        package_id = pkglist.get(package, None)
        if package_id is not None:
            print("Package %s already exists in tag %s" % (package, tag))
            continue
        to_add.append(package)
    if options.extra_arches:
        opts['extra_arches'] = koji.parse_arches(options.extra_arches)

    # add the packages
    print("Adding %i packages to tag %s" % (len(to_add), dsttag['name']))
    session.multicall = True
    for package in to_add:
        session.packageListAdd(tag, package, options.owner, **opts)
    session.multiCall(strict=True)


def handle_block_pkg(goptions, session, args):
    "[admin] Block a package in the listing for tag"
    usage = "usage: %prog block-pkg [options] <tag> <package> [<package> ...]"
    parser = OptionParser(usage=get_usage_str(usage))
    parser.add_option("--force", action='store_true', default=False,
                      help="Override blocks and owner if necessary")
    (options, args) = parser.parse_args(args)
    if len(args) < 2:
        parser.error("Please specify a tag and at least one package")
    activate_session(session, goptions)
    tag = args[0]
    # check if list of packages exists for that tag already
    dsttag = session.getTag(tag)
    if dsttag is None:
        error("No such tag: %s" % tag)
    try:
        pkglist = session.listPackages(tagID=dsttag['id'], inherited=True, with_owners=False)
    except koji.ParameterError:
        # performance option added in 1.25
        pkglist = session.listPackages(tagID=dsttag['id'], inherited=True)
    pkglist = dict([(p['package_name'], p['package_id']) for p in pkglist])
    ret = 0
    for package in args[1:]:
        package_id = pkglist.get(package, None)
        if package_id is None:
            warn("Package %s doesn't exist in tag %s" % (package, tag))
            ret = 1
    if ret:
        error(code=ret)
    session.multicall = True
    for package in args[1:]:
        # force is not supported on older hub, so use it only explicitly
        # https://pagure.io/koji/issue/1388
        if options.force:
            session.packageListBlock(tag, package, force=options.force)
        else:
            session.packageListBlock(tag, package)
    session.multiCall(strict=True)


def handle_remove_pkg(goptions, session, args):
    "[admin] Remove a package from the listing for tag"
    usage = "usage: %prog remove-pkg [options] <tag> <package> [<package> ...]"
    parser = OptionParser(usage=get_usage_str(usage))
    parser.add_option("--force", action='store_true', help="Override blocks if necessary")
    (options, args) = parser.parse_args(args)
    if len(args) < 2:
        parser.error("Please specify a tag and at least one package")
    activate_session(session, goptions)
    tag = args[0]
    opts = {}
    opts['force'] = options.force
    # check if list of packages exists for that tag already
    dsttag = session.getTag(tag)
    if dsttag is None:
        error("No such tag: %s" % tag)
    try:
        pkglist = session.listPackages(tagID=dsttag['id'], with_owners=False)
    except koji.ParameterError:
        # performance option added in 1.25
        pkglist = session.listPackages(tagID=dsttag['id'])
    pkglist = dict([(p['package_name'], p['package_id']) for p in pkglist])
    ret = 0
    for package in args[1:]:
        package_id = pkglist.get(package, None)
        if package_id is None:
            warn("Package %s is not in tag %s" % (package, tag))
            ret = 1
    if ret:
        error(code=ret)
    session.multicall = True
    for package in args[1:]:
        session.packageListRemove(tag, package, **opts)
    session.multiCall(strict=True)


def handle_build(options, session, args):
    "[build] Build a package from source"

    usage = """\
        usage: %prog build [options] <target> <srpm path or scm url>

        The first option is the build target, not to be confused with the destination
        tag (where the build eventually lands) or build tag (where the buildroot
        contents are pulled from).

        You can list all available build targets using the '%prog list-targets' command.
        More detail can be found in the documentation.
        https://docs.pagure.org/koji/HOWTO/#package-organization"""

    usage = textwrap.dedent(usage)
    parser = OptionParser(usage=get_usage_str(usage))
    parser.add_option("--skip-tag", action="store_true", help="Do not attempt to tag package")
    parser.add_option("--scratch", action="store_true", help="Perform a scratch build")
    parser.add_option("--rebuild-srpm", action="store_true", dest="rebuild_srpm",
                      help="Force rebuilding SRPM for scratch build only")
    parser.add_option("--no-rebuild-srpm", action="store_false", dest="rebuild_srpm",
                      help="Force not to rebuild srpm for scratch build only")
    parser.add_option("--wait", action="store_true",
                      help="Wait on the build, even if running in the background")
    parser.add_option("--nowait", action="store_false", dest="wait", help="Don't wait on build")
    parser.add_option("--wait-repo", action="store_true",
                      help="Wait for the actual buildroot repo of given target")
    parser.add_option("--wait-build", metavar="NVR", action="append", dest="wait_builds",
                      default=[], help="Wait for the given nvr to appear in buildroot repo")
    parser.add_option("--quiet", action="store_true",
                      help="Do not print the task information", default=options.quiet)
    parser.add_option("--arch-override", help="Override build arches")
    parser.add_option("--fail-fast", action="store_true",
                      help="Override build_arch_can_fail settings and fail as fast as possible")
    parser.add_option("--repo-id", type="int", help="Use a specific repo")
    parser.add_option("--noprogress", action="store_true",
                      help="Do not display progress of the upload")
    parser.add_option("--background", action="store_true",
                      help="Run the build at a lower priority")
    parser.add_option("--custom-user-metadata", type="str",
                      help="Provide a JSON string of custom metadata to be deserialized and "
                           "stored under the build's extra.custom_user_metadata field")
    parser.add_option("--draft", action="store_true",
                      help="Build draft build instead")
    (build_opts, args) = parser.parse_args(args)
    if len(args) != 2:
        parser.error("Exactly two arguments (a build target and a SCM URL or srpm file) are "
                     "required")
    if build_opts.rebuild_srpm is not None and not build_opts.scratch:
        parser.error("--no-/rebuild-srpm is only allowed for --scratch builds")
    if build_opts.arch_override and not build_opts.scratch:
        parser.error("--arch_override is only allowed for --scratch builds")
    if build_opts.scratch and build_opts.draft:
        parser.error("--scratch and --draft cannot be both specfied")
    custom_user_metadata = {}
    if build_opts.custom_user_metadata:
        try:
            custom_user_metadata = json.loads(build_opts.custom_user_metadata)
        # Use ValueError instead of json.JSONDecodeError for Python 2 and 3 compatibility
        except ValueError:
            parser.error("--custom-user-metadata is not valid JSON")

    if not isinstance(custom_user_metadata, dict):
        parser.error("--custom-user-metadata must be a JSON object")

    activate_session(session, options)
    target = args[0]
    if target.lower() == "none" and build_opts.repo_id:
        target = None
        build_opts.skip_tag = True
    else:
        build_target = session.getBuildTarget(target)
        if not build_target:
            parser.error("No such build target: %s" % target)
        dest_tag = session.getTag(build_target['dest_tag'])
        if not dest_tag:
            parser.error("No such destination tag: %s" % build_target['dest_tag_name'])
        if dest_tag['locked'] and not build_opts.scratch:
            parser.error("Destination tag %s is locked" % dest_tag['name'])
    source = args[1]
    opts = {}
    if build_opts.arch_override:
        opts['arch_override'] = koji.parse_arches(build_opts.arch_override)
    for key in ('skip_tag', 'scratch', 'repo_id', 'fail_fast', 'wait_repo', 'wait_builds',
                'rebuild_srpm', 'draft'):
        val = getattr(build_opts, key)
        if val is not None:
            opts[key] = val
    opts["custom_user_metadata"] = custom_user_metadata
    priority = None
    if build_opts.background:
        # relative to koji.PRIO_DEFAULT
        priority = 5
    # try to check that source is an SRPM
    if '://' not in source:
        # treat source as an srpm and upload it
        if not build_opts.quiet:
            print("Uploading srpm: %s" % source)
        serverdir = unique_path('cli-build')
        if _running_in_bg() or build_opts.noprogress or build_opts.quiet:
            callback = None
        else:
            callback = _progress_callback
        session.uploadWrapper(source, serverdir, callback=callback)
        print('')
        source = "%s/%s" % (serverdir, os.path.basename(source))
    task_id = session.build(source, target, opts, priority=priority)
    if not build_opts.quiet:
        print("Created task: %d" % task_id)
        print("Task info: %s/taskinfo?taskID=%s" % (options.weburl, task_id))
    if build_opts.wait or (build_opts.wait is None and not _running_in_bg()):
        session.logout()
        return watch_tasks(session, [task_id], quiet=build_opts.quiet,
                           poll_interval=options.poll_interval, topurl=options.topurl)


def handle_chain_build(options, session, args):
    # XXX - replace handle_build with this, once chain-building has gotten testing
    "[build] Build one or more packages from source"
    usage = "usage: %prog chain-build [options] <target> <URL> [<URL> [:] <URL> [:] <URL> ...]"
    parser = OptionParser(usage=get_usage_str(usage))
    parser.add_option("--wait", action="store_true",
                      help="Wait on build, even if running in the background")
    parser.add_option("--nowait", action="store_false", dest="wait", help="Don't wait on build")
    parser.add_option("--quiet", action="store_true",
                      help="Do not print the task information", default=options.quiet)
    parser.add_option("--background", action="store_true",
                      help="Run the build at a lower priority")
    (build_opts, args) = parser.parse_args(args)
    if len(args) < 2:
        parser.error("At least two arguments (a build target and a SCM URL) are required")
    activate_session(session, options)
    target = args[0]
    build_target = session.getBuildTarget(target)
    if not build_target:
        parser.error("No such build target: %s" % target)
    dest_tag = session.getTag(build_target['dest_tag'], strict=True)
    if dest_tag['locked']:
        parser.error("Destination tag %s is locked" % dest_tag['name'])

    # check that the destination tag is in the inheritance tree of the build tag
    # otherwise there is no way that a chain-build can work
    ancestors = session.getFullInheritance(build_target['build_tag'])
    if dest_tag['id'] not in [build_target['build_tag']] + \
            [ancestor['parent_id'] for ancestor in ancestors]:
        warn("Packages in destination tag %(dest_tag_name)s are not inherited by build tag "
             "%(build_tag_name)s" % build_target)
        error("Target %s is not usable for a chain-build" % build_target['name'])
    sources = args[1:]

    src_list = []
    build_level = []
    # src_lists is a list of lists of sources to build.
    #  each list is block of builds ("build level") which must all be completed
    #  before the next block begins. Blocks are separated on the command line with ':'
    for src in sources:
        if src == ':':
            if build_level:
                src_list.append(build_level)
                build_level = []
        elif '://' in src:
            # quick check that src might be a url
            build_level.append(src)
        elif '/' not in src and not src.endswith('.rpm') and len(src.split('-')) >= 3:
            # quick check that it looks like a N-V-R
            build_level.append(src)
        else:
            error('"%s" is not a SCM URL or package N-V-R' % src)
    if build_level:
        src_list.append(build_level)

    if len(src_list) < 2:
        parser.error('You must specify at least one dependency between builds with : (colon)\n'
                     'If there are no dependencies, use the build command instead')

    priority = None
    if build_opts.background:
        # relative to koji.PRIO_DEFAULT
        priority = 5

    task_id = session.chainBuild(src_list, target, priority=priority)
    if not build_opts.quiet:
        print("Created task: %d" % task_id)
        print("Task info: %s/taskinfo?taskID=%s" % (options.weburl, task_id))
    if build_opts.wait or (build_opts.wait is None and not _running_in_bg()):
        session.logout()
        return watch_tasks(session, [task_id], quiet=build_opts.quiet,
                           poll_interval=options.poll_interval, topurl=options.topurl)


def handle_maven_build(options, session, args):
    "[build] Build a Maven package from source"
    usage = "usage: %prog maven-build [options] <target> <URL>"
    usage += "\n       %prog maven-build --ini=CONFIG... [options] <target>"
    parser = OptionParser(usage=get_usage_str(usage))
    parser.add_option("--patches", action="store", metavar="URL",
                      help="SCM URL of a directory containing patches to apply to the sources "
                           "before building")
    parser.add_option("-G", "--goal", action="append", dest="goals", metavar="GOAL", default=[],
                      help="Additional goal to run before \"deploy\"")
    parser.add_option("-P", "--profile", action="append", dest="profiles", metavar="PROFILE",
                      default=[], help="Enable a profile for the Maven build")
    parser.add_option("-D", "--property", action="append", dest="properties", metavar="NAME=VALUE",
                      default=[], help="Pass a system property to the Maven build")
    parser.add_option("-E", "--env", action="append", dest="envs", metavar="NAME=VALUE",
                      default=[], help="Set an environment variable")
    parser.add_option("-p", "--package", action="append", dest="packages", metavar="PACKAGE",
                      default=[], help="Install an additional package into the buildroot")
    parser.add_option("-J", "--jvm-option", action="append", dest="jvm_options", metavar="OPTION",
                      default=[], help="Pass a command-line option to the JVM")
    parser.add_option("-M", "--maven-option", action="append", dest="maven_options",
                      metavar="OPTION", default=[], help="Pass a command-line option to Maven")
    parser.add_option("--ini", action="append", dest="inis", metavar="CONFIG", default=[],
                      help="Pass build parameters via a .ini file")
    parser.add_option("-s", "--section", help="Get build parameters from this section of the .ini")
    parser.add_option("--debug", action="store_true", help="Run Maven build in debug mode")
    parser.add_option("--specfile", action="store", metavar="URL",
                      help="SCM URL of a spec file fragment to use to generate wrapper RPMs")
    parser.add_option("--skip-tag", action="store_true", help="Do not attempt to tag package")
    parser.add_option("--scratch", action="store_true", help="Perform a scratch build")
    parser.add_option("--wait", action="store_true",
                      help="Wait on build, even if running in the background")
    parser.add_option("--nowait", action="store_false", dest="wait", help="Don't wait on build")
    parser.add_option("--quiet", action="store_true",
                      help="Do not print the task information", default=options.quiet)
    parser.add_option("--background", action="store_true",
                      help="Run the build at a lower priority")
    (build_opts, args) = parser.parse_args(args)
    if build_opts.inis:
        if len(args) != 1:
            parser.error("Exactly one argument (a build target) is required")
    else:
        if len(args) != 2:
            parser.error("Exactly two arguments (a build target and a SCM URL) are required")
    activate_session(session, options)
    target = args[0]
    build_target = session.getBuildTarget(target)
    if not build_target:
        parser.error("No such build target: %s" % target)
    dest_tag = session.getTag(build_target['dest_tag'])
    if not dest_tag:
        parser.error("No such destination tag: %s" % build_target['dest_tag_name'])
    if dest_tag['locked'] and not build_opts.scratch:
        parser.error("Destination tag %s is locked" % dest_tag['name'])
    if build_opts.inis:
        try:
            params = koji.util.parse_maven_param(build_opts.inis, scratch=build_opts.scratch,
                                                 section=build_opts.section)
        except ValueError as e:
            parser.error(e.args[0])
        opts = to_list(params.values())[0]
        if opts.pop('type', 'maven') != 'maven':
            parser.error("Section %s does not contain a maven-build config" %
                         to_list(params.keys())[0])
        source = opts.pop('scmurl')
    else:
        source = args[1]
        opts = koji.util.maven_opts(build_opts, scratch=build_opts.scratch)
    if '://' not in source:
        parser.error("No such SCM URL: %s" % source)
    if build_opts.debug:
        opts.setdefault('maven_options', []).append('--debug')
    if build_opts.skip_tag:
        opts['skip_tag'] = True
    priority = None
    if build_opts.background:
        # relative to koji.PRIO_DEFAULT
        priority = 5
    task_id = session.mavenBuild(source, target, opts, priority=priority)
    if not build_opts.quiet:
        print("Created task: %d" % task_id)
        print("Task info: %s/taskinfo?taskID=%s" % (options.weburl, task_id))
    if build_opts.wait or (build_opts.wait is None and not _running_in_bg()):
        session.logout()
        return watch_tasks(session, [task_id], quiet=build_opts.quiet,
                           poll_interval=options.poll_interval, topurl=options.topurl)


def handle_wrapper_rpm(options, session, args):
    """[build] Build wrapper rpms for any archives associated with a build."""
    usage = "usage: %prog wrapper-rpm [options] <target> <build-id|n-v-r> <URL>"
    parser = OptionParser(usage=get_usage_str(usage))
    parser.add_option("--create-build", action="store_true",
                      help="Create a new build to contain wrapper rpms")
    parser.add_option("--ini", action="append", dest="inis", metavar="CONFIG", default=[],
                      help="Pass build parameters via a .ini file")
    parser.add_option("-s", "--section",
                      help="Get build parameters from this section of the .ini")
    parser.add_option("--skip-tag", action="store_true",
                      help="If creating a new build, don't tag it")
    parser.add_option("--scratch", action="store_true", help="Perform a scratch build")
    parser.add_option("--wait", action="store_true",
                      help="Wait on build, even if running in the background")
    parser.add_option("--nowait", action="store_false", dest="wait", help="Don't wait on build")
    parser.add_option("--background", action="store_true",
                      help="Run the build at a lower priority")
    parser.add_option("--create-draft", action="store_true",
                      help="Create a new draft build instead")

    (build_opts, args) = parser.parse_args(args)
    if build_opts.inis:
        if len(args) != 1:
            parser.error("Exactly one argument (a build target) is required")
    else:
        if len(args) < 3:
            parser.error("You must provide a build target, a build ID or NVR, "
                         "and a SCM URL to a specfile fragment")
    if build_opts.create_draft:
        print("Will create a draft build instead")
        build_opts.create_build = True
        if build_opts.scratch:
            # TODO: --scratch and --create-build conflict too
            parser.error("--scratch and --create-draft cannot be both specfied")
    activate_session(session, options)

    target = args[0]
    if build_opts.inis:
        try:
            params = koji.util.parse_maven_param(build_opts.inis, scratch=build_opts.scratch,
                                                 section=build_opts.section)
        except ValueError as e:
            parser.error(e.args[0])
        opts = to_list(params.values())[0]
        if opts.get('type') != 'wrapper':
            parser.error("Section %s does not contain a wrapper-rpm config" %
                         to_list(params.keys())[0])
        url = opts['scmurl']
        package = opts['buildrequires'][0]
        target_info = session.getBuildTarget(target, strict=True)
        latest_builds = session.getLatestBuilds(target_info['dest_tag'], package=package)
        if not latest_builds:
            parser.error("No build of %s in %s" % (package, target_info['dest_tag_name']))
        build_id = latest_builds[0]['nvr']
    else:
        build_id = args[1]
        if build_id.isdigit():
            build_id = int(build_id)
        url = args[2]
    priority = None
    if build_opts.background:
        priority = 5
    opts = {}
    if build_opts.create_build:
        opts['create_build'] = True
    if build_opts.skip_tag:
        opts['skip_tag'] = True
    if build_opts.scratch:
        opts['scratch'] = True
    if build_opts.create_draft:
        opts['draft'] = True
    task_id = session.wrapperRPM(build_id, url, target, priority, opts=opts)
    print("Created task: %d" % task_id)
    print("Task info: %s/taskinfo?taskID=%s" % (options.weburl, task_id))
    if build_opts.wait or (build_opts.wait is None and not _running_in_bg()):
        session.logout()
        return watch_tasks(session, [task_id], quiet=options.quiet,
                           poll_interval=options.poll_interval, topurl=options.topurl)


def handle_maven_chain(options, session, args):
    "[build] Run a set of Maven builds in dependency order"
    usage = "usage: %prog maven-chain [options] <target> <config> [<config> ...]"
    parser = OptionParser(usage=get_usage_str(usage))
    parser.add_option("--skip-tag", action="store_true", help="Do not attempt to tag builds")
    parser.add_option("--scratch", action="store_true", help="Perform scratch builds")
    parser.add_option("--debug", action="store_true", help="Run Maven build in debug mode")
    parser.add_option("--force", action="store_true", help="Force rebuilds of all packages")
    parser.add_option("--wait", action="store_true",
                      help="Wait on build, even if running in the background")
    parser.add_option("--nowait", action="store_false", dest="wait", help="Don't wait on build")
    parser.add_option("--background", action="store_true",
                      help="Run the build at a lower priority")
    (build_opts, args) = parser.parse_args(args)
    if len(args) < 2:
        parser.error("Two arguments (a build target and a config file) are required")
    activate_session(session, options)
    target = args[0]
    build_target = session.getBuildTarget(target)
    if not build_target:
        parser.error("No such build target: %s" % target)
    dest_tag = session.getTag(build_target['dest_tag'])
    if not dest_tag:
        parser.error("No such destination tag: %s" % build_target['dest_tag_name'])
    if dest_tag['locked'] and not build_opts.scratch:
        parser.error("Destination tag %s is locked" % dest_tag['name'])
    opts = {}
    for key in ('skip_tag', 'scratch', 'debug', 'force'):
        val = getattr(build_opts, key)
        if val:
            opts[key] = val
    try:
        builds = koji.util.parse_maven_chain(args[1:], scratch=opts.get('scratch'))
    except ValueError as e:
        parser.error(e.args[0])
    priority = None
    if build_opts.background:
        priority = 5
    task_id = session.chainMaven(builds, target, opts, priority=priority)
    print("Created task: %d" % task_id)
    print("Task info: %s/taskinfo?taskID=%s" % (options.weburl, task_id))
    if build_opts.wait or (build_opts.wait is None and not _running_in_bg()):
        session.logout()
        return watch_tasks(session, [task_id], quiet=options.quiet,
                           poll_interval=options.poll_interval, topurl=options.topurl)


def handle_resubmit(goptions, session, args):
    """[build] Retry a canceled or failed task, using the same parameter as the original task."""
    usage = "usage: %prog resubmit [options] <task_id>"
    parser = OptionParser(usage=get_usage_str(usage))
    parser.add_option("--wait", action="store_true",
                      help="Wait on task, even if running in the background")
    parser.add_option("--nowait", action="store_false", dest="wait", help="Don't wait on task")
    parser.add_option("--nowatch", action="store_true", dest="nowait",
                      help="An alias for --nowait")
    parser.add_option("--quiet", action="store_true", default=goptions.quiet,
                      help="Do not print the task information")
    (options, args) = parser.parse_args(args)
    if len(args) != 1:
        parser.error("Please specify a single task ID")
    activate_session(session, goptions)
    taskID = int(args[0])
    if not options.quiet:
        print("Resubmitting the following task:")
        _printTaskInfo(session, taskID, goptions.topdir, 0, False, True)
    newID = session.resubmitTask(taskID)
    if not options.quiet:
        print("Resubmitted task %s as new task %s" % (taskID, newID))
    if options.wait or (options.wait is None and not _running_in_bg()):
        session.logout()
        return watch_tasks(session, [newID], quiet=options.quiet,
                           poll_interval=goptions.poll_interval, topurl=goptions.topurl)


def handle_call(goptions, session, args):
    "Execute an arbitrary XML-RPC call"
    usage = """\
        usage: %prog call [options] <name> [<arg> ...]

        <arg> values of the form NAME=VALUE are treated as keyword arguments
        Note, that you can use global option --noauth for anonymous calls here"""
    usage = textwrap.dedent(usage)
    parser = OptionParser(usage=get_usage_str(usage))
    parser.add_option("-p", "--python", action="store_true",
                      help="Use python syntax for RPC parameter values")
    parser.add_option("--kwargs",
                      help="Specify keyword arguments as a dictionary (implies --python or "
                           "--json-input)")
    parser.add_option("-j", "--json", action="store_true",
                      help="Use JSON syntax for input and output")
    parser.add_option("--json-input", action="store_true", help="Use JSON syntax for input")
    parser.add_option("--json-output", action="store_true", help="Use JSON syntax for output")
    parser.add_option("-b", "--bare-strings", action="store_true",
                      help="Treat invalid json/python as bare strings")
    (options, args) = parser.parse_args(args)
    if len(args) < 1:
        parser.error("Please specify the name of the XML-RPC method")
    if options.json:
        options.json_input = True
        options.json_output = True
    if options.python and options.json_input:
        parser.error('The --python option conflicts with using --json-input')
    if options.kwargs and not options.json_input:
        # for backwards compatibility, --python is implied
        options.python = True
    if options.python and ast is None:
        parser.error("The ast module is required to read python syntax")
    if (options.json_output or options.json_input) and json is None:
        parser.error("The json module is required to use JSON syntax")

    def parse_arg(arg):
        try:
            if options.python:
                return ast.literal_eval(arg)
            elif options.json_input:
                return json.loads(arg)
            else:
                return arg_filter(arg)
        except ValueError:
            if options.bare_strings:
                return arg
            else:
                parser.error("Invalid value: %r" % arg)

    # the method to call
    name = args[0]

    # base kw args
    # we update with name=value args later
    kw = {}
    if options.kwargs:
        kw = parse_arg(options.kwargs)

    kw_pat = re.compile(r'^([^\W0-9]\w*)=(.*)$')

    # read the args
    non_kw = []
    for arg in args[1:]:
        m = kw_pat.match(arg)
        if m:
            key, value = m.groups()
            kw[key] = parse_arg(value)
        else:
            non_kw.append(parse_arg(arg))

    # make the call
    activate_session(session, goptions)
    response = getattr(session, name).__call__(*non_kw, **kw)

    # print the result
    if options.json_output:
        print(json.dumps(response, indent=2, separators=(',', ': '), cls=DatetimeJSONEncoder))
    else:
        pprint.pprint(response)


def anon_handle_mock_config(goptions, session, args):
    "[info] Create a mock config"
    usage = "usage: %prog mock-config [options]"
    parser = OptionParser(usage=get_usage_str(usage))
    parser.add_option("-a", "--arch", help="Specify the arch")
    parser.add_option("-n", "--name", help="Specify the name for the buildroot")
    parser.add_option("--tag", help="Create a mock config for a tag")
    parser.add_option("--target", help="Create a mock config for a build target")
    parser.add_option("--task", help="Duplicate the mock config of a previous task")
    parser.add_option("--latest", action="store_true", help="use the latest redirect url")
    parser.add_option("--buildroot",
                      help="Duplicate the mock config for the specified buildroot id")
    parser.add_option("--mockdir", default="/var/lib/mock", metavar="DIR", help="Specify mockdir")
    parser.add_option("--topdir", metavar="DIR",
                      help="Specify topdir, topdir tops the topurl")
    parser.add_option("--topurl", metavar="URL",
                      help="URL under which Koji files are accessible, "
                           "when topdir is specified, topdir tops the topurl")
    parser.add_option("--distribution", default="Koji Testing",
                      help="Change the distribution macro")
    parser.add_option("--yum-proxy", help="Specify a yum proxy")
    parser.add_option("-o", metavar="FILE", dest="ofile", help="Output to a file")
    (options, args) = parser.parse_args(args)
    ensure_connection(session, goptions)
    if args:
        # for historical reasons, we also accept buildroot name as first arg
        if not options.name:
            options.name = args[0]
        else:
            parser.error("Name already specified via option")
    arch = None
    opts = {}
    for k in ('topdir', 'topurl', 'distribution', 'mockdir', 'yum_proxy'):
        if hasattr(options, k):
            if getattr(options, k) is not None:
                opts[k] = getattr(options, k)
    if opts.get('topdir') and opts.get('topurl'):
        del opts['topurl']
    if not opts.get('topdir') and not opts.get('topurl'):
        opts['topurl'] = goptions.topurl
    if options.buildroot:
        try:
            br_id = int(options.buildroot)
        except ValueError:
            parser.error("Buildroot id must be an integer")
        brootinfo = session.getBuildroot(br_id)
        if brootinfo is None:
            error("No such buildroot: %r" % br_id)
        if options.latest:
            opts['repoid'] = 'latest'
        else:
            opts['repoid'] = brootinfo['repo_id']
        opts['tag_name'] = brootinfo['tag_name']
        arch = brootinfo['arch']
    elif options.task:
        try:
            task_id = int(options.task)
        except ValueError:
            parser.error("Task id must be an integer")
        broots = session.listBuildroots(taskID=task_id)
        if not broots:
            error("No buildroots for task %s (or no such task)" % options.task)
        if len(broots) > 1:
            print("Multiple buildroots found: %s" % [br['id'] for br in broots])
        brootinfo = broots[-1]
        if options.latest:
            opts['repoid'] = 'latest'
        else:
            opts['repoid'] = brootinfo['repo_id']
        opts['tag_name'] = brootinfo['tag_name']
        arch = brootinfo['arch']
        if not options.name:
            options.name = "%s-task_%i" % (opts['tag_name'], task_id)
    elif options.tag:
        if not options.arch:
            error("Please specify an arch")
        tag = session.getTag(options.tag)
        if not tag:
            parser.error("No such tag: %s" % options.tag)
        arch = options.arch
        config = session.getBuildConfig(tag['id'])
        if not config:
            error("Could not get config info for tag: %(name)s" % tag)
        opts['tag_name'] = tag['name']
        if options.latest:
            opts['repoid'] = 'latest'
        else:
            repo = session.getRepo(config['id'])
            if not repo:
                error("Could not get a repo for tag: %(name)s" % tag)
            opts['repoid'] = repo['id']
    elif options.target:
        if not options.arch:
            error("Please specify an arch")
        arch = options.arch
        target = session.getBuildTarget(options.target)
        if not target:
            parser.error("No such build target: %s" % options.target)
        opts['tag_name'] = target['build_tag_name']
        if options.latest:
            opts['repoid'] = 'latest'
        else:
            repo = session.getRepo(target['build_tag'])
            if not repo:
                error("Could not get a repo for tag: %s" % opts['tag_name'])
            opts['repoid'] = repo['id']
    else:
        parser.error("Please specify one of: --tag, --target, --task, --buildroot")
    if options.name:
        name = options.name
    else:
        name = "%(tag_name)s-repo_%(repoid)s" % opts

    event = None
    if opts['repoid'] != 'latest':
        event = session.repoInfo(opts['repoid'])['create_event']
    buildcfg = session.getBuildConfig(opts['tag_name'], event=event)
    if arch:
        if not buildcfg['arches']:
            warn("Tag %s has an empty arch list" % opts['tag_name'])
        elif arch not in buildcfg['arches']:
            warn('%s is not in the list of tag arches' % arch)
        if 'mock.forcearch' in buildcfg['extra']:
            if bool(buildcfg['extra']['mock.forcearch']):
                opts['forcearch'] = arch
    if 'mock.package_manager' in buildcfg['extra']:
        opts['package_manager'] = buildcfg['extra']['mock.package_manager']
    if 'mock.yum.module_hotfixes' in buildcfg['extra']:
        opts['module_hotfixes'] = buildcfg['extra']['mock.yum.module_hotfixes']
    if 'mock.yum.best' in buildcfg['extra']:
        opts['yum_best'] = int(buildcfg['extra']['mock.yum.best'])
    if 'mock.bootstrap_image' in buildcfg['extra']:
        opts['use_bootstrap_image'] = True
        opts['bootstrap_image'] = buildcfg['extra']['mock.bootstrap_image']
    else:
        opts['use_bootstrap_image'] = False
    if 'mock.use_bootstrap' in buildcfg['extra']:
        opts['use_bootstrap'] = buildcfg['extra']['mock.use_bootstrap']
    if 'mock.module_setup_commands' in buildcfg['extra']:
        opts['module_setup_commands'] = buildcfg['extra']['mock.module_setup_commands']
    if 'mock.releasever' in buildcfg['extra']:
        opts['releasever'] = buildcfg['extra']['mock.releasever']
    opts['tag_macros'] = {}
    for key in buildcfg['extra']:
        if key.startswith('rpm.macro.'):
            macro = '%' + key[10:]
            opts['tag_macros'][macro] = buildcfg['extra'][key]
    output = koji.genMockConfig(name, arch, **opts)
    if options.ofile:
        with open(options.ofile, 'wt') as fo:
            fo.write(output)
    else:
        print(output)


def handle_disable_host(goptions, session, args):
    "[admin] Mark one or more hosts as disabled"
    usage = "usage: %prog disable-host [options] <hostname> [<hostname> ...]"
    parser = OptionParser(usage=get_usage_str(usage))
    parser.add_option("--comment", help="Comment indicating why the host(s) are being disabled")
    (options, args) = parser.parse_args(args)

    if not args:
        parser.error("At least one host must be specified")

    activate_session(session, goptions)
    session.multicall = True
    for host in args:
        session.getHost(host)
    error_hit = False
    for host, [id] in zip(args, session.multiCall(strict=True)):
        if not id:
            print("No such host: %s" % host)
            error_hit = True
    if error_hit:
        error("No changes made. Please correct the command line.")
    session.multicall = True
    for host in args:
        session.disableHost(host)
        if options.comment is not None:
            session.editHost(host, comment=options.comment)
    session.multiCall(strict=True)


def handle_enable_host(goptions, session, args):
    "[admin] Mark one or more hosts as enabled"
    usage = "usage: %prog enable-host [options] <hostname> [<hostname> ...]"
    parser = OptionParser(usage=get_usage_str(usage))
    parser.add_option("--comment", help="Comment indicating why the host(s) are being enabled")
    (options, args) = parser.parse_args(args)

    if not args:
        parser.error("At least one host must be specified")

    activate_session(session, goptions)
    session.multicall = True
    for host in args:
        session.getHost(host)
    error_hit = False
    for host, [id] in zip(args, session.multiCall(strict=True)):
        if not id:
            print("No such host: %s" % host)
            error_hit = True
    if error_hit:
        error("No changes made. Please correct the command line.")
    session.multicall = True
    for host in args:
        session.enableHost(host)
        if options.comment is not None:
            session.editHost(host, comment=options.comment)
    session.multiCall(strict=True)


def handle_restart_hosts(options, session, args):
    "[admin] Restart enabled hosts"
    usage = "usage: %prog restart-hosts [options]"
    parser = OptionParser(usage=get_usage_str(usage))
    parser.add_option("--wait", action="store_true",
                      help="Wait on the task, even if running in the background")
    parser.add_option("--nowait", action="store_false", dest="wait", help="Don't wait on task")
    parser.add_option("--quiet", action="store_true",
                      help="Do not print the task information", default=options.quiet)
    parser.add_option("--force", action="store_true", help="Ignore checks and force operation")
    parser.add_option("--channel", help="Only hosts in this channel")
    parser.add_option("--arch", "-a", action="append", default=[],
                      help="Limit to hosts of this architecture (can be given multiple times)")
    parser.add_option("--timeout", metavar='N', type='int', help="Time out after N seconds")
    (my_opts, args) = parser.parse_args(args)

    if len(args) > 0:
        parser.error("restart-hosts does not accept arguments")

    activate_session(session, options)

    # check for existing restart tasks
    if not my_opts.force:
        query = {
            'method': 'restartHosts',
            'state':
                [koji.TASK_STATES[s] for s in ('FREE', 'OPEN', 'ASSIGNED')],
        }
        others = session.listTasks(query)
        if others:
            warn('Found other restartHosts tasks running.')
            warn('Task ids: %r' % [t['id'] for t in others])
            error('Use --force to run anyway')

    callopts = {}
    if my_opts.channel:
        callopts['channel'] = my_opts.channel
    if my_opts.arch:
        callopts['arches'] = my_opts.arch
    if my_opts.timeout:
        callopts['timeout'] = my_opts.timeout
    if callopts:
        task_id = session.restartHosts(options=callopts)
    else:
        # allow default case to work with older hub
        task_id = session.restartHosts()
    if my_opts.wait or (my_opts.wait is None and not _running_in_bg()):
        session.logout()
        return watch_tasks(session, [task_id], quiet=my_opts.quiet,
                           poll_interval=options.poll_interval, topurl=options.topurl)


def handle_import(goptions, session, args):
    "[admin] Import externally built RPMs into the database"
    usage = "usage: %prog import [options] <package> [<package> ...]"
    parser = OptionParser(usage=get_usage_str(usage))
    parser.add_option("--link", action="store_true",
                      help="Attempt to hardlink instead of uploading")
    parser.add_option("--test", action="store_true", help="Don't actually import")
    parser.add_option("--create-build", action="store_true", help="Auto-create builds as needed")
    parser.add_option("--src-epoch", help="When auto-creating builds, use this epoch")
    (options, args) = parser.parse_args(args)
    if len(args) < 1:
        parser.error("At least one package must be specified")
    if options.src_epoch in ('None', 'none', '(none)'):
        options.src_epoch = None
    elif options.src_epoch:
        try:
            options.src_epoch = int(options.src_epoch)
        except (ValueError, TypeError):
            parser.error("Invalid value for epoch: %s" % options.src_epoch)
    activate_session(session, goptions)
    to_import = {}
    for path in args:
        data = koji.get_header_fields(path, ('name', 'version', 'release', 'epoch',
                                             'arch', 'sigmd5', 'sourcepackage', 'sourcerpm'))
        if data['sourcepackage']:
            data['arch'] = 'src'
            nvr = "%(name)s-%(version)s-%(release)s" % data
        else:
            nvr = "%(name)s-%(version)s-%(release)s" % koji.parse_NVRA(data['sourcerpm'])
        to_import.setdefault(nvr, []).append((path, data))
    builds_missing = False
    nvrs = sorted(to_list(to_import.keys()))
    for nvr in nvrs:
        to_import[nvr].sort()
        for path, data in to_import[nvr]:
            if data['sourcepackage']:
                break
        else:
            # no srpm included, check for build
            binfo = session.getBuild(nvr)
            if not binfo:
                print("Missing build or srpm: %s" % nvr)
                builds_missing = True
    if builds_missing and not options.create_build:
        print("Aborting import")
        return

    # local function to help us out below
    def do_import(path, data):
        rinfo = dict([(k, data[k]) for k in ('name', 'version', 'release', 'arch')])
        prev = session.getRPM(rinfo)
        if prev and not prev.get('external_repo_id', 0):
            if prev['payloadhash'] == koji.hex_string(data['sigmd5']):
                print("RPM already imported: %s" % path)
            else:
                warn("md5sum mismatch for %s" % path)
                warn("  A different rpm with the same name has already been imported")
                warn("  Existing sigmd5 is %r, your import has %r" % (
                    prev['payloadhash'], koji.hex_string(data['sigmd5'])))
            print("Skipping import")
            return
        if options.test:
            print("Test mode -- skipping import for %s" % path)
            return
        serverdir = unique_path('cli-import')
        if options.link:
            linked_upload(path, serverdir)
        else:
            sys.stdout.write("uploading %s... " % path)
            sys.stdout.flush()
            session.uploadWrapper(path, serverdir)
            print("done")
            sys.stdout.flush()
        sys.stdout.write("importing %s... " % path)
        sys.stdout.flush()
        try:
            session.importRPM(serverdir, os.path.basename(path))
        except koji.GenericError as e:
            print("\nError importing: %s" % str(e).splitlines()[-1])
            sys.stdout.flush()
        else:
            print("done")
        sys.stdout.flush()

    for nvr in nvrs:
        # check for existing build
        need_build = True
        binfo = session.getBuild(nvr)
        if binfo:
            b_state = koji.BUILD_STATES[binfo['state']]
            if b_state == 'COMPLETE':
                need_build = False
            elif b_state in ['FAILED', 'CANCELED']:
                if not options.create_build:
                    print("Build %s state is %s. Skipping import" % (nvr, b_state))
                    continue
            else:
                print("Build %s exists with state=%s. Skipping import" % (nvr, b_state))
                continue

        # import srpms first, if any
        for path, data in to_import[nvr]:
            if data['sourcepackage']:
                if binfo and b_state != 'COMPLETE':
                    # need to fix the state
                    print("Creating empty build: %s" % nvr)
                    b_data = koji.util.dslice(binfo, ['name', 'version', 'release'])
                    b_data['epoch'] = data['epoch']
                    session.createEmptyBuild(**b_data)
                    binfo = session.getBuild(nvr)
                do_import(path, data)
                need_build = False

        if need_build:
            # if we're doing this here, we weren't given the matching srpm
            if not options.create_build:  # pragma: no cover
                if binfo:
                    # should have caught this earlier, but just in case...
                    b_state = koji.BUILD_STATES[binfo['state']]
                    print("Build %s state is %s. Skipping import" % (nvr, b_state))
                    continue
                else:
                    print("No such build: %s (include matching srpm or use "
                          "--create-build option to add it)" % nvr)
                    continue
            else:
                # let's make a new build
                b_data = koji.parse_NVR(nvr)
                if options.src_epoch:
                    b_data['epoch'] = options.src_epoch
                else:
                    # pull epoch from first rpm
                    data = to_import[nvr][0][1]
                    b_data['epoch'] = data['epoch']
                if options.test:
                    print("Test mode -- would have created empty build: %s" % nvr)
                else:
                    print("Creating empty build: %s" % nvr)
                    session.createEmptyBuild(**b_data)
                    binfo = session.getBuild(nvr)

        for path, data in to_import[nvr]:
            if data['sourcepackage']:
                continue
            do_import(path, data)


def handle_import_cg(goptions, session, args):
    "[admin] Import external builds with rich metadata"
    usage = "usage: %prog import-cg [options] <metadata_file> <files_dir>"
    parser = OptionParser(usage=get_usage_str(usage))
    parser.add_option("--noprogress", action="store_true",
                      help="Do not display progress of the upload")
    parser.add_option("--link", action="store_true",
                      help="Attempt to hardlink instead of uploading")
    parser.add_option("--test", action="store_true", help="Don't actually import")
    parser.add_option("--token", action="store", default=None, help="Build reservation token")
    (options, args) = parser.parse_args(args)
    if len(args) < 2:
        parser.error("Please specify metadata files directory")
    activate_session(session, goptions)
    metadata = koji.load_json(args[0])
    if 'output' not in metadata:
        error("Metadata contains no output")
    localdir = args[1]

    to_upload = []
    for info in metadata['output']:
        if info.get('metadata_only', False):
            continue
        localpath = os.path.join(localdir, info.get('relpath', ''), info['filename'])
        if not os.path.exists(localpath):
            parser.error("No such file: %s" % localpath)
        to_upload.append([localpath, info])

    if options.test:
        return

    # get upload path
    # XXX - need a better way
    serverdir = unique_path('cli-import')

    for localpath, info in to_upload:
        relpath = os.path.join(serverdir, info.get('relpath', ''))
        if _running_in_bg() or options.noprogress:
            callback = None
        else:
            callback = _progress_callback
        if options.link:
            linked_upload(localpath, relpath)
        else:
            print("Uploading %s" % localpath)
            session.uploadWrapper(localpath, relpath, callback=callback)
            if callback:
                print('')

    session.CGImport(metadata, serverdir, options.token)


def handle_import_comps(goptions, session, args):
    "Import group/package information from a comps file"
    usage = "usage: %prog import-comps [options] <file> <tag>"
    parser = OptionParser(usage=get_usage_str(usage))
    parser.add_option("--force", action="store_true", help="force import")
    (local_options, args) = parser.parse_args(args)
    if len(args) != 2:
        parser.error("Incorrect number of arguments")
    activate_session(session, goptions)
    # check if the tag exists
    dsttag = session.getTag(args[1])
    if dsttag is None:
        error("No such tag: %s" % args[1])
    if libcomps is not None:
        _import_comps(session, args[0], args[1], local_options)
    elif yumcomps is not None:
        _import_comps_alt(session, args[0], args[1], local_options)
    else:
        error("comps module not available")


def _import_comps(session, filename, tag, options):
    """Import comps data using libcomps module"""
    comps = libcomps.Comps()
    comps.fromxml_f(filename)
    force = options.force
    ptypes = {
        libcomps.PACKAGE_TYPE_DEFAULT: 'default',
        libcomps.PACKAGE_TYPE_OPTIONAL: 'optional',
        libcomps.PACKAGE_TYPE_CONDITIONAL: 'conditional',
        libcomps.PACKAGE_TYPE_MANDATORY: 'mandatory',
        libcomps.PACKAGE_TYPE_UNKNOWN: 'unknown',
    }
    for group in comps.groups:
        print("Group: %s (%s)" % (group.id, group.name))
        session.groupListAdd(
            tag, group.id, force=force, display_name=group.name,
            is_default=bool(group.default),
            uservisible=bool(group.uservisible),
            description=group.desc,
            langonly=group.lang_only,
            biarchonly=bool(group.biarchonly))
        for pkg in group.packages:
            pkgopts = {'type': ptypes[pkg.type],
                       'basearchonly': bool(pkg.basearchonly),
                       }
            if pkg.type == libcomps.PACKAGE_TYPE_CONDITIONAL:
                pkgopts['requires'] = pkg.requires
            for k in pkgopts.keys():
                if six.PY2 and isinstance(pkgopts[k], unicode):  # noqa: F821
                    pkgopts[k] = str(pkgopts[k])
            s_opts = ', '.join(["'%s': %r" % (k, pkgopts[k]) for k in sorted(pkgopts.keys())])
            print("  Package: %s: {%s}" % (pkg.name, s_opts))
            session.groupPackageListAdd(tag, group.id, pkg.name, force=force, **pkgopts)
        # libcomps does not support group dependencies
        # libcomps does not support metapkgs


def _import_comps_alt(session, filename, tag, options):  # no cover 3.x
    """Import comps data using yum.comps module"""
    print('WARN: yum.comps does not support the biarchonly of group and basearchonly of package')
    comps = yumcomps.Comps()
    comps.add(filename)
    force = options.force
    for group in comps.groups:
        print("Group: %(groupid)s (%(name)s)" % vars(group))
        session.groupListAdd(tag, group.groupid, force=force, display_name=group.name,
                             is_default=bool(group.default),
                             uservisible=bool(group.user_visible),
                             description=group.description,
                             langonly=group.langonly)
        # yum.comps does not support the biarchonly field
        for ptype, pdata in [('mandatory', group.mandatory_packages),
                             ('default', group.default_packages),
                             ('optional', group.optional_packages),
                             ('conditional', group.conditional_packages)]:
            for pkg in pdata:
                # yum.comps does not support basearchonly
                pkgopts = {'type': ptype}
                if ptype == 'conditional':
                    pkgopts['requires'] = pdata[pkg]
                for k in pkgopts.keys():
                    if six.PY2 and isinstance(pkgopts[k], unicode):  # noqa: F821
                        pkgopts[k] = str(pkgopts[k])
                s_opts = ', '.join(["'%s': %r" % (k, pkgopts[k]) for k in sorted(pkgopts.keys())])
                print("  Package: %s: {%s}" % (pkg, s_opts))
                session.groupPackageListAdd(tag, group.groupid, pkg, force=force, **pkgopts)
        # yum.comps does not support group dependencies
        # yum.comps does not support metapkgs


def handle_import_sig(goptions, session, args):
    "[admin] Import signatures into the database and write signed RPMs"
    usage = "usage: %prog import-sig [options] <package> [<package> ...]"
    parser = OptionParser(usage=get_usage_str(usage))
    parser.add_option("--with-unsigned", action="store_true",
                      help="Also import unsigned sig headers")
    parser.add_option("--write", action="store_true", help=SUPPRESS_HELP)
    parser.add_option("--test", action="store_true", help="Test mode -- don't actually import")
    (options, args) = parser.parse_args(args)
    if len(args) < 1:
        parser.error("At least one package must be specified")
    for path in args:
        if not os.path.exists(path):
            parser.error("No such file: %s" % path)
    activate_session(session, goptions)
    for path in args:
        data = koji.get_header_fields(path, ('name', 'version', 'release', 'arch', 'siggpg',
                                             'sigpgp', 'dsaheader', 'rsaheader',
                                             'sourcepackage'))
        if data['sourcepackage']:
            data['arch'] = 'src'
        sigkey = data['siggpg']
        if not sigkey:
            sigkey = data['sigpgp']
        if not sigkey:
            sigkey = data['dsaheader']
        if not sigkey:
            sigkey = data['rsaheader']
        if not sigkey:
            sigkey = ""
            if not options.with_unsigned:
                print("Skipping unsigned package: %s" % path)
                continue
        else:
            sigkey = koji.get_sigpacket_key_id(sigkey)
        del data['siggpg']
        del data['sigpgp']
        del data['dsaheader']
        del data['rsaheader']
        rinfo = session.getRPM(data)
        if not rinfo:
            print("No such rpm in system: %(name)s-%(version)s-%(release)s.%(arch)s" % data)
            continue
        if rinfo.get('external_repo_id'):
            print("Skipping external rpm: %(name)s-%(version)s-%(release)s.%(arch)s@"
                  "%(external_repo_name)s" % rinfo)
            continue
        sighdr = koji.rip_rpm_sighdr(path)
        previous = session.queryRPMSigs(rpm_id=rinfo['id'], sigkey=sigkey)
        assert len(previous) <= 1
        if previous:
            sighash = md5_constructor(sighdr).hexdigest()
            if previous[0]['sighash'] == sighash:
                print("Signature already imported: %s" % path)
                continue
            else:
                warn("signature mismatch: %s" % path)
                warn("  The system already has a signature for this rpm with key %s" % sigkey)
                warn("  The two signature headers are not the same")
                continue
        print("Importing signature [key %s] from %s..." % (sigkey, path))
        if not options.test:
            session.addRPMSig(rinfo['id'], base64encode(sighdr))
        print("Writing signed copy")
        if not options.test:
            session.writeSignedRPM(rinfo['id'], sigkey)


def handle_remove_sig(goptions, session, args):
    "[admin] Remove signed RPMs from db and disk"
    usage = "usage: %prog remove-sig [options] <rpm-id/n-v-r.a/rpminfo>"
    description = "Only use this method in extreme situations, because it "
    description += "goes against Koji's design of immutable, auditable data."
    parser = OptionParser(usage=get_usage_str(usage), description=description)
    parser.add_option("--sigkey", action="store", default=None, help="Specify signature key")
    parser.add_option("--all", action="store_true", default=False,
                      help="Remove all signed copies for specified RPM")
    (options, args) = parser.parse_args(args)
    if len(args) < 1:
        parser.error("Please specify an RPM")

    if not options.all and not options.sigkey:
        error("Either --sigkey or --all options must be given")

    if options.all and options.sigkey:
        error("Conflicting options specified")

    activate_session(session, goptions)
    rpminfo = args[0]

    try:
        session.deleteRPMSig(rpminfo, sigkey=options.sigkey, all_sigs=options.all)
    except koji.GenericError as e:
        msg = str(e)
        if msg.startswith("No such rpm"):
            # make this a little more readable than the hub error
            error("No such rpm in system: %s" % rpminfo)
        else:
            error("Signature removal failed: %s" % msg)


def handle_write_signed_rpm(goptions, session, args):
    "[admin] Write signed RPMs to disk"
    usage = "usage: %prog write-signed-rpm [options] <signature-key> <n-v-r> [<n-v-r> ...]"
    parser = OptionParser(usage=get_usage_str(usage))
    parser.add_option("--all", action="store_true", help="Write out all RPMs signed with this key")
    parser.add_option("--buildid", help="Specify a build id rather than an n-v-r")
    (options, args) = parser.parse_args(args)
    if len(args) < 1:
        parser.error("A signature key must be specified")
    if len(args) < 2 and not (options.all or options.buildid):
        parser.error("At least one RPM must be specified")
    key = args.pop(0).lower()
    activate_session(session, goptions)
    if options.all:
        rpms = session.queryRPMSigs(sigkey=key)
        with session.multicall() as m:
            results = [m.getRPM(r['rpm_id']) for r in rpms]
        rpms = [x.result for x in results]
    elif options.buildid:
        rpms = session.listRPMs(int(options.buildid))
    else:
        nvrs = []
        rpms = []

        with session.multicall() as m:
            result = [m.getRPM(nvra, strict=False) for nvra in args]
        for rpm, nvra in zip(result, args):
            rpm = rpm.result
            if rpm:
                rpms.append(rpm)
            else:
                nvrs.append(nvra)

        # for historical reasons, we also accept nvrs
        with session.multicall() as m:
            result = [m.getBuild(nvr, strict=True) for nvr in nvrs]
        builds = []
        for nvr, build in zip(nvrs, result):
            try:
                builds.append(build.result['id'])
            except koji.GenericError:
                raise koji.GenericError("No such rpm or build: %s" % nvr)

        with session.multicall() as m:
            rpm_lists = [m.listRPMs(buildID=build_id) for build_id in builds]
        for rpm_list in rpm_lists:
            rpms.extend(rpm_list.result)

    with session.multicall(strict=True) as m:
        for i, rpminfo in enumerate(rpms):
            nvra = "%(name)s-%(version)s-%(release)s.%(arch)s" % rpminfo
            print("[%d/%d] %s" % (i + 1, len(rpms), nvra))
            m.writeSignedRPM(rpminfo['id'], key)


def handle_prune_signed_copies(goptions, session, args):
    "[admin] Prune signed copies"
    usage = "usage: %prog prune-signed-copies [options]"
    parser = OptionParser(usage=get_usage_str(usage))
    parser.add_option("-n", "--test", action="store_true", help="Test mode")
    parser.add_option("-v", "--verbose", action="store_true", help="Be more verbose")
    parser.add_option("--days", type="int", default=5, help="Timeout before clearing")
    parser.add_option("-p", "--package", "--pkg", help="Limit to a single package")
    parser.add_option("-b", "--build", help="Limit to a single build")
    parser.add_option("-i", "--ignore-tag", action="append", default=[],
                      help="Ignore these tags when considering whether a build is/was latest")
    parser.add_option("--ignore-tag-file",
                      help="File to read tag ignore patterns from")
    parser.add_option("-r", "--protect-tag", action="append", default=[],
                      help="Do not prune signed copies from matching tags")
    parser.add_option("--protect-tag-file",
                      help="File to read tag protect patterns from")
    parser.add_option("--trashcan-tag", default="trashcan", help="Specify trashcan tag")
    # Don't use local debug option, this one stays here for backward compatibility
    # https://pagure.io/koji/issue/2084
    parser.add_option("--debug", action="store_true", default=goptions.debug, help=SUPPRESS_HELP)
    (options, args) = parser.parse_args(args)
    # different ideas/modes
    #  1) remove all signed copies of builds that are not latest for some tag
    #  2) remove signed copies when a 'better' signature is available
    #  3) for a specified tag, remove all signed copies that are not latest (w/ inheritance)
    #  4) for a specified tag, remove all signed copies (no inheritance)
    #     (but skip builds that are multiply tagged)

    # for now, we're just implementing mode #1
    # (with the modification that we check to see if the build was latest within
    # the last N days)
    if options.ignore_tag_file:
        with open(options.ignore_tag_file) as fo:
            options.ignore_tag.extend([line.strip() for line in fo.readlines()])
    if options.protect_tag_file:
        with open(options.protect_tag_file) as fo:
            options.protect_tag.extend([line.strip() for line in fo.readlines()])
    if options.debug:
        options.verbose = True
    cutoff_ts = time.time() - options.days * 24 * 3600
    if options.debug:
        print("Cutoff date: %s" % time.asctime(time.localtime(cutoff_ts)))
    activate_session(session, goptions)
    if not options.build:
        if options.verbose:
            print("Getting builds...")
        qopts = {
            'state': koji.BUILD_STATES['COMPLETE'],
            'queryOpts': {
                'limit': 50000,
                'offset': 0,
                'order': 'build_id',
            }
        }
        if options.package:
            pkginfo = session.getPackage(options.package)
            qopts['packageID'] = pkginfo['id']
        builds = []
        while True:
            chunk = [(b['nvr'], b) for b in session.listBuilds(**qopts)]
            if not chunk:
                break
            builds.extend(chunk)
            qopts['queryOpts']['offset'] += qopts['queryOpts']['limit']
        if options.verbose:
            print("...got %i builds" % len(builds))
        builds.sort()
    else:
        # single build
        binfo = session.getBuild(options.build)
        if not binfo:
            parser.error('No such build: %s' % options.build)
        builds = [("%(name)s-%(version)s-%(release)s" % binfo, binfo)]
    total_files = 0
    total_space = 0

    def _histline(event_id, x):
        if event_id == x['revoke_event']:
            ts = x['revoke_ts']
            fmt = "Untagged %(name)s-%(version)s-%(release)s from %(tag_name)s"
        elif event_id == x['create_event']:
            ts = x['create_ts']
            fmt = "Tagged %(name)s-%(version)s-%(release)s with %(tag_name)s"
            if x['active']:
                fmt += " [still active]"
        else:
            raise koji.GenericError("No such event: (%r, %r)" % (event_id, x))
        time_str = time.asctime(time.localtime(ts))
        return "%s: %s" % (time_str, fmt % x)
    for nvr, binfo in builds:
        # listBuilds returns slightly different data than normal
        if 'id' not in binfo:
            binfo['id'] = binfo['build_id']
        if 'name' not in binfo:
            binfo['name'] = binfo['package_name']
        if options.debug:
            print("DEBUG: %s" % nvr)
        # see how recently this build was latest for a tag
        is_latest = False
        is_protected = False
        last_latest = None
        tags = {}
        for entry in session.queryHistory(build=binfo['id'])['tag_listing']:
            # we used queryHistory rather than listTags so we can consider tags
            # that the build was recently untagged from
            tags.setdefault(entry['tag.name'], 1)
        if options.debug:
            print("Tags: %s" % to_list(tags.keys()))
        for tag_name in tags:
            if tag_name == options.trashcan_tag:
                if options.debug:
                    print("Ignoring trashcan tag for build %s" % nvr)
                continue
            ignore_tag = False
            for pattern in options.ignore_tag:
                if fnmatch.fnmatch(tag_name, pattern):
                    if options.debug:
                        print("Ignoring tag %s for build %s" % (tag_name, nvr))
                    ignore_tag = True
                    break
            if ignore_tag:
                continue
            # in order to determine how recently this build was latest, we have
            # to look at the tagging history.
            hist = session.queryHistory(tag=tag_name, package=binfo['name'])['tag_listing']
            if not hist:
                # really shouldn't happen
                raise koji.GenericError("No history found for %s in %s" % (nvr, tag_name))
            timeline = []
            for x in hist:
                # note that for revoked entries, we're effectively splitting them into
                # two parts: creation and revocation.
                timeline.append((x['create_event'], 1, x))
                # at the same event, revokes happen first
                if x['revoke_event'] is not None:
                    timeline.append((x['revoke_event'], 0, x))
            timeline.sort(key=lambda entry: entry[:2])
            # find most recent creation entry for our build and crop there
            latest_ts = None
            for i in range(len(timeline) - 1, -1, -1):
                # searching in reverse cronological order
                event_id, is_create, entry = timeline[i]
                if entry['build_id'] == binfo['id'] and is_create:
                    latest_ts = event_id
                    break
            if not latest_ts:
                # really shouldn't happen
                raise koji.GenericError("No creation event found for %s in %s" % (nvr, tag_name))
            our_entry = entry
            if options.debug:
                print(_histline(event_id, our_entry))
            # now go through the events since most recent creation entry
            timeline = timeline[i + 1:]
            if not timeline:
                is_latest = True
                if options.debug:
                    print("%s is latest in tag %s" % (nvr, tag_name))
                break
            # before we go any further, is this a protected tag?
            protect_tag = False
            for pattern in options.protect_tag:
                if fnmatch.fnmatch(tag_name, pattern):
                    protect_tag = True
                    break
            if protect_tag:
                # we use the same time limit as for the latest calculation
                # if this build was in this tag within that limit, then we will
                # not prune its signed copies
                if our_entry['revoke_event'] is None:
                    # we're still tagged with a protected tag
                    if options.debug:
                        print("Build %s has protected tag %s" % (nvr, tag_name))
                    is_protected = True
                    break
                elif our_entry['revoke_ts'] > cutoff_ts:
                    # we were still tagged here sometime before the cutoff
                    if options.debug:
                        print("Build %s had protected tag %s until %s"
                              % (nvr, tag_name,
                                 time.asctime(time.localtime(our_entry['revoke_ts']))))
                    is_protected = True
                    break
            replaced_ts = None
            revoke_ts = None
            others = {}
            for event_id, is_create, entry in timeline:
                # So two things can knock this build from the title of latest:
                #  - it could be untagged (entry revoked)
                #  - another build could become latest (replaced)
                # Note however that if the superceding entry is itself revoked, then
                # our build could become latest again
                if options.debug:
                    print(_histline(event_id, entry))
                if entry['build_id'] == binfo['id']:
                    if is_create:
                        # shouldn't happen
                        raise koji.GenericError("Duplicate creation event found for %s in %s"
                                                % (nvr, tag_name))
                    else:
                        # we've been revoked
                        revoke_ts = entry['revoke_ts']
                        break
                else:
                    if is_create:
                        # this build has become latest
                        replaced_ts = entry['create_ts']
                        if entry['active']:
                            # this entry not revoked yet, so we're done for this tag
                            break
                        # since this entry is revoked later, our build might eventually be
                        # uncovered, so we have to keep looking
                        others[entry['build_id']] = 1
                    else:
                        # other build revoked
                        # see if our build has resurfaced
                        if entry['build_id'] in others:
                            del others[entry['build_id']]
                        if replaced_ts is not None and not others:
                            # we've become latest again
                            # (note: we're not revoked yet because that triggers a break above)
                            replaced_ts = None
                            latest_ts = entry['revoke_ts']
            if last_latest is None:
                timestamps = []
            else:
                timestamps = [last_latest]
            if revoke_ts is None:
                if replaced_ts is None:
                    # turns out we are still latest
                    is_latest = True
                    if options.debug:
                        print("%s is latest (again) in tag %s" % (nvr, tag_name))
                    break
                else:
                    # replaced (but not revoked)
                    timestamps.append(replaced_ts)
                    if options.debug:
                        print("tag %s: %s not latest (replaced %s)"
                              % (tag_name, nvr, time.asctime(time.localtime(replaced_ts))))
            elif replaced_ts is None:
                # revoked but not replaced
                timestamps.append(revoke_ts)
                if options.debug:
                    print("tag %s: %s not latest (revoked %s)"
                          % (tag_name, nvr, time.asctime(time.localtime(revoke_ts))))
            else:
                # revoked AND replaced
                timestamps.append(min(revoke_ts, replaced_ts))
                if options.debug:
                    print("tag %s: %s not latest (revoked %s, replaced %s)"
                          % (tag_name, nvr, time.asctime(time.localtime(revoke_ts)),
                             time.asctime(time.localtime(replaced_ts))))
            last_latest = max(timestamps)
            if last_latest > cutoff_ts:
                if options.debug:
                    print("%s was latest past the cutoff" % nvr)
                is_latest = True
                break
        if is_latest:
            continue
        if is_protected:
            continue
        # not latest anywhere since cutoff, so we can remove all signed copies
        rpms = session.listRPMs(buildID=binfo['id'])
        session.multicall = True
        for rpminfo in rpms:
            session.queryRPMSigs(rpm_id=rpminfo['id'])
        by_sig = {}
        # index by sig
        for rpminfo, [sigs] in zip(rpms, session.multiCall()):
            for sig in sigs:
                sigkey = sig['sigkey']
                by_sig.setdefault(sigkey, []).append(rpminfo)
        builddir = koji.pathinfo.build(binfo)
        build_files = 0
        build_space = 0
        if not by_sig and options.debug:
            print("(build has no signatures)")
        for sigkey, rpms in six.iteritems(by_sig):
            mycount = 0
            archdirs = {}
            sigdirs = {}
            for rpminfo in rpms:
                signedpath = "%s/%s" % (builddir, koji.pathinfo.signed(rpminfo, sigkey))
                try:
                    st = os.lstat(signedpath)
                except OSError:
                    continue
                if not stat.S_ISREG(st.st_mode):
                    # warn about this
                    print("Skipping %s. Not a regular file" % signedpath)
                    continue
                if st.st_mtime > cutoff_ts:
                    print("Skipping %s. File newer than cutoff" % signedpath)
                    continue
                if options.test:
                    print("Would have unlinked: %s" % signedpath)
                else:
                    if options.verbose:
                        print("Unlinking: %s" % signedpath)
                    try:
                        os.unlink(signedpath)
                    except OSError as e:
                        print("Error removing %s: %s" % (signedpath, e))
                        print("This script needs write access to %s" % koji.BASEDIR)
                        continue
                mycount += 1
                build_files += 1
                build_space += st.st_size
                # XXX - this makes some layout assumptions, but
                #      pathinfo doesn't report what we need
                mydir = os.path.dirname(signedpath)
                archdirs[mydir] = 1
                sigdirs[os.path.dirname(mydir)] = 1
            for dir in archdirs:
                if options.test:
                    print("Would have removed dir: %s" % dir)
                else:
                    if options.verbose:
                        print("Removing dir: %s" % dir)
                    try:
                        os.rmdir(dir)
                    except OSError as e:
                        print("Error removing %s: %s" % (signedpath, e))
            if len(sigdirs) == 1:
                dir = to_list(sigdirs.keys())[0]
                if options.test:
                    print("Would have removed dir: %s" % dir)
                else:
                    if options.verbose:
                        print("Removing dir: %s" % dir)
                    try:
                        os.rmdir(dir)
                    except OSError as e:
                        print("Error removing %s: %s" % (signedpath, e))
            elif len(sigdirs) > 1:
                warn("More than one signature dir for %s: %r" % (sigkey, sigdirs))
        if build_files:
            total_files += build_files
            total_space += build_space
            if options.verbose:
                print("Build: %s, Removed %i signed copies (%i bytes). Total: %i/%i"
                      % (nvr, build_files, build_space, total_files, total_space))
        elif options.debug and by_sig:
            print("(build has no signed copies)")
    print("--- Grand Totals ---")
    print("Files: %i" % total_files)
    print("Bytes: %i" % total_space)


def handle_set_build_volume(goptions, session, args):
    "[admin] Move a build to a different volume"
    usage = "usage: %prog set-build-volume <volume> <n-v-r> [<n-v-r> ...]"
    parser = OptionParser(usage=get_usage_str(usage))
    parser.add_option("-v", "--verbose", action="store_true", help="Be verbose")
    (options, args) = parser.parse_args(args)
    if len(args) < 2:
        parser.error("You must provide a volume and at least one build")
    volinfo = session.getVolume(args[0])
    if not volinfo:
        error("No such volume: %s" % args[0])
    activate_session(session, goptions)
    builds = []
    for nvr in args[1:]:
        binfo = session.getBuild(nvr)
        if not binfo:
            print("No such build: %s" % nvr)
        elif binfo['volume_id'] == volinfo['id']:
            print("Build %s already on volume %s" % (nvr, volinfo['name']))
        else:
            builds.append(binfo)
    if not builds:
        error("No builds to move")
    for binfo in builds:
        session.changeBuildVolume(binfo['id'], volinfo['id'])
        if options.verbose:
            print("%s: %s -> %s" % (binfo['nvr'], binfo['volume_name'], volinfo['name']))


def handle_add_volume(goptions, session, args):
    "[admin] Add a new storage volume"
    usage = "usage: %prog add-volume <volume-name>"
    parser = OptionParser(usage=get_usage_str(usage))
    (options, args) = parser.parse_args(args)
    if len(args) != 1:
        parser.error("Command requires exactly one volume-name.")
    name = args[0]
    volinfo = session.getVolume(name)
    if volinfo:
        error("Volume %s already exists" % name)
    activate_session(session, goptions)
    volinfo = session.addVolume(name)
    print("Added volume %(name)s with id %(id)i" % volinfo)


def anon_handle_list_volumes(goptions, session, args):
    "[info] List storage volumes"
    usage = "usage: %prog list-volumes"
    parser = OptionParser(usage=get_usage_str(usage))
    (options, args) = parser.parse_args(args)
    ensure_connection(session, goptions)
    for volinfo in session.listVolumes():
        print(volinfo['name'])


def handle_list_permissions(goptions, session, args):
    "[info] List user permissions"
    usage = "usage: %prog list-permissions [options]"
    parser = OptionParser(usage=get_usage_str(usage))
    parser.add_option("--user", help="List permissions for the given user")
    parser.add_option("--mine", action="store_true", help="List your permissions")
    parser.add_option("--quiet", action="store_true", default=goptions.quiet,
                      help="Do not print the header information")
    (options, args) = parser.parse_args(args)
    if len(args) > 0:
        parser.error("This command takes no arguments")
    activate_session(session, goptions)
    perms = []
    if options.mine:
        options.user = session.getLoggedInUser()['id']
    if options.user:
        user = session.getUser(options.user)
        if not user:
            error("No such user: %s" % options.user)
        try:
            for p, groups in session.getUserPermsInheritance(user['id']).items():
                p = {'name': p}
                if groups != [None]:
                    p['description'] = 'inherited from: %s' % ', '.join(groups)
                perms.append(p)
        except koji.GenericError as e:
            # backwards compatible
            # TODO: can be removed in 1.36
            if "Invalid method" in str(e):
                warn("Old hub doesn't support Inherited Group Permissions.")
                for p in session.getUserPerms(user['id']):
                    perms.append({'name': p})
            else:
                raise
    else:
        for p in session.getAllPerms():
            perms.append({'name': p['name'], 'description': p['description']})
    if perms:
        longest_perm = max([len(perm['name']) for perm in perms])
        perms = sorted(perms, key=lambda x: x['name'])
    else:
        longest_perm = 8
    if longest_perm < len('Permission name   '):
        longest_perm = len('Permission name   ')
    if not options.quiet:
        hdr = '{permname:<{longest_perm}}'
        hdr = hdr.format(longest_perm=longest_perm, permname='Permission name')
        if perms and perms[0].get('description'):
            hdr += "   Description".ljust(53)
        print(hdr)
        print(len(hdr) * '-')
    for perm in perms:
        line = '{permname:<{longest_perm}}'
        line = line.format(longest_perm=longest_perm, permname=perm['name'])
        if perm.get('description'):
            line += "   %s" % perm['description']
        print(line)


def handle_add_user(goptions, session, args):
    "[admin] Add a user"
    usage = "usage: %prog add-user <username> [options]"
    parser = OptionParser(usage=get_usage_str(usage))
    parser.add_option("--principal", help="The Kerberos principal for this user")
    parser.add_option("--disable", help="Prohibit logins by this user", action="store_true")
    (options, args) = parser.parse_args(args)
    if len(args) < 1:
        parser.error("You must specify the username of the user to add")
    elif len(args) > 1:
        parser.error("This command only accepts one argument (username)")
    username = args[0]
    if options.disable:
        status = koji.USER_STATUS['BLOCKED']
    else:
        status = koji.USER_STATUS['NORMAL']
    activate_session(session, goptions)
    user_id = session.createUser(username, status=status, krb_principal=options.principal)
    print("Added user %s (%i)" % (username, user_id))


def handle_enable_user(goptions, session, args):
    "[admin] Enable logins by a user"
    usage = "usage: %prog enable-user <username>"
    parser = OptionParser(usage=get_usage_str(usage))
    (options, args) = parser.parse_args(args)
    if len(args) < 1:
        parser.error("You must specify the username of the user to enable")
    elif len(args) > 1:
        parser.error("This command only accepts one argument (username)")
    username = args[0]
    activate_session(session, goptions)
    session.enableUser(username)


def handle_disable_user(goptions, session, args):
    "[admin] Disable logins by a user"
    usage = "usage: %prog disable-user <username>"
    parser = OptionParser(usage=get_usage_str(usage))
    (options, args) = parser.parse_args(args)
    if len(args) < 1:
        parser.error("You must specify the username of the user to disable")
    elif len(args) > 1:
        parser.error("This command only accepts one argument (username)")
    username = args[0]
    activate_session(session, goptions)
    session.disableUser(username)


def handle_edit_user(goptions, session, args):
    "[admin] Alter user information"
    usage = "usage: %prog edit-user <username> [options]"
    parser = OptionParser(usage=get_usage_str(usage))
    parser.add_option("--rename", help="Rename the user")
    parser.add_option("--edit-krb", action="append", default=[], metavar="OLD=NEW",
                      help="Change kerberos principal of the user")
    parser.add_option("--add-krb", action="append", default=[], metavar="KRB",
                      help="Add kerberos principal of the user")
    parser.add_option("--remove-krb", action="append", default=[], metavar="KRB",
                      help="Remove kerberos principal of the user")
    (options, args) = parser.parse_args(args)
    if len(args) < 1:
        parser.error("You must specify the username of the user to edit")
    elif len(args) > 1:
        parser.error("This command only accepts one argument (username)")
    activate_session(session, goptions)
    user = args[0]
    princ_mappings = []
    for p in options.edit_krb:
        old, new = p.split('=', 1)
        princ_mappings.append({'old': arg_filter(old), 'new': arg_filter(new)})
    for a in options.add_krb:
        princ_mappings.append({'old': None, 'new': arg_filter(a)})
    for r in options.remove_krb:
        princ_mappings.append({'old': arg_filter(r), 'new': None})
    session.editUser(user, options.rename, princ_mappings)


def handle_list_signed(goptions, session, args):
    "[admin] List signed copies of rpms"
    usage = "usage: %prog list-signed [options]"
    description = "You must have local access to Koji's topdir filesystem."
    parser = OptionParser(usage=get_usage_str(usage), description=description)
    # Don't use local debug option, this one stays here for backward compatibility
    # https://pagure.io/koji/issue/2084
    parser.add_option("--debug", action="store_true", default=goptions.debug, help=SUPPRESS_HELP)
    parser.add_option("--key", help="Only list RPMs signed with this key")
    parser.add_option("--build", help="Only list RPMs from this build")
    parser.add_option("--rpm", help="Only list signed copies for this RPM")
    parser.add_option("--tag", help="Only list RPMs within this tag")
    (options, args) = parser.parse_args(args)
    if not options.build and not options.tag and not options.rpm:
        parser.error("At least one from --build, --rpm, --tag needs to be specified.")
    activate_session(session, goptions)
    qopts = {}
    build_idx = {}
    rpm_idx = {}
    if options.key:
        qopts['sigkey'] = options.key

    sigs = []
    if options.rpm:
        rpm_info = options.rpm
        try:
            rpm_info = int(rpm_info)
        except ValueError:
            pass
        rinfo = session.getRPM(rpm_info, strict=True)
        rpm_idx[rinfo['id']] = rinfo
        if rinfo.get('external_repo_id'):
            parser.error("External rpm: %(name)s-%(version)s-%(release)s.%(arch)s@"
                         "%(external_repo_name)s" % rinfo)
        sigs += session.queryRPMSigs(rpm_id=rinfo['id'], **qopts)
    if options.build:
        build = options.build
        try:
            build = int(build)
        except ValueError:
            pass
        binfo = session.getBuild(build, strict=True)
        build_idx[binfo['id']] = binfo
        rpms = session.listRPMs(buildID=binfo['id'])
        for rinfo in rpms:
            rpm_idx[rinfo['id']] = rinfo
            sigs += session.queryRPMSigs(rpm_id=rinfo['id'], **qopts)
    if options.tag:
        tag = options.tag
        try:
            tag = int(tag)
        except ValueError:
            pass
        rpms, builds = session.listTaggedRPMS(tag, inherit=False, latest=False)
        tagged = {}
        for binfo in builds:
            build_idx.setdefault(binfo['id'], binfo)
        results = []
        # use batched multicall as there could be potentially a lot of results
        # so we don't exhaust server resources
        with session.multicall(batch=5000) as m:
            for rinfo in rpms:
                rpm_idx.setdefault(rinfo['id'], rinfo)
                tagged[rinfo['id']] = 1
                results.append(m.queryRPMSigs(rpm_id=rinfo['id']), **qopts)
        sigs += [x.result[0] for x in results]

    # Now figure out which sig entries actually have live copies
    for sig in sigs:
        rpm_id = sig['rpm_id']
        sigkey = sig['sigkey']
        if options.tag:
            if tagged.get(rpm_id) is None:
                continue
        rinfo = rpm_idx.get(rpm_id)
        if not rinfo:
            rinfo = session.getRPM(rpm_id)
            rpm_idx[rinfo['id']] = rinfo
        binfo = build_idx.get(rinfo['build_id'])
        if not binfo:
            binfo = session.getBuild(rinfo['build_id'])
            build_idx[binfo['id']] = binfo
        binfo['name'] = binfo['package_name']
        builddir = koji.pathinfo.build(binfo)
        signedpath = "%s/%s" % (builddir, koji.pathinfo.signed(rinfo, sigkey))
        if not os.path.exists(signedpath):
            if goptions.debug:
                print("No copy: %s" % signedpath)
            continue
        print(signedpath)


def handle_import_archive(options, session, args):
    "[admin] Import an archive file and associate it with a build"
    usage = "usage: %prog import-archive <build-id|n-v-r> <archive_path> [<archive_path2 ...]"
    parser = OptionParser(usage=get_usage_str(usage))
    parser.add_option("--noprogress", action="store_true",
                      help="Do not display progress of the upload")
    parser.add_option("--create-build", action="store_true", help="Auto-create builds as needed")
    parser.add_option("--link", action="store_true",
                      help="Attempt to hardlink instead of uploading")
    parser.add_option("--type",
                      help="The type of archive being imported. "
                           "Currently supported types: maven, win, image")
    parser.add_option("--type-info",
                      help="Type-specific information to associate with the archives. "
                           "For Maven archives this should be a local path to a .pom file. "
                           "For Windows archives this should be relpath:platforms[:flags])) "
                           "Images need an arch")
    (suboptions, args) = parser.parse_args(args)

    if not len(args) > 1:
        parser.error("You must specify a build ID or N-V-R and an archive to import")

    activate_session(session, options)

    if not suboptions.type:
        parser.error("You must specify an archive type")
    if suboptions.type == 'maven':
        if not (session.hasPerm('maven-import') or session.hasPerm('admin')):
            parser.error("This action requires the maven-import privilege")
        if not suboptions.type_info:
            parser.error("--type-info must point to a .pom file when importing Maven archives")
        pom_info = koji.parse_pom(suboptions.type_info)
        maven_info = koji.pom_to_maven_info(pom_info)
        suboptions.type_info = maven_info
    elif suboptions.type == 'win':
        if not (session.hasPerm('win-import') or session.hasPerm('admin')):
            parser.error("This action requires the win-import privilege")
        if not suboptions.type_info:
            parser.error("--type-info must be specified")
        type_info = suboptions.type_info.split(':', 2)
        if len(type_info) < 2:
            parser.error("--type-info must be in relpath:platforms[:flags] format")
        win_info = {'relpath': type_info[0], 'platforms': type_info[1].split()}
        if len(type_info) > 2:
            win_info['flags'] = type_info[2].split()
        else:
            win_info['flags'] = []
        suboptions.type_info = win_info
    elif suboptions.type == 'image':
        if not (session.hasPerm('image-import') or session.hasPerm('admin')):
            parser.error("This action requires the image-import privilege")
        if not suboptions.type_info:
            parser.error("--type-info must be specified")
        image_info = {'arch': suboptions.type_info}
        suboptions.type_info = image_info
    else:
        parser.error("Unsupported archive type: %s" % suboptions.type)

    buildinfo = session.getBuild(arg_filter(args[0]))
    if not buildinfo:
        if not suboptions.create_build:
            parser.error("No such build: %s" % args[0])
        buildinfo = koji.parse_NVR(args[0])
        if buildinfo['epoch'] == '':
            buildinfo['epoch'] = None
        else:
            buildinfo['epoch'] = int(buildinfo['epoch'])
        if suboptions.type == 'maven':
            # --type-info should point to a local .pom file
            session.createMavenBuild(buildinfo, suboptions.type_info)
        elif suboptions.type == 'win':
            # We're importing, so we don't know what platform the build
            # was run on.  Use "import" as a placeholder.
            session.createWinBuild(buildinfo, {'platform': 'import'})
        elif suboptions.type == 'image':
            # --type-info should have an arch of the image
            session.createImageBuild(buildinfo)
        else:
            # should get caught above
            assert False  # pragma: no cover

    for filepath in args[1:]:
        filename = os.path.basename(filepath)
        print("Uploading archive: %s" % filename)
        serverdir = unique_path('cli-import')
        if _running_in_bg() or suboptions.noprogress:
            callback = None
        else:
            callback = _progress_callback
        if suboptions.link:
            linked_upload(filepath, serverdir)
        else:
            session.uploadWrapper(filepath, serverdir, callback=callback)
        print('')
        serverpath = "%s/%s" % (serverdir, filename)
        session.importArchive(serverpath, buildinfo, suboptions.type, suboptions.type_info)
        print("Imported: %s" % filename)


def handle_grant_permission(goptions, session, args):
    "[admin] Grant a permission to a user"
    usage = "usage: %prog grant-permission [options] <permission> <user> [<user> ...]"
    parser = OptionParser(usage=get_usage_str(usage))
    parser.add_option("--new", action="store_true",
                      help="Create this permission if the permission does not exist")
    parser.add_option("--description",
                      help="Add description about new permission")
    (options, args) = parser.parse_args(args)
    if len(args) < 2:
        parser.error("Please specify a permission and at least one user")
    activate_session(session, goptions)
    perm = args[0]
    names = args[1:]
    users = []
    for n in names:
        user = session.getUser(n)
        if user is None:
            parser.error("No such user: %s" % n)
        users.append(user)
    kwargs = {}
    if options.new:
        kwargs['create'] = True
        if options.description:
            kwargs['description'] = options.description
    if options.description and not options.new:
        parser.error("Option new must be specified with option description.")
    for user in users:
        session.grantPermission(user['name'], perm, **kwargs)


def handle_revoke_permission(goptions, session, args):
    "[admin] Revoke a permission from a user"
    usage = "usage: %prog revoke-permission <permission> <user> [<user> ...]"
    parser = OptionParser(usage=get_usage_str(usage))
    (options, args) = parser.parse_args(args)
    if len(args) < 2:
        parser.error("Please specify a permission and at least one user")
    activate_session(session, goptions)
    perm = args[0]
    names = args[1:]
    users = []
    for n in names:
        user = session.getUser(n)
        if user is None:
            parser.error("No such user: %s" % n)
        users.append(user)
    for user in users:
        session.revokePermission(user['name'], perm)


def handle_edit_permission(goptions, session, args):
    "[admin] Edit a permission description"
    usage = "usage: %prog edit-permission <permission> <description>"
    parser = OptionParser(usage=get_usage_str(usage))
    (options, args) = parser.parse_args(args)
    if len(args) < 2:
        parser.error("Please specify a permission and a description")
    activate_session(session, goptions)
    perm = args[0]
    description = args[1]
    session.editPermission(perm, description)


def handle_grant_cg_access(goptions, session, args):
    "[admin] Add a user to a content generator"
    usage = "usage: %prog grant-cg-access <user> <content generator>"
    parser = OptionParser(usage=get_usage_str(usage))
    parser.add_option("--new", action="store_true", help="Create a new content generator")
    (options, args) = parser.parse_args(args)
    if len(args) != 2:
        parser.error("Please specify a user and content generator")
    activate_session(session, goptions)
    user = args[0]
    cg = args[1]
    uinfo = session.getUser(user)
    if uinfo is None:
        parser.error("No such user: %s" % user)
    kwargs = {}
    if options.new:
        kwargs['create'] = True
    session.grantCGAccess(uinfo['name'], cg, **kwargs)


def handle_revoke_cg_access(goptions, session, args):
    "[admin] Remove a user from a content generator"
    usage = "usage: %prog revoke-cg-access <user> <content generator>"
    parser = OptionParser(usage=get_usage_str(usage))
    (options, args) = parser.parse_args(args)
    if len(args) != 2:
        parser.error("Please specify a user and content generator")
    activate_session(session, goptions)
    user = args[0]
    cg = args[1]
    uinfo = session.getUser(user)
    if uinfo is None:
        parser.error("No such user: %s" % user)
    session.revokeCGAccess(uinfo['name'], cg)


def anon_handle_latest_build(goptions, session, args):
    """[info] Print the latest builds for a tag"""
    usage = """\
        usage: %prog latest-build [options] <tag> <package> [<package> ...]

        The first option should be the name of a tag, not the name of a build target.
        If you want to know the latest build in buildroots for a given build target,
        then you should use the name of the build tag for that target. You can find
        this value by running '%prog list-targets --name=<target>'

        More information on tags and build targets can be found in the documentation.
        https://docs.pagure.org/koji/HOWTO/#package-organization"""

    usage = textwrap.dedent(usage)
    parser = OptionParser(usage=get_usage_str(usage))
    parser.add_option("--arch", help="List all of the latest packages for this arch")
    parser.add_option("--all", action="store_true",
                      help="List all of the latest packages for this tag")
    parser.add_option("--quiet", action="store_true", default=goptions.quiet,
                      help="Do not print the header information")
    parser.add_option("--paths", action="store_true", help="Show the file paths")
    parser.add_option("--type",
                      help="Show builds of the given type only. "
                           "Currently supported types: maven, win, image, or any custom "
                           "content generator btypes")
    (options, args) = parser.parse_args(args)
    if len(args) == 0:
        parser.error("A tag name must be specified")
    ensure_connection(session, goptions)
    if options.all:
        if len(args) > 1:
            parser.error("A package name may not be combined with --all")
        # Set None as the package argument
        args.append(None)
    else:
        if len(args) < 2:
            parser.error("A tag name and package name must be specified")
    pathinfo = koji.PathInfo()

    for pkg in args[1:]:
        if options.arch:
            rpms, builds = session.getLatestRPMS(args[0], package=pkg, arch=options.arch)
            builds_hash = dict([(x['build_id'], x) for x in builds])
            data = rpms
            if options.paths:
                for x in data:
                    z = x.copy()
                    x['name'] = builds_hash[x['build_id']]['package_name']
                    x['path'] = os.path.join(pathinfo.build(x), pathinfo.rpm(z))
                fmt = "%(path)s"
            else:
                fmt = "%(name)s-%(version)s-%(release)s.%(arch)s"
        else:
            kwargs = {'package': pkg}
            if options.type:
                kwargs['type'] = options.type
            data = session.getLatestBuilds(args[0], **kwargs)
            if options.paths:
                if options.type == 'maven':
                    for x in data:
                        x['path'] = pathinfo.mavenbuild(x)
                    fmt = "%(path)-40s  %(tag_name)-20s  %(maven_group_id)-20s  " \
                          "%(maven_artifact_id)-20s  %(owner_name)s"
                else:
                    for x in data:
                        x['path'] = pathinfo.build(x)
                    fmt = "%(path)-40s  %(tag_name)-20s  %(owner_name)s"
            else:
                if options.type == 'maven':
                    fmt = "%(nvr)-40s  %(tag_name)-20s  %(maven_group_id)-20s  " \
                          "%(maven_artifact_id)-20s  %(owner_name)s"
                else:
                    fmt = "%(nvr)-40s  %(tag_name)-20s  %(owner_name)s"
            if not options.quiet:
                if options.type == 'maven':
                    print("%-40s  %-20s  %-20s  %-20s  %s" %
                          ("Build", "Tag", "Group Id", "Artifact Id", "Built by"))
                    print("%s  %s  %s  %s  %s" %
                          ("-" * 40, "-" * 20, "-" * 20, "-" * 20, "-" * 16))
                else:
                    print("%-40s  %-20s  %s" % ("Build", "Tag", "Built by"))
                    print("%s  %s  %s" % ("-" * 40, "-" * 20, "-" * 16))
                options.quiet = True

        output = sorted([fmt % x for x in data])
        for line in output:
            print(line)


def anon_handle_list_api(goptions, session, args):
    "[info] Print the list of XML-RPC APIs"
    usage = "usage: %prog list-api [options] [method_name ...]"
    parser = OptionParser(usage=get_usage_str(usage))
    (options, args) = parser.parse_args(args)
    ensure_connection(session, goptions)
    if args:
        for method in args:
            help = session.system.methodHelp(method)
            if not help:
                parser.error("Unknown method: %s" % method)
            print(help)
    else:
        for x in sorted(session._listapi(), key=lambda x: x['name']):
            if 'argdesc' in x:
                args = x['argdesc']
            elif x['args']:
                # older servers may not provide argdesc
                expanded = []
                for arg in x['args']:
                    if isinstance(arg, str):
                        expanded.append(arg)
                    else:
                        expanded.append('%s=%s' % (arg[0], arg[1]))
                args = "(%s)" % ", ".join(expanded)
            else:
                args = "()"
            print('%s%s' % (x['name'], args))
            if x['doc']:
                print("  description: %s" % x['doc'])


def anon_handle_list_tagged(goptions, session, args):
    "[info] List the builds or rpms in a tag"
    usage = "usage: %prog list-tagged [options] <tag> [<package>]"
    parser = OptionParser(usage=get_usage_str(usage))
    parser.add_option("--arch", action="append", default=[], help="List rpms for this arch")
    parser.add_option("--rpms", action="store_true", help="Show rpms instead of builds")
    parser.add_option("--inherit", action="store_true", help="Follow inheritance")
    parser.add_option("--latest", action="store_true", help="Only show the latest builds/rpms")
    parser.add_option("--latest-n", type='int', metavar="N",
                      help="Only show the latest N builds/rpms")
    parser.add_option("--quiet", action="store_true", default=goptions.quiet,
                      help="Do not print the header information")
    parser.add_option("--paths", action="store_true", help="Show the file paths")
    parser.add_option("--sigs", action="store_true", help="Show signatures")
    parser.add_option("--type",
                      help="Show builds of the given type only. "
                           "Currently supported types: maven, win, image")
    parser.add_option("--event", type='int', metavar="EVENT#", help="query at event")
    parser.add_option("--ts", type='int', metavar="TIMESTAMP",
                      help="query at last event before timestamp")
    parser.add_option("--repo", type='int', metavar="REPO#", help="query at event for a repo")
    parser.add_option("--draft-only", action="store_true", help="Only list draft builds/rpms")
    parser.add_option("--no-draft", action="store_true", help="Only list regular builds/rpms")
    (options, args) = parser.parse_args(args)
    if len(args) == 0:
        parser.error("A tag name must be specified")
    elif len(args) > 2:
        parser.error("Only one package name may be specified")
    if options.no_draft and options.draft_only:
        parser.error("--draft-only conflicts with --no-draft")
    ensure_connection(session, goptions)
    pathinfo = koji.PathInfo()
    package = None
    if len(args) > 1:
        package = args[1]
    tag = args[0]
    opts = {}
    for key in ('latest', 'inherit'):
        opts[key] = getattr(options, key)
    if options.latest_n is not None:
        opts['latest'] = options.latest_n
    if package:
        opts['package'] = package
    if options.arch:
        options.rpms = True
        opts['arch'] = options.arch
    if options.sigs:
        opts['rpmsigs'] = True
        options.rpms = True
    if options.type:
        opts['type'] = options.type
    elif options.no_draft:
        opts['draft'] = False
    elif options.draft_only:
        opts['draft'] = True
    event = koji.util.eventFromOpts(session, options)
    event_id = None
    if event:
        opts['event'] = event['id']
        event_id = event['id']
        event['timestr'] = time.asctime(time.localtime(event['ts']))
        if not options.quiet:
            print("Querying at event %(id)i (%(timestr)s)" % event)

    # check if tag exist(s|ed)
    taginfo = session.getTag(tag, event=event_id)
    if not taginfo:
        parser.error("No such tag: %s" % tag)

    if options.sigs and options.paths:
        packages_dir = os.path.join(koji.BASEDIR, 'packages')
        if not os.path.exists(packages_dir):
            error("'list-tagged --sigs --paths' requires accessible %s" % packages_dir)

    if options.rpms:
        rpms, builds = session.listTaggedRPMS(tag, **opts)
        data = rpms
        if options.paths:
            build_idx = {}
            for build in builds:
                build_idx[build['id']] = build
                builddir = pathinfo.build(build)
                if options.sigs and not os.path.isdir(builddir):
                    warn('Build directory not found: %s' % builddir)
                else:
                    build['_dir'] = builddir
            for rinfo in data:
                build = build_idx[rinfo['build_id']]
                builddir = build.get('_dir')
                if builddir:
                    if options.sigs:
                        sigkey = rinfo['sigkey']
                        signedpath = os.path.join(builddir, pathinfo.signed(rinfo, sigkey))
                        if os.path.exists(signedpath):
                            rinfo['path'] = signedpath
                    else:
                        rinfo['path'] = os.path.join(builddir, pathinfo.rpm(rinfo))
            fmt = "%(path)s"
            data = [x for x in data if 'path' in x]
        else:
            fmt = "%(name)s-%(version)s-%(release)s.%(arch)s%(draft_suffix)s"
            for x in data:
                x['draft_suffix'] = (' (,draft_%s)' % x['build_id']) if x.get('draft') else ''
            if options.sigs:
                fmt = "%(sigkey)s " + fmt
    else:
        data = session.listTagged(tag, **opts)
        if options.paths:
            if options.type == 'maven':
                for x in data:
                    x['path'] = pathinfo.mavenbuild(x)
                fmt = "%(path)-40s  %(tag_name)-20s  %(maven_group_id)-20s  " \
                      "%(maven_artifact_id)-20s  %(owner_name)s"
            else:
                for x in data:
                    x['path'] = pathinfo.build(x)
                fmt = "%(path)-40s  %(tag_name)-20s  %(owner_name)s"
        else:
            if options.type == 'maven':
                fmt = "%(nvr)-40s  %(tag_name)-20s  %(maven_group_id)-20s  " \
                      "%(maven_artifact_id)-20s  %(owner_name)s"
            else:
                fmt = "%(nvr)-40s  %(tag_name)-20s  %(owner_name)s"
        if not options.quiet:
            if options.type == 'maven':
                print("%-40s  %-20s  %-20s  %-20s  %s" %
                      ("Build", "Tag", "Group Id", "Artifact Id", "Built by"))
                print("%s  %s  %s  %s  %s" %
                      ("-" * 40, "-" * 20, "-" * 20, "-" * 20, "-" * 16))
            else:
                print("%-40s  %-20s  %s" % ("Build", "Tag", "Built by"))
                print("%s  %s  %s" % ("-" * 40, "-" * 20, "-" * 16))

    output = sorted([fmt % x for x in data])
    for line in output:
        print(line)


def anon_handle_list_buildroot(goptions, session, args):
    "[info] List the rpms used in or built in a buildroot"
    usage = "usage: %prog list-buildroot [options] <buildroot-id>"
    parser = OptionParser(usage=get_usage_str(usage))
    parser.add_option("--built", action="store_true", help="Show the built rpms and archives")
    parser.add_option("--verbose", "-v", action="store_true", help="Show more information")
    (options, args) = parser.parse_args(args)
    if len(args) != 1:
        parser.error("Incorrect number of arguments")
    ensure_connection(session, goptions)
    buildrootID = int(args[0])
    opts = {}
    if options.built:
        opts['buildrootID'] = buildrootID
    else:
        opts['componentBuildrootID'] = buildrootID

    list_rpms = session.listRPMs(**opts)
    if list_rpms:
        if options.built:
            print('Built RPMs:')
        else:
            print('Component RPMs:')

    fmt = "%(nvr)s.%(arch)s"
    order = sorted([(fmt % x, x) for x in list_rpms])
    for nvra, rinfo in order:
        line = nvra
        if options.verbose:
            if rinfo.get('draft'):
                line += " (,draft_%s)" % rinfo['build_id']
            if rinfo.get('is_update'):
                line += " [update]"
        print(line)

    list_archives = session.listArchives(**opts)
    if list_archives:
        if list_rpms:
            # print empty line between list of RPMs and archives
            print('')
        if options.built:
            print('Built Archives:')
        else:
            print('Component Archives:')
    order = sorted([x['filename'] for x in list_archives])
    for filename in order:
        print(filename)


def anon_handle_list_untagged(goptions, session, args):
    "[info] List untagged builds"
    usage = "usage: %prog list-untagged [options] [<package>]"
    parser = OptionParser(usage=get_usage_str(usage))
    parser.add_option("--paths", action="store_true", help="Show the file paths")
    parser.add_option("--show-references", action="store_true", help="Show build references")
    (options, args) = parser.parse_args(args)
    if len(args) > 1:
        parser.error("Only one package name may be specified")
    ensure_connection(session, goptions)
    package = None
    if len(args) > 0:
        package = args[0]
    opts = {}
    if package:
        package_id = session.getPackageID(package)
        if package_id is None:
            error("No such package: %s" % package)
        opts['name'] = package
    pathinfo = koji.PathInfo()

    data = session.untaggedBuilds(**opts)
    if options.show_references:
        print("(Showing build references)")
        references = {}
        with session.multicall(strict=True, batch=10000) as m:
            for build in data:
                references[build['id']] = m.buildReferences(build['id'])

        for build in data:
            refs = references[build['id']].result
            r = []
            if refs.get('rpms'):
                r.append("rpms: %s" % refs['rpms'])
            if refs.get('component_of'):
                r.append("images/archives: %s" % refs['component_of'])
            if refs.get('archives'):
                r.append("archives buildroots: %s" % refs['archives'])
            build['refs'] = ', '.join(r)
    if options.paths:
        for x in data:
            x['path'] = pathinfo.build(x)
        fmt = "%(path)s"
    else:
        fmt = "%(name)s-%(version)s-%(release)s"
    if options.show_references:
        fmt = fmt + " %(refs)s"
    output = sorted([fmt % x for x in data])
    for line in output:
        print(line)


def print_group_list_req_group(group):
    print("  @%(name)s  [%(tag_name)s]" % group)


def print_group_list_req_package(pkg):
    fmt = "  %(package)s: %(basearchonly)s, %(type)s  [%(tag_name)s]"
    if pkg['blocked']:
        fmt += " [BLOCKED]"
    print(fmt % pkg)


def anon_handle_list_groups(goptions, session, args):
    "[info] Print the group listings"
    usage = "usage: %prog list-groups [options] <tag> [<group>]"
    parser = OptionParser(usage=get_usage_str(usage))
    parser.add_option("--event", type='int', metavar="EVENT#", help="query at event")
    parser.add_option("--ts", type='int', metavar="TIMESTAMP",
                      help="query at last event before timestamp")
    parser.add_option("--repo", type='int', metavar="REPO#", help="query at event for a repo")
    parser.add_option("--show-blocked", action="store_true", dest="incl_blocked",
                      help="Show blocked packages and groups")
    (options, args) = parser.parse_args(args)
    if len(args) < 1 or len(args) > 2:
        parser.error("Incorrect number of arguments")
    opts = {}
    if options.incl_blocked:
        opts['incl_blocked'] = True
    ensure_connection(session, goptions)
    event = koji.util.eventFromOpts(session, options)
    if event:
        opts['event'] = event['id']
        event['timestr'] = time.asctime(time.localtime(event['ts']))
        print("Querying at event %(id)i (%(timestr)s)" % event)
    tmp_list = sorted([(x['name'], x) for x in session.getTagGroups(args[0], **opts)])
    groups = [x[1] for x in tmp_list]

    tags_cache = {}

    def get_cached_tag(tag_id):
        if tag_id not in tags_cache:
            tag = session.getTag(tag_id, strict=False)
            if tag is None:
                tags_cache[tag_id] = tag_id
            else:
                tags_cache[tag_id] = tag['name']
        return tags_cache[tag_id]

    for group in groups:
        if len(args) > 1 and group['name'] != args[1]:
            continue
        print("%s  [%s]" % (group['name'], get_cached_tag(group['tag_id'])))
        groups = sorted([(x['name'], x) for x in group['grouplist']])
        for x in [x[1] for x in groups]:
            x['tag_name'] = get_cached_tag(x['tag_id'])
            print_group_list_req_group(x)
        pkgs = sorted([(x['package'], x) for x in group['packagelist']])
        for x in [x[1] for x in pkgs]:
            x['tag_name'] = get_cached_tag(x['tag_id'])
            print_group_list_req_package(x)


def handle_add_group_pkg(goptions, session, args):
    "[admin] Add a package to a group's package listing"
    usage = "usage: %prog add-group-pkg [options] <tag> <group> <pkg> [<pkg> ...]"
    parser = OptionParser(usage=get_usage_str(usage))
    (options, args) = parser.parse_args(args)
    if len(args) < 3:
        parser.error("You must specify a tag name, group name, and one or more package names")
    tag = args[0]
    group = args[1]
    activate_session(session, goptions)
    for pkg in args[2:]:
        session.groupPackageListAdd(tag, group, pkg)


def handle_block_group_pkg(goptions, session, args):
    "[admin] Block a package from a group's package listing"
    usage = "usage: %prog block-group-pkg [options] <tag> <group> <pkg> [<pkg> ...]"
    usage += '\n' + "Note that blocking is propagated through the inheritance chain, so " \
                    "it is not exactly the same as package removal."
    parser = OptionParser(usage=get_usage_str(usage))
    (options, args) = parser.parse_args(args)
    if len(args) < 3:
        parser.error("You must specify a tag name, group name, and one or more package names")
    tag = args[0]
    group = args[1]
    activate_session(session, goptions)
    for pkg in args[2:]:
        session.groupPackageListBlock(tag, group, pkg)


def handle_unblock_group_pkg(goptions, session, args):
    "[admin] Unblock a package from a group's package listing"
    usage = "usage: %prog unblock-group-pkg [options] <tag> <group> <pkg> [<pkg> ...]"
    parser = OptionParser(usage=get_usage_str(usage))
    (options, args) = parser.parse_args(args)
    if len(args) < 3:
        parser.error("You must specify a tag name, group name, and one or more package names")
    tag = args[0]
    group = args[1]
    activate_session(session, goptions)
    for pkg in args[2:]:
        session.groupPackageListUnblock(tag, group, pkg)


def handle_add_group_req(goptions, session, args):
    "[admin] Add a group to a group's required list"
    usage = "usage: %prog add-group-req [options] <tag> <target group> <required group>"
    parser = OptionParser(usage=get_usage_str(usage))
    (options, args) = parser.parse_args(args)
    if len(args) != 3:
        parser.error("You must specify a tag name and two group names")
    tag = args[0]
    group = args[1]
    req = args[2]
    activate_session(session, goptions)
    session.groupReqListAdd(tag, group, req)


def handle_block_group_req(goptions, session, args):
    "[admin] Block a group's requirement listing"
    usage = "usage: %prog block-group-req [options] <tag> <group> <blocked req>"
    parser = OptionParser(usage=get_usage_str(usage))
    (options, args) = parser.parse_args(args)
    if len(args) != 3:
        parser.error("You must specify a tag name and two group names")
    tag = args[0]
    group = args[1]
    req = args[2]
    activate_session(session, goptions)
    session.groupReqListBlock(tag, group, req)


def handle_unblock_group_req(goptions, session, args):
    "[admin] Unblock a group's requirement listing"
    usage = "usage: %prog unblock-group-req [options] <tag> <group> <requirement>"
    parser = OptionParser(usage=get_usage_str(usage))
    (options, args) = parser.parse_args(args)
    if len(args) != 3:
        parser.error("You must specify a tag name and two group names")
    tag = args[0]
    group = args[1]
    req = args[2]
    activate_session(session, goptions)
    session.groupReqListUnblock(tag, group, req)


def anon_handle_list_channels(goptions, session, args):
    "[info] Print channels listing"
    usage = "usage: %prog list-channels [options]"
    parser = OptionParser(usage=get_usage_str(usage))
    parser.add_option("--simple", action="store_true", default=False,
                      help="Print just list of channels without additional info")
    parser.add_option("--quiet", action="store_true", default=goptions.quiet,
                      help="Do not print header information")
    parser.add_option("--comment", action="store_true", help="Show comments")
    parser.add_option("--description", action="store_true", help="Show descriptions")
    parser.add_option("--enabled", action="store_true", help="Limit to enabled channels")
    parser.add_option("--not-enabled", action="store_false", dest="enabled",
                      help="Limit to not enabled channels")
    parser.add_option("--disabled", action="store_false", dest="enabled",
                      help="Alias for --not-enabled")
    parser.add_option("--arch", help="Limit to channels with specific arch")
    (options, args) = parser.parse_args(args)
    ensure_connection(session, goptions)
    opts = {}
    if options.enabled is not None:
        opts['enabled'] = options.enabled
    try:
        channels = sorted([x for x in session.listChannels(**opts)], key=lambda x: x['name'])
    except koji.ParameterError:
        channels = sorted([x for x in session.listChannels()], key=lambda x: x['name'])
    if len(channels) > 0:
        first_item = channels[0]
    else:
        first_item = {}
    session.multicall = True
    for channel in channels:
        if options.arch is not None:
            session.listHosts(channelID=channel['id'], arches=options.arch)
        else:
            session.listHosts(channelID=channel['id'])
    for channel, [hosts] in zip(channels, session.multiCall()):
        channel['enabled_host'] = len([x for x in hosts if x['enabled']])
        channel['disabled'] = len(hosts) - channel['enabled_host']
        channel['ready'] = len([x for x in hosts if x['ready']])
        channel['capacity'] = sum([x['capacity'] for x in hosts])
        channel['load'] = sum([x['task_load'] for x in hosts])
        if 'comment' in first_item:
            channel['comment'] = truncate_string(channel['comment'])
        if 'description' in first_item:
            channel['description'] = truncate_string(channel['description'])
        if channel['capacity']:
            channel['perc_load'] = channel['load'] / channel['capacity'] * 100.0
        else:
            channel['perc_load'] = 0.0
        if 'enabled' in first_item:
            if not channel['enabled']:
                channel['name'] = channel['name'] + ' [disabled]'
    if channels:
        longest_channel = max([len(ch['name']) for ch in channels])
    else:
        longest_channel = 8
    if options.simple:
        if not options.quiet:
            hdr = 'Channel'
            print(hdr)
            print(len(hdr) * '-')
        for channel in channels:
            print(channel['name'])
    else:
        if not options.quiet:
            hdr = '{channame:<{longest_channel}}Enabled  Ready Disbld   Load    Cap   ' \
                  'Perc    '
            hdr = hdr.format(longest_channel=longest_channel, channame='Channel')
            if options.description and 'description' in first_item:
                hdr += "Description".ljust(53)
            if options.comment and 'comment' in first_item:
                hdr += "Comment".ljust(53)
            print(hdr)
            print(len(hdr) * '-')
        mask = "%%(name)-%ss %%(enabled_host)6d %%(ready)6d %%(disabled)6d %%(load)6d %%(" \
               "capacity)6d %%(perc_load)6d%%%%" % longest_channel
        if options.description and 'description' in first_item:
            mask += "   %(description)-50s"
        if options.comment and 'comment' in first_item:
            mask += "   %(comment)-50s"
        for channel in channels:
            print(mask % channel)


def anon_handle_list_hosts(goptions, session, args):
    "[info] Print the host listing"
    usage = "usage: %prog list-hosts [options]"
    parser = OptionParser(usage=get_usage_str(usage))
    parser.add_option("--arch", action="append", default=[], help="Specify an architecture")
    parser.add_option("--channel", help="Specify a channel")
    parser.add_option("--ready", action="store_true", help="Limit to ready hosts")
    parser.add_option("--not-ready", action="store_false", dest="ready",
                      help="Limit to not ready hosts")
    parser.add_option("--enabled", action="store_true", help="Limit to enabled hosts")
    parser.add_option("--not-enabled", action="store_false", dest="enabled",
                      help="Limit to not enabled hosts")
    parser.add_option("--disabled", action="store_false", dest="enabled",
                      help="Alias for --not-enabled")
    parser.add_option("--quiet", action="store_true", default=goptions.quiet,
                      help="Do not print header information")
    parser.add_option("--show-channels", action="store_true", help="Show host's channels")
    parser.add_option("--comment", action="store_true", help="Show comments")
    parser.add_option("--description", action="store_true", help="Show descriptions")
    (options, args) = parser.parse_args(args)
    opts = {}
    ensure_connection(session, goptions)
    if options.arch:
        opts['arches'] = options.arch
    if options.channel:
        channel = session.getChannel(options.channel)
        if not channel:
            parser.error('No such channel: %s' % options.channel)
        opts['channelID'] = channel['id']
    if options.ready is not None:
        opts['ready'] = options.ready
    if options.enabled is not None:
        opts['enabled'] = options.enabled
    hosts = sorted(session.listHosts(**opts), key=lambda x: x['name'])

    if not hosts:
        warn("No hosts found.")
        return

    def yesno(x):
        if x:
            return 'Y'
        else:
            return 'N'

    if 'update_ts' not in hosts[0]:
        _get_host_update_oldhub(session, hosts)

    for host in hosts:
        if host['update_ts'] is None:
            host['update'] = '-'
        else:
            host['update'] = koji.formatTimeLong(host['update_ts'])
        host['enabled'] = yesno(host['enabled'])
        host['ready'] = yesno(host['ready'])
        host['arches'] = ','.join(host['arches'].split())
        host['description'] = truncate_string(host['description'])
        host['comment'] = truncate_string(host['comment'])

    # pull hosts' channels
    if options.show_channels:
        with session.multicall() as m:
            result = [m.listChannels(host['id']) for host in hosts]
        for host, channels in zip(hosts, result):
            list_channels = []
            for c in channels.result:
                # enabled column was added in Koji 1.26
                if c.get('enabled') is not None:
                    if c['enabled']:
                        list_channels.append(c['name'])
                    else:
                        list_channels.append('*' + c['name'])
                else:
                    list_channels.append(c['name'])
            host['channels'] = ','.join(sorted(list_channels))

    longest_host = max([len(h['name']) for h in hosts])

    if not options.quiet:
        hdr = "{hostname:<{longest_host}} Enb Rdy Load/Cap  Arches           " \
              "Last Update                         "
        hdr = hdr.format(longest_host=longest_host, hostname='Hostname')
        if options.description:
            hdr += "Description".ljust(51)
        if options.comment:
            hdr += "Comment".ljust(51)
        if options.show_channels:
            hdr += "Channels"
        print(hdr)
        print(len(hdr) * '-')
    mask = "%%(name)-%ss %%(enabled)-3s %%(ready)-3s %%(task_load)4.1f/%%(capacity)-4.1f " \
           "%%(arches)-16s %%(update)-35s" % longest_host
    if options.description:
        mask += " %(description)-50s"
    if options.comment:
        mask += " %(comment)-50s"
    if options.show_channels:
        mask += " %(channels)s"
    for host in hosts:
        print(mask % host)


def _get_host_update_oldhub(session, hosts):
    """Fetch host update times from older hubs"""

    # figure out if hub supports ts parameter
    try:
        first = session.getLastHostUpdate(hosts[0]['id'], ts=True)
        opts = {'ts': True}
    except koji.ParameterError:
        # Hubs prior to v1.25.0 do not have a "ts" parameter for getLastHostUpdate
        first = session.getLastHostUpdate(hosts[0]['id'])
        opts = {}

    with session.multicall() as m:
        result = [m.getLastHostUpdate(host['id'], **opts) for host in hosts[1:]]

    updateList = [first] + [x.result for x in result]

    for host, update in zip(hosts, updateList):
        if 'ts' in opts:
            host['update_ts'] = update
        elif update is None:
            host['update_ts'] = None
        else:
            dt = dateutil.parser.parse(update)
            host['update_ts'] = time.mktime(dt.timetuple())


def anon_handle_list_pkgs(goptions, session, args):
    "[info] Print the package listing for tag or for owner"
    usage = "usage: %prog list-pkgs [options]"
    parser = OptionParser(usage=get_usage_str(usage))
    parser.add_option("--owner", help="Specify owner")
    parser.add_option("--tag", help="Specify tag")
    parser.add_option("--package", help="Specify package")
    parser.add_option("--quiet", action="store_true", default=goptions.quiet,
                      help="Do not print header information")
    parser.add_option("--noinherit", action="store_true", help="Don't follow inheritance")
    parser.add_option("--show-blocked", action="store_true", help="Show blocked packages")
    parser.add_option("--show-dups", action="store_true", help="Show superseded owners")
    parser.add_option("--event", type='int', metavar="EVENT#", help="query at event")
    parser.add_option("--ts", type='int', metavar="TIMESTAMP",
                      help="query at last event before timestamp")
    parser.add_option("--repo", type='int', metavar="REPO#", help="query at event for a repo")
    (options, args) = parser.parse_args(args)
    if len(args) != 0:
        parser.error("This command takes no arguments")
    ensure_connection(session, goptions)
    opts = {}
    if options.owner:
        user = session.getUser(options.owner)
        if user is None:
            parser.error("No such user: %s" % options.owner)
        opts['userID'] = user['id']
    if options.tag:
        tag = session.getTag(options.tag)
        if tag is None:
            parser.error("No such tag: %s" % options.tag)
        opts['tagID'] = tag['id']
    if options.package:
        opts['pkgID'] = options.package
    allpkgs = False
    if not opts:
        # no limiting clauses were specified
        allpkgs = True
    opts['inherited'] = not options.noinherit
    # hiding dups only makes sense if we're querying a tag
    if options.tag:
        opts['with_dups'] = options.show_dups
    else:
        opts['with_dups'] = True
    event = koji.util.eventFromOpts(session, options)
    if event:
        opts['event'] = event['id']
        event['timestr'] = time.asctime(time.localtime(event['ts']))
        print("Querying at event %(id)i (%(timestr)s)" % event)

    if not opts.get('tagID') and not opts.get('userID') and \
       not opts.get('pkgID'):
        if opts.get('event'):
            parser.error("--event and --ts makes sense only with --tag,"
                         " --owner or --package")
        if options.show_blocked:
            parser.error("--show-blocked makes sense only with --tag,"
                         " --owner or --package")
    if options.show_blocked:
        opts['with_blocked'] = options.show_blocked

    try:
        data = session.listPackages(**opts)
    except koji.ParameterError:
        del opts['with_blocked']
        data = session.listPackages(**opts)

    if not data:
        error("(no matching packages)")
    if not options.quiet:
        if allpkgs:
            print("Package")
            print('-' * 23)
        else:
            print("%-23s %-23s %-16s %-15s" % ('Package', 'Tag', 'Extra Arches', 'Owner'))
            print("%s %s %s %s" % ('-' * 23, '-' * 23, '-' * 16, '-' * 15))
    for pkg in data:
        if allpkgs:
            print(pkg['package_name'])
        else:
            if not options.show_blocked and pkg.get('blocked', False):
                continue
            if 'tag_id' in pkg:
                if pkg['extra_arches'] is None:
                    pkg['extra_arches'] = ""
                fmt = "%(package_name)-23s %(tag_name)-23s %(extra_arches)-16s %(owner_name)-15s"
                if pkg.get('blocked', False):
                    fmt += " [BLOCKED]"
            else:
                fmt = "%(package_name)s"
            print(fmt % pkg)


def anon_handle_list_builds(goptions, session, args):
    "[info] Print the build listing"
    usage = "usage: %prog list-builds [options]"
    parser = OptionParser(usage=get_usage_str(usage), option_class=TimeOption)
    parser.add_option("--package", help="List builds for this package")
    parser.add_option("--buildid", help="List specific build from ID or nvr")
    parser.add_option("--before", type="time",
                      help="List builds built before this time, " + TimeOption.get_help())
    parser.add_option("--after", type="time",
                      help="List builds built after this time (same format as for --before")
    parser.add_option("--state", help="List builds in this state")
    parser.add_option("--task", help="List builds for this task")
    parser.add_option("--type", help="List builds of this type.")
    parser.add_option("--prefix", help="Only builds starting with this prefix")
    parser.add_option("--pattern", help="Only list builds matching this GLOB pattern")
    parser.add_option("--cg", help="Only list builds imported by matching content generator name")
    parser.add_option("--source", help="Only builds where the source field matches (glob pattern)")
    parser.add_option("--owner", help="List builds built by this owner")
    parser.add_option("--volume", help="List builds by volume ID")
    parser.add_option("--draft-only", action="store_true", help="Only list draft builds")
    parser.add_option("--no-draft", action="store_true", help="Only list regular builds")
    parser.add_option("-k", "--sort-key", action="append", metavar='FIELD',
                      default=[], help="Sort the list by the named field. Allowed sort keys: "
                                       "build_id, owner_name, state")
    parser.add_option("-r", "--reverse", action="store_true", default=False,
                      help="Print the list in reverse order")
    parser.add_option("--quiet", action="store_true", default=goptions.quiet,
                      help="Do not print the header information")
    (options, args) = parser.parse_args(args)
    if len(args) != 0:
        parser.error("This command takes no arguments")
    ensure_connection(session, goptions)
    opts = {}
    for key in ('type', 'prefix', 'pattern'):
        value = getattr(options, key)
        if value is not None:
            opts[key] = value
    if options.no_draft and options.draft_only:
        parser.error("--draft-only conflits with --no-draft")
    elif options.no_draft:
        opts['draft'] = False
    elif options.draft_only:
        opts['draft'] = True
    if options.cg:
        opts['cgID'] = options.cg
    if options.package:
        try:
            opts['packageID'] = int(options.package)
        except ValueError:
            package = session.getPackageID(options.package)
            if package is None:
                parser.error("No such package: %s" % options.package)
            opts['packageID'] = package
    if options.owner:
        try:
            opts['userID'] = int(options.owner)
        except ValueError:
            user = session.getUser(options.owner)
            if user is None:
                parser.error("No such user: %s" % options.owner)
            opts['userID'] = user['id']
    if options.volume:
        try:
            opts['volumeID'] = int(options.volume)
        except ValueError:
            volumes = session.listVolumes()
            volumeID = None
            for volume in volumes:
                if options.volume == volume['name']:
                    volumeID = volume['id']
            if volumeID is None:
                parser.error("No such volume: %s" % options.volume)
            opts['volumeID'] = volumeID
    if options.state:
        try:
            state = int(options.state)
            if state > 4 or state < 0:
                parser.error("Invalid state: %s" % options.state)
            opts['state'] = state
        except ValueError:
            try:
                opts['state'] = koji.BUILD_STATES[options.state]
            except KeyError:
                parser.error("Invalid state: %s" % options.state)
    if options.before:
        opts['completeBefore'] = options.before
    if options.after:
        opts['completeAfter'] = options.after
    if options.task:
        try:
            opts['taskID'] = int(options.task)
        except ValueError:
            parser.error("Task id must be an integer")
    if options.source:
        opts['source'] = options.source
    if options.buildid:
        try:
            buildid = int(options.buildid)
        except ValueError:
            buildid = options.buildid
        data = [session.getBuild(buildid)]
        if data[0] is None:
            parser.error("No such build: '%s'" % buildid)
    else:
        # Check filter exists
        if any(opts):
            try:
                data = session.listBuilds(**opts)
            except koji.ParameterError as e:
                if e.args[0].endswith("'pattern'"):
                    parser.error("The hub doesn't support the 'pattern' argument, please try"
                                 " filtering the result on your local instead.")
                if e.args[0].endswith("'cgID'"):
                    parser.error("The hub doesn't support the 'cg' argument, please try"
                                 " filtering the result on your local instead.")
        else:
            parser.error("Filter must be provided for list")
    if not options.sort_key:
        options.sort_key = ['build_id']
    else:
        for s_key in options.sort_key:
            if s_key not in ['build_id', 'owner_name', 'state']:
                warn("Invalid sort_key: %s." % s_key)

    data = sorted(data, key=lambda b: [b.get(k) for k in options.sort_key],
                  reverse=options.reverse)
    for build in data:
        build['state'] = koji.BUILD_STATES[build['state']]

    fmt = "%(nvr)-55s  %(owner_name)-16s  %(state)s"
    if not options.quiet:
        print("%-55s  %-16s  %s" % ("Build", "Built by", "State"))
        print("%s  %s  %s" % ("-" * 55, "-" * 16, "-" * 16))

    for build in data:
        print(fmt % build)


def anon_handle_rpminfo(goptions, session, args):
    "[info] Print basic information about an RPM"
    usage = "usage: %prog rpminfo [options] <n-v-r.a|id> [<n-v-r.a|id> ...]"
    parser = OptionParser(usage=get_usage_str(usage))
    parser.add_option("--buildroots", action="store_true",
                      help="show buildroots the rpm was used in")

    (options, args) = parser.parse_args(args)
    if len(args) < 1:
        parser.error("Please specify an RPM")
    ensure_connection(session, goptions)
    error_hit = False
    for rpm in args:
        info = session.getRPM(rpm)
        if info is None:
            warn("No such rpm: %s\n" % rpm)
            error_hit = True
            continue
        if info['epoch'] is None:
            info['epoch'] = ""
        else:
            info['epoch'] = str(info['epoch']) + ":"
        if not info.get('external_repo_id', 0):
            if info['arch'] == 'src':
                srpminfo = info.copy()
            else:
                srpminfo = None
                srpms = session.listRPMs(buildID=info['build_id'], arches='src')
                if srpms:
                    srpminfo = srpms[0]
                    if srpminfo['epoch'] is None:
                        srpminfo['epoch'] = ""
                    else:
                        srpminfo['epoch'] = str(srpminfo['epoch']) + ":"
            buildinfo = session.getBuild(info['build_id'])
        print("RPM: %(epoch)s%(name)s-%(version)s-%(release)s.%(arch)s [%(id)d]" % info)
        if info.get('draft'):
            print("Draft: YES")
        if info.get('external_repo_id'):
            repo = session.getExternalRepo(info['external_repo_id'])
            print("External Repository: %(name)s [%(id)i]" % repo)
            print("External Repository url: %(url)s" % repo)
        else:
            print("Build: %(nvr)s [%(id)d]" % buildinfo)
            print("RPM Path: %s" %
                  os.path.join(koji.pathinfo.build(buildinfo), koji.pathinfo.rpm(info)))
            if srpminfo:
                srpm_str = "%(epoch)s%(name)s-%(version)s-%(release)s [%(id)d]" % srpminfo
                srpm_path = os.path.join(
                    koji.pathinfo.build(buildinfo),
                    koji.pathinfo.rpm(srpminfo)
                )
            else:
                srpm_path = srpm_str = "(none)"
            print("SRPM: %s" % srpm_str)
            print("SRPM Path: %s" % srpm_path)
            print("Built: %s" % time.strftime('%a, %d %b %Y %H:%M:%S %Z',
                                              time.localtime(info['buildtime'])))
        print("SIGMD5: %(payloadhash)s" % info)
        print("Size: %(size)s" % info)
        if not info.get('external_repo_id', 0):
            headers = session.getRPMHeaders(rpmID=info['id'],
                                            headers=["license"])
            if 'license' in headers:
                print("License: %(license)s" % headers)
            # kept for backward compatibility
            print("Build ID: %(build_id)s" % info)
        if info['buildroot_id'] is None:
            print("No buildroot data available")
        else:
            br_info = session.getBuildroot(info['buildroot_id'])
            if br_info['br_type'] == koji.BR_TYPES['STANDARD']:
                print("Buildroot: %(id)i (tag %(tag_name)s, arch %(arch)s, repo %(repo_id)i)" %
                      br_info)
                print("Build Host: %(host_name)s" % br_info)
                print("Build Task: %(task_id)i" % br_info)
            else:
                print("Content generator: %(cg_name)s" % br_info)
                print("Buildroot: %(id)i" % br_info)
                print("Build Host OS: %(host_os)s (%(host_arch)s)" % br_info)
        if info.get('extra'):
            print("Extra: %(extra)r" % info)
        if options.buildroots:
            br_list = session.listBuildroots(rpmID=info['id'], queryOpts={'order': 'buildroot.id'})
            print("Used in %i buildroots:" % len(br_list))
            if len(br_list):
                print("  %8s %-28s %-8s %-29s" % ('id', 'build tag', 'arch', 'build host'))
                print("  %s %s %s %s" % ('-' * 8, '-' * 28, '-' * 8, '-' * 29))
            for br_info in br_list:
                print("  %(id)8i %(tag_name)-28s %(arch)-8s %(host_name)-29s" % br_info)
    if error_hit:
        error()


def anon_handle_buildinfo(goptions, session, args):
    "[info] Print basic information about a build"
    usage = "usage: %prog buildinfo [options] <n-v-r> [<n-v-r> ...]"
    parser = OptionParser(usage=get_usage_str(usage))
    parser.add_option("--changelog", action="store_true", help="Show the changelog for the build")
    (options, args) = parser.parse_args(args)
    if len(args) < 1:
        parser.error("Please specify a build")
    ensure_connection(session, goptions)
    error_hit = False
    for build in args:
        if build.isdigit():
            build = int(build)
        info = session.getBuild(build)
        if info is None:
            warn("No such build: %s\n" % build)
            error_hit = True
            continue
        task = None
        task_id = extract_build_task(info)
        if task_id:
            task = session.getTaskInfo(task_id, request=True)
        taglist = []
        for tag in session.listTags(build):
            taglist.append(tag['name'])
        info['arch'] = 'src'
        info['state'] = koji.BUILD_STATES[info['state']]
        print("BUILD: %(name)s-%(version)s-%(release)s [%(id)d]" % info)
        if info.get('draft'):
            print("Draft: YES")
        print("State: %(state)s" % info)
        if info['state'] == 'BUILDING':
            print("Reserved by: %(cg_name)s" % info)
        print("Built by: %(owner_name)s" % info)
        source = info.get('source')
        if source is not None:
            print("Source: %s" % source)
        if 'volume_name' in info:
            print("Volume: %(volume_name)s" % info)
        if task:
            print("Task: %s %s" % (task['id'], koji.taskLabel(task)))
        else:
            print("Task: none")
        print("Finished: %s" % koji.formatTimeLong(info['completion_ts']))
        if info.get('promotion_ts'):
            print("Promoted by: %(promoter_name)s" % info)
            print("Promoted at: %s" % koji.formatTimeLong(info['promotion_ts']))
        maven_info = session.getMavenBuild(info['id'])
        if maven_info:
            print("Maven groupId: %s" % maven_info['group_id'])
            print("Maven artifactId: %s" % maven_info['artifact_id'])
            print("Maven version: %s" % maven_info['version'])
        win_info = session.getWinBuild(info['id'])
        if win_info:
            print("Windows build platform: %s" % win_info['platform'])
        print("Tags: %s" % ' '.join(taglist))
        if info.get('extra'):
            print("Extra: %(extra)r" % info)
        archives_seen = {}
        maven_archives = session.listArchives(buildID=info['id'], type='maven')
        if maven_archives:
            print("Maven archives:")
            for archive in maven_archives:
                archives_seen.setdefault(archive['id'], 1)
                print(os.path.join(koji.pathinfo.mavenbuild(info),
                                   koji.pathinfo.mavenfile(archive)))
        win_archives = session.listArchives(buildID=info['id'], type='win')
        if win_archives:
            print("Windows archives:")
            for archive in win_archives:
                archives_seen.setdefault(archive['id'], 1)
                print(os.path.join(koji.pathinfo.winbuild(info), koji.pathinfo.winfile(archive)))
        img_archives = session.listArchives(buildID=info['id'], type='image')
        if img_archives:
            print('Image archives:')
            for archive in img_archives:
                archives_seen.setdefault(archive['id'], 1)
                print(os.path.join(koji.pathinfo.imagebuild(info), archive['filename']))
        archive_idx = {}
        for archive in session.listArchives(buildID=info['id']):
            if archive['id'] in archives_seen:
                continue
            archive_idx.setdefault(archive['btype'], []).append(archive)
        for btype in archive_idx:
            archives = archive_idx[btype]
            print('%s Archives:' % btype.capitalize())
            for archive in archives:
                print(os.path.join(koji.pathinfo.typedir(info, btype), archive['filename']))
        rpms = session.listRPMs(buildID=info['id'])
        if rpms:
            with session.multicall() as mc:
                for rpm in rpms:
                    rpm['sigs'] = mc.queryRPMSigs(rpm['id'])
            print("RPMs:")
            for rpm in rpms:
                line = os.path.join(koji.pathinfo.build(info), koji.pathinfo.rpm(rpm))
                keys = ', '.join(sorted([x['sigkey'] for x in rpm['sigs'].result if x['sigkey']]))
                if keys:
                    line += '\tSignatures: %s' % keys
                print(line)
        if options.changelog:
            changelog = session.getChangelogEntries(info['id'])
            if changelog:
                print("Changelog:")
                print(koji.util.formatChangelog(changelog))
    if error_hit:
        error()


def anon_handle_hostinfo(goptions, session, args):
    "[info] Print basic information about a host"
    usage = "usage: %prog hostinfo [options] <hostname> [<hostname> ...]"
    parser = OptionParser(usage=get_usage_str(usage))
    (options, args) = parser.parse_args(args)
    if len(args) < 1:
        parser.error("Please specify a host")
    ensure_connection(session, goptions)
    error_hit = False
    for host in args:
        if host.isdigit():
            host = int(host)
        info = session.getHost(host)
        if info is None:
            warn("No such host: %s\n" % host)
            error_hit = True
            continue
        print("Name: %(name)s" % info)
        print("ID: %(id)d" % info)
        print("Arches: %(arches)s" % info)
        print("Capacity: %(capacity)s" % info)
        print("Task Load: %(task_load).2f" % info)
        if info['description']:
            description = info['description'].splitlines()
            print("Description: %s" % description[0])
            for line in description[1:]:
                print("%s%s" % (" " * 13, line))
        else:
            print("Description:")
        if info['comment']:
            comment = info['comment'].splitlines()
            print("Comment: %s" % comment[0])
            for line in comment[1:]:
                print("%s%s" % (" " * 9, line))
        else:
            print("Comment:")
        print("Enabled: %s" % (info['enabled'] and 'yes' or 'no'))
        print("Ready: %s" % (info['ready'] and 'yes' or 'no'))

        if 'update_ts' not in info:
            _get_host_update_oldhub(session, [info])
        update = info['update_ts']
        if update is None:
            update = "never"
        else:
            update = koji.formatTimeLong(update)
        print("Last Update: %s" % update)
        print("Channels: %s" % ' '.join([c['name']
                                         for c in session.listChannels(hostID=info['id'])]))
        print("Active Buildroots:")
        states = {0: "INIT", 1: "WAITING", 2: "BUILDING"}
        rows = [('NAME', 'STATE', 'CREATION TIME')]
        for s in range(0, 3):
            for b in session.listBuildroots(hostID=info['id'], state=s):
                rows.append((("%s-%s-%s" % (b['tag_name'], b['id'], b['repo_id'])), states[s],
                             b['create_event_time'][:b['create_event_time'].find('.')]))
        if len(rows) > 1:
            for row in rows:
                print("%-50s %-10s %-20s" % row)
        else:
            print("None")
    if error_hit:
        error()


def handle_clone_tag(goptions, session, args):
    "[admin] Duplicate the contents of one tag onto another tag"
    usage = "usage: %prog clone-tag [options] <src-tag> <dst-tag>"
    usage += "\nclone-tag will create the destination tag if it does not already exist"
    parser = OptionParser(usage=get_usage_str(usage))
    parser.add_option('--config', action='store_true',
                      help="Copy config from the source to the dest tag")
    parser.add_option('--groups', action='store_true',
                      help="Copy group information")
    parser.add_option('--pkgs', action='store_true',
                      help="Copy package list from the source to the dest tag")
    parser.add_option('--builds', action='store_true',
                      help="Tag builds into the dest tag")
    parser.add_option('--all', action='store_true',
                      help="The same as --config --groups --pkgs --builds")
    parser.add_option('--latest-only', action='store_true',
                      help="Tag only the latest build of each package")
    parser.add_option('--inherit-builds', action='store_true',
                      help="Include all builds inherited into the source tag into the dest tag")
    parser.add_option('--ts', type='int', metavar="TIMESTAMP",
                      help='Clone tag at last event before specific timestamp')
    parser.add_option('--no-delete', action='store_false', dest="delete",
                      default=True,
                      help="Don't delete any existing content in dest tag.")
    parser.add_option('--event', type='int',
                      help='Clone tag at a specific event')
    parser.add_option('--repo', type='int',
                      help='Clone tag at a specific repo event')
    parser.add_option("-v", "--verbose", action="store_true",
                      help=SUPPRESS_HELP)
    parser.add_option("--notify", action="store_true", default=False,
                      help='Send tagging/untagging notifications')
    parser.add_option("-f", "--force", action="store_true",
                      help="override tag locks if necessary")
    parser.add_option("-n", "--test", action="store_true", help=SUPPRESS_HELP)
    parser.add_option("--batch", type='int', default=100, metavar='SIZE', help=SUPPRESS_HELP)
    (options, args) = parser.parse_args(args)

    if len(args) != 2:
        parser.error("This command takes two arguments: <src-tag> <dst-tag>")
    activate_session(session, goptions)

    if not options.test and not (session.hasPerm('admin') or session.hasPerm('tag')):
        parser.error("This action requires tag or admin privileges")

    if args[0] == args[1]:
        parser.error('Source and destination tags must be different.')

    if options.batch < 0:
        parser.error("batch size must be bigger than zero")

    if options.all:
        options.config = options.groups = options.pkgs = options.builds = True

    event = koji.util.eventFromOpts(session, options) or {}
    if event:
        event['timestr'] = time.asctime(time.localtime(event['ts']))
        print("Cloning at event %(id)i (%(timestr)s)" % event)

    if options.builds and not options.pkgs:
        parser.error("--builds can't be used without also specifying --pkgs")

    # store tags.
    try:
        srctag = session.getBuildConfig(args[0], event=event.get('id'))
    except koji.GenericError:
        parser.error("No such src-tag: %s" % args[0])
    dsttag = session.getTag(args[1])
    if (srctag['locked'] and not options.force) \
            or (dsttag and dsttag['locked'] and not options.force):
        parser.error("Error: You are attempting to clone from or to a tag which is locked.\n"
                     "Please use --force if this is what you really want to do.")

    if options.test:
        parser.error("server-side operation, test output is no longer available")

    if dsttag:
        session.snapshotTagModify(srctag['id'], args[1],
                                  config=options.config,
                                  pkgs=options.pkgs,
                                  builds=options.builds,
                                  groups=options.groups,
                                  latest_only=options.latest_only,
                                  inherit_builds=options.inherit_builds,
                                  remove=options.delete,
                                  event=event.get('id'),
                                  force=options.force)
    else:
        session.snapshotTag(srctag['id'], args[1],
                            config=options.config,
                            pkgs=options.pkgs,
                            builds=options.builds,
                            groups=options.groups,
                            latest_only=options.latest_only,
                            inherit_builds=options.inherit_builds,
                            event=event.get('id'),
                            force=options.force)


def handle_add_target(goptions, session, args):
    "[admin] Create a new build target"
    usage = "usage: %prog add-target <name> <build tag> <dest tag>"
    parser = OptionParser(usage=get_usage_str(usage))
    (options, args) = parser.parse_args(args)
    if len(args) < 2:
        parser.error("Please specify a target name, a build tag, and destination tag")
    elif len(args) > 3:
        parser.error("Incorrect number of arguments")
    name = args[0]
    build_tag = args[1]
    if len(args) > 2:
        dest_tag = args[2]
    else:
        # most targets have the same name as their destination
        dest_tag = name
    activate_session(session, goptions)
    if not (session.hasPerm('admin') or session.hasPerm('target')):
        parser.error("This action requires target or admin privileges")

    chkbuildtag = session.getTag(build_tag)
    chkdesttag = session.getTag(dest_tag)
    if not chkbuildtag:
        error("No such tag: %s" % build_tag)
    if not chkbuildtag.get("arches", None):
        error("Build tag has no arches: %s" % build_tag)
    if not chkdesttag:
        error("No such destination tag: %s" % dest_tag)

    session.createBuildTarget(name, build_tag, dest_tag)


def handle_edit_target(goptions, session, args):
    "[admin] Set the name, build_tag, and/or dest_tag of an existing build target to new values"
    usage = "usage: %prog edit-target [options] <name>"
    parser = OptionParser(usage=get_usage_str(usage))
    parser.add_option("--rename", help="Specify new name for target")
    parser.add_option("--build-tag", help="Specify a different build tag")
    parser.add_option("--dest-tag", help="Specify a different destination tag")

    (options, args) = parser.parse_args(args)

    if len(args) != 1:
        parser.error("Please specify a build target")
    activate_session(session, goptions)

    if not (session.hasPerm('admin') or session.hasPerm('target')):
        parser.error("This action requires target or admin privileges")

    targetInfo = session.getBuildTarget(args[0])
    if targetInfo is None:
        raise koji.GenericError("No such build target: %s" % args[0])

    targetInfo['orig_name'] = targetInfo['name']

    if options.rename:
        targetInfo['name'] = options.rename
    if options.build_tag:
        targetInfo['build_tag_name'] = options.build_tag
        chkbuildtag = session.getTag(options.build_tag)
        if not chkbuildtag:
            error("No such tag: %s" % options.build_tag)
        if not chkbuildtag.get("arches", None):
            error("Build tag has no arches: %s" % options.build_tag)
    if options.dest_tag:
        chkdesttag = session.getTag(options.dest_tag)
        if not chkdesttag:
            error("No such destination tag: %s" % options.dest_tag)
        targetInfo['dest_tag_name'] = options.dest_tag

    session.editBuildTarget(targetInfo['orig_name'], targetInfo['name'],
                            targetInfo['build_tag_name'], targetInfo['dest_tag_name'])


def handle_remove_target(goptions, session, args):
    "[admin] Remove a build target"
    usage = "usage: %prog remove-target [options] <name>"
    parser = OptionParser(usage=get_usage_str(usage))
    (options, args) = parser.parse_args(args)

    if len(args) != 1:
        parser.error("Please specify a build target to remove")
    activate_session(session, goptions)

    if not (session.hasPerm('admin') or session.hasPerm('target')):
        parser.error("This action requires target or admin privileges")

    target = args[0]
    target_info = session.getBuildTarget(target)
    if not target_info:
        error("No such build target: %s" % target)

    session.deleteBuildTarget(target_info['id'])


def handle_remove_tag(goptions, session, args):
    "[admin] Remove a tag"
    usage = "usage: %prog remove-tag [options] <name>"
    parser = OptionParser(usage=get_usage_str(usage))
    (options, args) = parser.parse_args(args)

    if len(args) != 1:
        parser.error("Please specify a tag to remove")
    activate_session(session, goptions)

    if not (session.hasPerm('admin') or session.hasPerm('tag')):
        parser.error("This action requires tag or admin privileges")

    tag = args[0]
    tag_info = session.getTag(tag)
    if not tag_info:
        error("No such tag: %s" % tag)

    session.deleteTag(tag_info['id'])


def anon_handle_list_targets(goptions, session, args):
    "[info] List the build targets"
    usage = "usage: %prog list-targets [options]"
    parser = OptionParser(usage=get_usage_str(usage))
    parser.add_option("--name", help="Specify the build target name")
    parser.add_option("--quiet", action="store_true", default=goptions.quiet,
                      help="Do not print the header information")
    (options, args) = parser.parse_args(args)

    if len(args) != 0:
        parser.error("This command takes no arguments")
    ensure_connection(session, goptions)

    targets = session.getBuildTargets(options.name)
    if len(targets) == 0:
        if options.name:
            parser.error('No such build target: %s' % options.name)
        else:
            parser.error('No targets were found')

    fmt = "%(name)-30s %(build_tag_name)-30s %(dest_tag_name)-30s"
    if not options.quiet:
        print("%-30s %-30s %-30s" % ('Name', 'Buildroot', 'Destination'))
        print("-" * 93)
    tmp_list = sorted([(x['name'], x) for x in targets])
    targets = [x[1] for x in tmp_list]
    for target in targets:
        print(fmt % target)
    # pprint.pprint(session.getBuildTargets())


def _printInheritance(tags, sibdepths=None, reverse=False):
    if len(tags) == 0:
        return
    if sibdepths is None:
        sibdepths = []
    currtag = tags[0]
    tags = tags[1:]
    if reverse:
        siblings = len([tag for tag in tags if tag['parent_id'] == currtag['parent_id']])
    else:
        siblings = len([tag for tag in tags if tag['child_id'] == currtag['child_id']])

    sys.stdout.write(format_inheritance_flags(currtag))
    outdepth = 0
    for depth in sibdepths:
        if depth < currtag['currdepth']:
            outspacing = depth - outdepth
            sys.stdout.write(' ' * (outspacing * 3 - 1))
            sys.stdout.write(_printable_unicode(u'\u2502'))
            outdepth = depth

    sys.stdout.write(' ' * ((currtag['currdepth'] - outdepth) * 3 - 1))
    if siblings:
        sys.stdout.write(_printable_unicode(u'\u251c'))
    else:
        sys.stdout.write(_printable_unicode(u'\u2514'))
    sys.stdout.write(_printable_unicode(u'\u2500'))
    if reverse:
        sys.stdout.write('%(name)s (%(tag_id)i)\n' % currtag)
    else:
        sys.stdout.write('%(name)s (%(parent_id)i)\n' % currtag)

    if siblings:
        if len(sibdepths) == 0 or sibdepths[-1] != currtag['currdepth']:
            sibdepths.append(currtag['currdepth'])
    else:
        if len(sibdepths) > 0 and sibdepths[-1] == currtag['currdepth']:
            sibdepths.pop()

    _printInheritance(tags, sibdepths, reverse)


def anon_handle_list_tag_inheritance(goptions, session, args):
    "[info] Print the inheritance information for a tag"
    usage = """\
        usage: %prog list-tag-inheritance [options] <tag>

        Prints tag inheritance with basic information about links.
        Four flags could be seen in the output:
         M - maxdepth - limits inheritance to n-levels
         F - package filter (packages ignored for inheritance)
         I - intransitive link - inheritance immediately stops here
         N - noconfig - if tag is used in buildroot, its configuration values will not be used

        Exact values for maxdepth and package filter can be inquired by taginfo command.
    """
    usage = textwrap.dedent(usage)
    parser = OptionParser(usage=get_usage_str(usage))
    parser.add_option("--reverse", action="store_true",
                      help="Process tag's children instead of its parents")
    parser.add_option("--stop", help=SUPPRESS_HELP)
    parser.add_option("--jump", help=SUPPRESS_HELP)
    parser.add_option("--event", type='int', metavar="EVENT#", help="query at event")
    parser.add_option("--ts", type='int', metavar="TIMESTAMP",
                      help="query at last event before timestamp")
    parser.add_option("--repo", type='int', metavar="REPO#", help="query at event for a repo")
    (options, args) = parser.parse_args(args)
    if len(args) != 1:
        parser.error("This command takes exactly one argument: a tag name or ID")
    for deprecated in ('stop', 'jump'):
        if getattr(options, deprecated):
            parser.error("--%s option has been removed in 1.26" % deprecated)
    ensure_connection(session, goptions)
    event = koji.util.eventFromOpts(session, options)
    if event:
        event['timestr'] = time.asctime(time.localtime(event['ts']))
        print("Querying at event %(id)i (%(timestr)s)" % event)
    if event:
        tag = session.getTag(args[0], event=event['id'])
    else:
        tag = session.getTag(args[0])
    if not tag:
        parser.error("No such tag: %s" % args[0])

    opts = {}
    opts['reverse'] = options.reverse or False
    if event:
        opts['event'] = event['id']

    sys.stdout.write('     %s (%i)\n' % (tag['name'], tag['id']))
    data = session.getFullInheritance(tag['id'], **opts)
    _printInheritance(data, None, opts['reverse'])


def anon_handle_list_tags(goptions, session, args):
    "[info] Print the list of tags"
    usage = "usage: %prog list-tags [options] [pattern]"
    parser = OptionParser(usage=get_usage_str(usage))
    parser.add_option("--show-id", action="store_true", help="Show tag ids")
    parser.add_option("--verbose", action="store_true", help="Show more information")
    parser.add_option("--unlocked", action="store_true", help="Only show unlocked tags")
    parser.add_option("--build", help="Show tags associated with a build")
    parser.add_option("--package", help="Show tags associated with a package")
    (options, patterns) = parser.parse_args(args)
    ensure_connection(session, goptions)

    pkginfo = {}
    buildinfo = {}

    if options.package:
        pkginfo = session.getPackage(options.package)
        if not pkginfo:
            parser.error("No such package: %s" % options.package)

    if options.build:
        buildinfo = session.getBuild(options.build)
        if not buildinfo:
            parser.error("No such build: %s" % options.build)

    if not patterns:
        # list everything if no pattern is supplied
        tags = session.listTags(build=buildinfo.get('id', None),
                                package=pkginfo.get('id', None))
    else:
        # The hub may not support the pattern option. We try with that first
        # and fall back to the old way.
        fallback = False
        try:
            tags = []
            with session.multicall(strict=True) as m:
                for pattern in patterns:
                    tags.append(m.listTags(build=buildinfo.get('id', None),
                                           package=pkginfo.get('id', None),
                                           pattern=pattern))
            tags = list(itertools.chain(*[t.result for t in tags]))
        except koji.ParameterError:
            fallback = True
        if fallback:
            # without the pattern option, we have to filter client side
            tags = session.listTags(buildinfo.get('id', None), pkginfo.get('id', None))
            tags = [t for t in tags if koji.util.multi_fnmatch(t['name'], patterns)]

    tags.sort(key=lambda x: x['name'])
    # if options.verbose:
    #    fmt = "%(name)s [%(id)i] %(perm)s %(locked)s %(arches)s"
    if options.show_id:
        fmt = "%(name)s [%(id)i]"
    else:
        fmt = "%(name)s"
    for tag in tags:
        if options.unlocked:
            if tag['locked'] or tag['perm']:
                continue
        if not options.verbose:
            print(fmt % tag)
        else:
            sys.stdout.write(fmt % tag)
            if tag['locked']:
                sys.stdout.write(' [LOCKED]')
            if tag['perm']:
                sys.stdout.write(' [%(perm)s perm required]' % tag)
            print('')


def _print_histline(entry, **kwargs):
    options = kwargs['options']
    event_id, table, create, x = entry
    who = None
    edit = x.get('.related')
    if edit:
        del x['.related']
        bad_edit = None
        if len(edit) != 1:
            bad_edit = "%i elements" % (len(edit) + 1)
        other = edit[0]
        # check edit for sanity
        if create or not other[2]:
            bad_edit = "out of order"
        if event_id != other[0]:
            bad_edit = "non-matching"
        if bad_edit:
            warn("Unusual edit at event %i in table %s (%s)" % (event_id, table, bad_edit))
            # we'll simply treat them as separate events
            pprint.pprint(entry)
            pprint.pprint(edit)
            _print_histline(entry, **kwargs)
            for data in edit:
                _print_histline(entry, **kwargs)
            return
    if create:
        ts = x['create_ts']
        if 'creator_name' in x:
            who = "by %(creator_name)s"
    else:
        ts = x['revoke_ts']
        if 'revoker_name' in x:
            who = "by %(revoker_name)s"
    if table == 'tag_listing':
        if edit:
            fmt = "%(name)s-%(version)s-%(release)s re-tagged into %(tag.name)s"
        elif create:
            fmt = "%(name)s-%(version)s-%(release)s tagged into %(tag.name)s"
        else:
            fmt = "%(name)s-%(version)s-%(release)s untagged from %(tag.name)s"
    elif table == 'user_perms':
        if edit:
            fmt = "permission %(permission.name)s re-granted to %(user.name)s"
        elif create:
            fmt = "permission %(permission.name)s granted to %(user.name)s"
        else:
            fmt = "permission %(permission.name)s revoked for %(user.name)s"
    elif table == 'user_groups':
        if edit:
            fmt = "user %(user.name)s re-added to group %(group.name)s"
        elif create:
            fmt = "user %(user.name)s added to group %(group.name)s"
        else:
            fmt = "user %(user.name)s removed from group %(group.name)s"
    elif table == 'cg_users':
        if edit:
            fmt = "user %(user.name)s re-added to content generator %(content_generator.name)s"
        elif create:
            fmt = "user %(user.name)s added to content generator %(content_generator.name)s"
        else:
            fmt = "user %(user.name)s removed from content generator %(content_generator.name)s"
    elif table == 'tag_packages':
        if edit:
            fmt = "package list entry for %(package.name)s in %(tag.name)s updated"
        elif create:
            fmt = "package list entry created: %(package.name)s in %(tag.name)s"
        else:
            fmt = "package list entry revoked: %(package.name)s in %(tag.name)s"
    elif table == 'tag_package_owners':
        if edit:
            fmt = "package owner changed for %(package.name)s in %(tag.name)s"
        elif create:
            fmt = "package owner %(owner.name)s set for %(package.name)s in %(tag.name)s"
        else:
            fmt = "package owner %(owner.name)s revoked for %(package.name)s in %(tag.name)s"
    elif table == 'tag_inheritance':
        if edit:
            fmt = "inheritance line %(tag.name)s->%(parent.name)s updated"
        elif create:
            fmt = "inheritance line %(tag.name)s->%(parent.name)s added"
        else:
            fmt = "inheritance line %(tag.name)s->%(parent.name)s removed"
    elif table == 'tag_config':
        if edit:
            fmt = "tag configuration for %(tag.name)s altered"
        elif create:
            fmt = "new tag: %(tag.name)s"
        else:
            fmt = "tag deleted: %(tag.name)s"
    elif table == 'tag_extra':
        if edit:
            fmt = "tag option %(key)s for tag %(tag.name)s altered"
        elif create:
            fmt = "added tag option %(key)s for tag %(tag.name)s"
        else:
            fmt = "tag option %(key)s removed for %(tag.name)s"
    elif table == 'host_config':
        if edit:
            fmt = "host configuration for %(host.name)s altered"
        elif create:
            fmt = "new host: %(host.name)s"
        else:
            fmt = "host deleted: %(host.name)s"
    elif table == 'host_channels':
        if create:
            fmt = "host %(host.name)s added to channel %(channels.name)s"
        else:
            fmt = "host %(host.name)s removed from channel %(channels.name)s"
    elif table == 'build_target_config':
        if edit:
            fmt = "build target configuration for %(build_target.name)s updated"
        elif create:
            fmt = "new build target: %(build_target.name)s"
        else:
            fmt = "build target deleted: %(build_target.name)s"
    elif table == 'external_repo_config':
        if edit:
            fmt = "external repo configuration for %(external_repo.name)s altered"
        elif create:
            fmt = "new external repo: %(external_repo.name)s"
        else:
            fmt = "external repo deleted: %(external_repo.name)s"
    elif table == 'tag_external_repos':
        if edit:
            fmt = "external repo entry for %(external_repo.name)s in tag %(tag.name)s updated"
        elif create:
            fmt = "external repo entry for %(external_repo.name)s added to tag %(tag.name)s"
        else:
            fmt = "external repo entry for %(external_repo.name)s removed from tag %(tag.name)s"
    elif table == 'group_config':
        if edit:
            fmt = "group %(group.name)s configuration for tag %(tag.name)s updated"
        elif create:
            fmt = "group %(group.name)s added to tag %(tag.name)s"
        else:
            fmt = "group %(group.name)s removed from tag %(tag.name)s"
    elif table == 'group_req_listing':
        if edit:
            fmt = "group dependency %(group.name)s->%(req.name)s updated in tag %(tag.name)s"
        elif create:
            fmt = "group dependency %(group.name)s->%(req.name)s added in tag %(tag.name)s"
        else:
            fmt = "group dependency %(group.name)s->%(req.name)s dropped from tag %(tag.name)s"
    elif table == 'group_package_listing':
        if edit:
            fmt = "package entry %(package)s in group %(group.name)s, tag %(tag.name)s updated"
        elif create:
            fmt = "package %(package)s added to group %(group.name)s in tag %(tag.name)s"
        else:
            fmt = "package %(package)s removed from group %(group.name)s in tag %(tag.name)s"
    else:
        if edit:
            fmt = "%s entry updated" % table
        elif create:
            fmt = "%s entry created" % table
        else:
            fmt = "%s entry revoked" % table
    if options.utc:
        time_str = time.asctime(datetime.fromtimestamp(ts, tzutc()).timetuple())
    else:
        time_str = time.asctime(time.localtime(ts))

    parts = [time_str, fmt % x]
    if options.events or options.verbose:
        parts.insert(1, "(eid %i)" % event_id)
    if who:
        parts.append(who % x)
    if (create and x['active']) or (edit and other[-1]['active']):
        parts.append("[still active]")
    print(' '.join(parts))
    hidden_fields = ['active', 'create_event', 'revoke_event', 'creator_id', 'revoker_id',
                     'creator_name', 'revoker_name', 'create_ts', 'revoke_ts']

    def get_nkey(key):
        if key == 'perm_id':
            return 'permission.name'
        elif key.endswith('_id'):
            return '%s.name' % key[:-3]
        else:
            return '%s.name' % key
    if edit:
        keys = sorted(to_list(x.keys()))
        y = other[-1]
        for key in keys:
            if key in hidden_fields:
                continue
            if x[key] == y[key]:
                continue
            if key[0] == '_':
                continue
            nkey = get_nkey(key)
            if nkey in x and nkey in y:
                continue
            print("    %s: %s -> %s" % (key, x[key], y[key]))
    elif create and options.verbose and table != 'tag_listing':
        keys = sorted(to_list(x.keys()))
        # the table keys have already been represented in the base format string
        also_hidden = list(_table_keys[table])
        also_hidden.extend([get_nkey(k) for k in also_hidden])
        for key in keys:
            if key in hidden_fields or key in also_hidden:
                continue
            nkey = get_nkey(key)
            if nkey in x:
                continue
            if key[0] == '_':
                continue
            if x.get('blocked') and key != 'blocked':
                continue
            if key.endswith('.name'):
                dkey = key[:-5]
            else:
                dkey = key
            print("    %s: %s" % (dkey, x[key]))


_table_keys = {
    'user_perms': ['user_id', 'perm_id'],
    'user_groups': ['user_id', 'group_id'],
    'cg_users': ['user_id', 'cg_id'],
    'tag_inheritance': ['tag_id', 'parent_id'],
    'tag_config': ['tag_id'],
    'tag_extra': ['tag_id', 'key'],
    'build_target_config': ['build_target_id'],
    'external_repo_config': ['external_repo_id'],
    'host_config': ['host_id'],
    'host_channels': ['host_id', 'channel_id'],
    'tag_external_repos': ['tag_id', 'external_repo_id'],
    'tag_listing': ['build_id', 'tag_id'],
    'tag_packages': ['package_id', 'tag_id'],
    'tag_package_owners': ['package_id', 'tag_id'],
    'group_config': ['group_id', 'tag_id'],
    'group_req_listing': ['group_id', 'tag_id', 'req_id'],
    'group_package_listing': ['group_id', 'tag_id', 'package'],
}


def anon_handle_list_history(goptions, session, args):
    "[info] Display historical data"
    usage = "usage: %prog list-history [options]"
    parser = OptionParser(usage=get_usage_str(usage), option_class=TimeOption)
    # Don't use local debug option, this one stays here for backward compatibility
    # https://pagure.io/koji/issue/2084
    parser.add_option("--debug", action="store_true", default=goptions.debug, help=SUPPRESS_HELP)
    parser.add_option("--build", help="Only show data for a specific build")
    parser.add_option("--package", help="Only show data for a specific package")
    parser.add_option("--tag", help="Only show data for a specific tag")
    parser.add_option("--editor", "--by", metavar="USER",
                      help="Only show entries modified by user")
    parser.add_option("--user", help="Only show entries affecting a user")
    parser.add_option("--permission", help="Only show entries relating to a given permission")
    parser.add_option("--cg", help="Only show entries relating to a given content generator")
    parser.add_option("--external-repo", "--erepo",
                      help="Only show entries relating to a given external repo")
    parser.add_option("--build-target", "--target",
                      help="Only show entries relating to a given build target")
    parser.add_option("--group", help="Only show entries relating to a given group")
    parser.add_option("--host", help="Only show entries related to given host")
    parser.add_option("--channel", help="Only show entries related to given channel")
    parser.add_option("--xkey", help="Only show entries related to given tag extra key")
    parser.add_option("--before", type="time",
                      help="Only show entries before this time, " + TimeOption.get_help())
    parser.add_option("--after", type="time",
                      help="Only show entries after timestamp (same format as for --before)")
    parser.add_option("--before-event", metavar="EVENT_ID", type='int',
                      help="Only show entries before event")
    parser.add_option("--after-event", metavar="EVENT_ID", type='int',
                      help="Only show entries after event")
    parser.add_option("--watch", action="store_true", help="Monitor history data")
    parser.add_option("--active", action='store_true',
                      help="Only show entries that are currently active")
    parser.add_option("--revoked", action='store_false', dest='active',
                      help="Only show entries that are currently revoked")
    parser.add_option("--context", action="store_true", help="Show related entries")
    parser.add_option("-s", "--show", action="append", help="Show data from selected tables")
    parser.add_option("-v", "--verbose", action="store_true", help="Show more detail")
    parser.add_option("-e", "--events", action="store_true", help="Show event ids")
    parser.add_option("--all", action="store_true",
                      help="Allows listing the entire global history")
    parser.add_option("--utc", action="store_true",
                      help="Shows time in UTC timezone")
    (options, args) = parser.parse_args(args)
    if len(args) != 0:
        parser.error("This command takes no arguments")
    kwargs = {}
    limited = False
    for opt in ('package', 'tag', 'build', 'editor', 'user', 'permission',
                'cg', 'external_repo', 'build_target', 'group', 'before',
                'after', 'host', 'channel', 'xkey'):
        val = getattr(options, opt)
        if val:
            kwargs[opt] = val
            limited = True
    if options.before_event:
        kwargs['beforeEvent'] = options.before_event
    if options.after_event:
        kwargs['afterEvent'] = options.after_event
    if options.active is not None:
        kwargs['active'] = options.active
    if options.host:
        hostinfo = session.getHost(options.host)
        if not hostinfo:
            error("No such host: %s" % options.host)
    if options.channel:
        channelinfo = session.getChannel(options.channel)
        if not channelinfo:
            error("No such channel: %s" % options.channel)
    if options.utc:
        kwargs['utc'] = options.utc
    tables = None
    if options.show:
        tables = []
        for arg in options.show:
            tables.extend(arg.split(','))
    if not limited and not options.all:
        parser.error("Please specify an option to limit the query")

    ensure_connection(session, goptions)

    if options.watch:
        if not kwargs.get('afterEvent') and not kwargs.get('after'):
            kwargs['afterEvent'] = session.getLastEvent()['id']

    while True:
        histdata = session.queryHistory(tables=tables, **kwargs)
        timeline = []

        def distinguish_match(x, name):
            """determine if create or revoke event matched"""
            if options.context:
                return True
            name = "_" + name
            ret = True
            for key in x:
                if key.startswith(name):
                    ret = ret and x[key]
            return ret
        for table in histdata:
            hist = histdata[table]
            for x in hist:
                if x['revoke_event'] is not None:
                    if distinguish_match(x, 'revoked'):
                        timeline.append((x['revoke_event'], table, 0, x.copy()))
                    # pprint.pprint(timeline[-1])
                if distinguish_match(x, 'created'):
                    timeline.append((x['create_event'], table, 1, x))
        timeline.sort(key=lambda entry: entry[:3])
        # group edits together
        new_timeline = []
        last_event = None
        edit_index = {}
        for entry in timeline:
            event_id, table, create, x = entry
            if event_id != last_event:
                edit_index = {}
                last_event = event_id
            key = tuple([x[k] for k in _table_keys[table]])
            prev = edit_index.get((table, event_id), {}).get(key)
            if prev:
                prev[-1].setdefault('.related', []).append(entry)
            else:
                edit_index.setdefault((table, event_id), {})[key] = entry
                new_timeline.append(entry)
        for entry in new_timeline:
            if options.debug:
                print("%r" % list(entry))
            _print_histline(entry, options=options)
        if not options.watch:
            break
        else:
            time.sleep(goptions.poll_interval)
            # repeat query for later events
            if last_event:
                kwargs['afterEvent'] = last_event


def _handleMap(lines, data, prefix=''):
    for key, val in data.items():
        if key != '__starstar':
            lines.append('  %s%s: %s' % (prefix, key, val))


def _handleOpts(lines, opts, prefix=''):
    if opts:
        lines.append("%sOptions:" % prefix)
        _handleMap(lines, opts, prefix)


def _parseTaskParams(session, method, task_id, topdir):
    try:
        return _do_parseTaskParams(session, method, task_id, topdir)
    except Exception:
        logger = logging.getLogger("koji")
        if logger.isEnabledFor(logging.DEBUG):
            tb_str = ''.join(traceback.format_exception(*sys.exc_info()))
            logger.debug(tb_str)
        return ['Unable to parse task parameters']


def _do_parseTaskParams(session, method, task_id, topdir):
    """Parse the return of getTaskRequest()"""
    params = session.getTaskRequest(task_id)

    lines = []

    if method == 'buildSRPMFromCVS':
        lines.append("CVS URL: %s" % params[0])
    elif method == 'buildSRPMFromSCM':
        lines.append("SCM URL: %s" % params[0])
    elif method == 'buildArch':
        lines.append("SRPM: %s/work/%s" % (topdir, params[0]))
        taginfo = session.getTag(params[1])
        if taginfo:
            tagname = taginfo['name']
        else:
            tagname = str(params[1]) + " (deleted)"
        lines.append("Build Tag: %s" % tagname)
        lines.append("Build Arch: %s" % params[2])
        lines.append("SRPM Kept: %r" % params[3])
        if len(params) > 4:
            _handleOpts(lines, params[4])
    elif method == 'tagBuild':
        build = session.getBuild(params[1])
        lines.append("Destination Tag: %s" % session.getTag(params[0])['name'])
        lines.append("Build: %s" % koji.buildLabel(build))
    elif method == 'buildNotification':
        build = params[1]
        buildTarget = params[2]
        lines.append("Recipients: %s" % (", ".join(params[0])))
        lines.append("Build: %s" % koji.buildLabel(build))
        lines.append("Build Target: %s" % buildTarget['name'])
        lines.append("Web URL: %s" % params[3])
    elif method == 'build':
        lines.append("Source: %s" % params[0])
        lines.append("Build Target: %s" % params[1])
        if len(params) > 2:
            _handleOpts(lines, params[2])
    elif method == 'maven':
        lines.append("SCM URL: %s" % params[0])
        lines.append("Build Target: %s" % params[1])
        if len(params) > 2:
            _handleOpts(lines, params[2])
    elif method == 'buildMaven':
        lines.append("SCM URL: %s" % params[0])
        lines.append("Build Tag: %s" % params[1]['name'])
        if len(params) > 2:
            _handleOpts(lines, params[2])
    elif method == 'wrapperRPM':
        lines.append("Spec File URL: %s" % params[0])
        lines.append("Build Tag: %s" % params[1]['name'])
        if params[2]:
            lines.append("Build: %s" % koji.buildLabel(params[2]))
        if params[3]:
            lines.append("Task: %s %s" % (params[3]['id'], koji.taskLabel(params[3])))
        if len(params) > 4:
            _handleOpts(lines, params[4])
    elif method == 'chainmaven':
        lines.append("Builds:")
        for package, opts in params[0].items():
            lines.append("  " + package)
            _handleMap(lines, opts, prefix="  ")
        lines.append("Build Target: %s" % params[1])
        if len(params) > 2:
            _handleOpts(lines, params[2])
    elif method == 'winbuild':
        lines.append("VM: %s" % params[0])
        lines.append("SCM URL: %s" % params[1])
        lines.append("Build Target: %s" % params[2])
        if len(params) > 3:
            _handleOpts(lines, params[3])
    elif method == 'vmExec':
        lines.append("VM: %s" % params[0])
        lines.append("Exec Params:")
        for info in params[1]:
            if isinstance(info, dict):
                _handleMap(lines, info, prefix='  ')
            else:
                lines.append("  %s" % info)
        if len(params) > 2:
            _handleOpts(lines, params[2])
    elif method in ('createLiveCD', 'createAppliance', 'createLiveMedia'):
        argnames = ['Name', 'Version', 'Release', 'Arch', 'Target Info', 'Build Tag', 'Repo',
                    'Kickstart File']
        for n, v in zip(argnames, params):
            lines.append("%s: %s" % (n, v))
        if len(params) > 8:
            _handleOpts(lines, params[8])
    elif method in ('appliance', 'livecd', 'livemedia'):
        argnames = ['Name', 'Version', 'Arches', 'Target', 'Kickstart']
        for n, v in zip(argnames, params):
            lines.append("%s: %s" % (n, v))
        if len(params) > 5:
            _handleOpts(lines, params[5])
    elif method == 'newRepo':
        tag = session.getTag(params[0])
        lines.append("Tag: %s" % tag['name'])
    elif method == 'prepRepo':
        lines.append("Tag: %s" % params[0]['name'])
    elif method == 'createrepo':
        lines.append("Repo ID: %i" % params[0])
        lines.append("Arch: %s" % params[1])
        oldrepo = params[2]
        if oldrepo:
            lines.append("Old Repo ID: %i" % oldrepo['id'])
            lines.append("Old Repo Creation: %s" % koji.formatTimeLong(oldrepo['create_ts']))
        if len(params) > 3:
            lines.append("External Repos: %s" %
                         ', '.join([ext['external_repo_name'] for ext in params[3]]))
    elif method == 'tagNotification':
        destTag = session.getTag(params[2])
        srcTag = None
        if params[3]:
            srcTag = session.getTag(params[3])
        build = session.getBuild(params[4])
        user = session.getUser(params[5])

        lines.append("Recipients: %s" % ", ".join(params[0]))
        lines.append("Successful?: %s" % (params[1] and 'yes' or 'no'))
        lines.append("Tagged Into: %s" % destTag['name'])
        if srcTag:
            lines.append("Moved From: %s" % srcTag['name'])
        lines.append("Build: %s" % koji.buildLabel(build))
        lines.append("Tagged By: %s" % user['name'])
        lines.append("Ignore Success?: %s" % (params[6] and 'yes' or 'no'))
        if params[7]:
            lines.append("Failure Message: %s" % params[7])
    elif method == 'dependantTask':
        lines.append("Dependant Tasks: %s" % ", ".join([str(depID) for depID in params[0]]))
        lines.append("Subtasks:")
        for subtask in params[1]:
            lines.append("  Method: %s" % subtask[0])
            lines.append("  Parameters: %s" %
                         ", ".join([str(subparam) for subparam in subtask[1]]))
            if len(subtask) > 2 and subtask[2]:
                subopts = subtask[2]
                _handleOpts(lines, subopts, prefix='  ')
            lines.append("")
    elif method == 'chainbuild':
        lines.append("Build Groups:")
        group_num = 0
        for group_list in params[0]:
            group_num += 1
            lines.append("  %i: %s" % (group_num, ', '.join(group_list)))
        lines.append("Build Target: %s" % params[1])
        if len(params) > 2:
            _handleOpts(lines, params[2])
    elif method == 'waitrepo':
        lines.append("Build Target: %s" % params[0])
        if params[1]:
            lines.append("Newer Than: %s" % params[1])
        if params[2]:
            lines.append("NVRs: %s" % ', '.join(params[2]))

    return lines


def _printTaskInfo(session, task_id, topdir, level=0, recurse=True, verbose=True):
    """Recursive function to print information about a task
       and its children."""

    BUILDDIR = '/var/lib/mock'
    indent = " " * 2 * level

    info = session.getTaskInfo(task_id)

    if info is None:
        raise koji.GenericError("No such task: %d" % task_id)

    if info['host_id']:
        host_info = session.getHost(info['host_id'])
    else:
        host_info = None
    buildroot_infos = session.listBuildroots(taskID=task_id)
    build_info = session.listBuilds(taskID=task_id)

    files = list_task_output_all_volumes(session, task_id)
    logs = []
    output = []
    for filename in files:
        if filename.endswith('.log'):
            logs += [os.path.join(koji.pathinfo.work(volume=volume),
                                  koji.pathinfo.taskrelpath(task_id),
                                  filename) for volume in files[filename]]
        else:
            output += [os.path.join(koji.pathinfo.work(volume=volume),
                                    koji.pathinfo.taskrelpath(task_id),
                                    filename) for volume in files[filename]]

    owner = session.getUser(info['owner'])['name']

    print("%sTask: %d" % (indent, task_id))
    print("%sType: %s" % (indent, info['method']))
    if verbose:
        print("%sRequest Parameters:" % indent)
        for line in _parseTaskParams(session, info['method'], task_id, topdir):
            print("%s  %s" % (indent, line))
    print("%sOwner: %s" % (indent, owner))
    print("%sState: %s" % (indent, koji.TASK_STATES[info['state']].lower()))
    print("%sCreated: %s" % (indent, time.asctime(time.localtime(info['create_ts']))))
    if info.get('start_ts'):
        print("%sStarted: %s" % (indent, time.asctime(time.localtime(info['start_ts']))))
    if info.get('completion_ts'):
        print("%sFinished: %s" % (indent, time.asctime(time.localtime(info['completion_ts']))))
    if host_info:
        print("%sHost: %s" % (indent, host_info['name']))
    if build_info:
        print("%sBuild: %s (%d)" % (indent, build_info[0]['nvr'], build_info[0]['build_id']))
    if buildroot_infos:
        print("%sBuildroots:" % indent)
        for root in buildroot_infos:
            print("%s  %s/%s-%d-%d/" %
                  (indent, BUILDDIR, root['tag_name'], root['id'], root['repo_id']))
    if logs:
        print("%sLog Files:" % indent)
        for log_path in logs:
            print("%s  %s" % (indent, log_path))
    if output:
        print("%sOutput:" % indent)
        for file_path in output:
            print("%s  %s" % (indent, file_path))

    # white space
    print('')

    if recurse:
        level += 1
        children = session.getTaskChildren(task_id, request=True)
        children.sort(key=lambda x: x['id'])
        for child in children:
            _printTaskInfo(session, child['id'], topdir, level, verbose=verbose)


def anon_handle_taskinfo(goptions, session, args):
    """[info] Show information about a task"""
    usage = "usage: %prog taskinfo [options] <task_id> [<task_id> ...]"
    parser = OptionParser(usage=get_usage_str(usage))
    parser.add_option("-r", "--recurse", action="store_true",
                      help="Show children of this task as well")
    parser.add_option("-v", "--verbose", action="store_true", help="Be verbose")
    (options, args) = parser.parse_args(args)
    if len(args) < 1:
        parser.error("You must specify at least one task ID")

    ensure_connection(session, goptions)

    for arg in args:
        task_id = int(arg)
        _printTaskInfo(session, task_id, goptions.topdir, 0, options.recurse, options.verbose)


def anon_handle_taginfo(goptions, session, args):
    "[info] Print basic information about a tag"
    usage = "usage: %prog taginfo [options] <tag> [<tag> ...]"
    parser = OptionParser(usage=get_usage_str(usage))
    parser.add_option("--event", type='int', metavar="EVENT#", help="query at event")
    parser.add_option("--ts", type='int', metavar="TIMESTAMP",
                      help="query at last event before timestamp")
    parser.add_option("--repo", type='int', metavar="REPO#", help="query at event for a repo")
    (options, args) = parser.parse_args(args)
    if len(args) < 1:
        parser.error("Please specify a tag")
    ensure_connection(session, goptions)
    event = koji.util.eventFromOpts(session, options)
    event_opts = {}
    if event:
        event['timestr'] = time.asctime(time.localtime(event['ts']))
        print("Querying at event %(id)i (%(timestr)s)" % event)
        event_opts['event'] = event['id']
    perms = dict([(p['id'], p['name']) for p in session.getAllPerms()])

    tags = []
    for tag in args:
        info = session.getBuildConfig(tag, **event_opts)
        if info is None:
            try:
                info = session.getBuildConfig(int(tag), **event_opts)
            except ValueError:
                info = None
            if info is None:
                parser.error('No such tag: %s' % tag)
        tags.append(info)

    for n, info in enumerate(tags):
        if n > 0:
            print('')
        print("Tag: %(name)s [%(id)d]" % info)
        print("Arches: %(arches)s" % info)
        group_list = sorted([x['name'] for x in session.getTagGroups(info['id'], **event_opts)])
        print("Groups: " + ', '.join(group_list))
        if info.get('locked'):
            print('LOCKED')
        if info.get('perm_id') is not None:
            perm_id = info['perm_id']
            print("Required permission: %r" % perms.get(perm_id, perm_id))
        if session.mavenEnabled():
            print("Maven support?: %s" % (info['maven_support'] and 'yes' or 'no'))
            print("Include all Maven archives?: %s" %
                  (info['maven_include_all'] and 'yes' or 'no'))
        if 'extra' in info:
            print("Tag options:")
            for key in sorted(info['extra'].keys()):
                line = "  %s : %s" % (key, pprint.pformat(info['extra'][key]))
                if key in info.get('config_inheritance', {}).get('extra', []):
                    line = "%-30s [%s]" % (line, info['config_inheritance']['extra'][key]['name'])
                print(line)
        dest_targets = session.getBuildTargets(destTagID=info['id'], **event_opts)
        build_targets = session.getBuildTargets(buildTagID=info['id'], **event_opts)
        repos = {}
        if not event:
            for target in dest_targets + build_targets:
                if target['build_tag'] not in repos:
                    repo = session.getRepo(target['build_tag'])
                    if repo is None:
                        repos[target['build_tag']] = "no active repo"
                    else:
                        repos[target['build_tag']] = "repo#%(id)i: %(creation_time)s" % repo
        if dest_targets:
            print("Targets that build into this tag:")
            for target in dest_targets:
                if event:
                    print("  %s (%s)" % (target['name'], target['build_tag_name']))
                else:
                    print("  %s (%s, %s)" %
                          (target['name'], target['build_tag_name'], repos[target['build_tag']]))
        if build_targets:
            print("This tag is a buildroot for one or more targets")
            if not event:
                print("Current repo: %s" % repos[info['id']])
            print("Targets that build from this tag:")
            for target in build_targets:
                print("  %s" % target['name'])
        external_repos = session.getTagExternalRepos(tag_info=info['id'], **event_opts)
        if external_repos:
            print("External repos:")
            for rinfo in external_repos:
                if 'arches' not in rinfo:
                    # older hubs will not return this field
                    rinfo['arches'] = '-'
                elif not rinfo['arches']:
                    rinfo['arches'] = 'inherited from tag'
                    # TODO else intersection of arches?
                print("  %(priority)3i %(external_repo_name)s "
                      "(%(url)s, merge mode: %(merge_mode)s), arches: %(arches)s" % rinfo)
        print("Inheritance:")
        for parent in session.getInheritanceData(info['id'], **event_opts):
            parent['flags'] = format_inheritance_flags(parent)
            print("  %(priority)-4d %(flags)s %(name)s [%(parent_id)s]" % parent)
            if parent['maxdepth'] is not None:
                print("    maxdepth: %(maxdepth)s" % parent)
            if parent['pkg_filter']:
                print("    package filter: %(pkg_filter)s" % parent)


def handle_add_tag(goptions, session, args):
    "[admin] Add a new tag to the database"
    usage = "usage: %prog add-tag [options] <name>"
    parser = OptionParser(usage=get_usage_str(usage))
    parser.add_option("--parent", help="Set a parent tag with priority 0")
    parser.add_option("--arches", help="Specify arches")
    parser.add_option("--maven-support", action="store_true",
                      help="Enable creation of Maven repos for this tag")
    parser.add_option("--include-all", action="store_true",
                      help="Include all packages in this tag when generating Maven repos")
    parser.add_option("-x", "--extra", action="append", default=[], metavar="key=value",
                      help="Set tag extra option")
    (options, args) = parser.parse_args(args)
    if len(args) != 1:
        parser.error("Please specify a name for the tag")
    activate_session(session, goptions)
    if not (session.hasPerm('admin') or session.hasPerm('tag')):
        parser.error("This action requires tag or admin privileges")
    opts = {}
    if options.parent:
        opts['parent'] = options.parent
    if options.arches:
        opts['arches'] = koji.parse_arches(options.arches)
    if options.maven_support:
        opts['maven_support'] = True
    if options.include_all:
        opts['maven_include_all'] = True
    if options.extra:
        extra = {}
        for xopt in options.extra:
            key, value = xopt.split('=', 1)
            value = arg_filter(value)
            extra[key] = value
        opts['extra'] = extra
    session.createTag(args[0], **opts)


def handle_edit_tag(goptions, session, args):
    "[admin] Alter tag information"
    usage = "usage: %prog edit-tag [options] <name>"
    parser = OptionParser(usage=get_usage_str(usage))
    parser.add_option("--arches", help="Specify arches")
    parser.add_option("--perm", help="Specify permission requirement")
    parser.add_option("--no-perm", action="store_true", help="Remove permission requirement")
    parser.add_option("--lock", action="store_true", help="Lock the tag")
    parser.add_option("--unlock", action="store_true", help="Unlock the tag")
    parser.add_option("--rename", help="Rename the tag")
    parser.add_option("--maven-support", action="store_true",
                      help="Enable creation of Maven repos for this tag")
    parser.add_option("--no-maven-support", action="store_true",
                      help="Disable creation of Maven repos for this tag")
    parser.add_option("--include-all", action="store_true",
                      help="Include all packages in this tag when generating Maven repos")
    parser.add_option("--no-include-all", action="store_true",
                      help="Do not include all packages in this tag when generating Maven repos")
    parser.add_option("-x", "--extra", action="append", default=[], metavar="key=value",
                      help="Set tag extra option. JSON-encoded or simple value")
    parser.add_option("-r", "--remove-extra", action="append", default=[], metavar="key",
                      help="Remove tag extra option")
    parser.add_option("-b", "--block-extra", action="append", default=[], metavar="key",
                      help="Block inherited tag extra option")
    (options, args) = parser.parse_args(args)
    if len(args) != 1:
        parser.error("Please specify a name for the tag")
    activate_session(session, goptions)
    tag = args[0]
    opts = {}
    if options.arches:
        opts['arches'] = koji.parse_arches(options.arches)
    if options.no_perm:
        opts['perm'] = None
    elif options.perm:
        opts['perm'] = options.perm
    if options.unlock:
        opts['locked'] = False
    if options.lock:
        opts['locked'] = True
    if options.rename:
        opts['name'] = options.rename
    if options.maven_support:
        opts['maven_support'] = True
    if options.no_maven_support:
        opts['maven_support'] = False
    if options.include_all:
        opts['maven_include_all'] = True
    if options.no_include_all:
        opts['maven_include_all'] = False
    if options.extra:
        extra = {}
        for xopt in options.extra:
            key, value = xopt.split('=', 1)
            if key in extra:
                parser.error("Duplicate extra key: %s" % key)
            extra[key] = arg_filter(value, parse_json=True)
        opts['extra'] = extra
    opts['remove_extra'] = options.remove_extra
    opts['block_extra'] = options.block_extra
    # XXX change callname
    session.editTag2(tag, **opts)


def handle_lock_tag(goptions, session, args):
    "[admin] Lock a tag"
    usage = "usage: %prog lock-tag [options] <tag> [<tag> ...]"
    parser = OptionParser(usage=get_usage_str(usage))
    parser.add_option("--perm", help="Specify permission requirement")
    parser.add_option("--glob", action="store_true", help="Treat args as glob patterns")
    parser.add_option("--master", action="store_true", help="Lock the master lock")
    parser.add_option("-n", "--test", action="store_true", help="Test mode")
    (options, args) = parser.parse_args(args)
    if len(args) < 1:
        parser.error("Please specify a tag")
    activate_session(session, goptions)
    pdata = session.getAllPerms()
    perm_ids = dict([(p['name'], p['id']) for p in pdata])
    perm = options.perm
    if perm is None:
        perm = 'admin'
    perm_id = perm_ids[perm]
    if options.glob:
        selected = []
        for tag in session.listTags():
            for pattern in args:
                if fnmatch.fnmatch(tag['name'], pattern):
                    selected.append(tag)
                    break
        if not selected:
            print("No tags matched")
    else:
        selected = [session.getTag(name, strict=True) for name in args]
    for tag in selected:
        if options.master:
            # set the master lock
            if tag['locked']:
                print("Tag %s: master lock already set" % tag['name'])
                continue
            elif options.test:
                print("Would have set master lock for: %s" % tag['name'])
                continue
            session.editTag2(tag['id'], locked=True)
        else:
            if tag['perm_id'] == perm_id:
                print("Tag %s: %s permission already required" % (tag['name'], perm))
                continue
            elif options.test:
                print("Would have set permission requirement %s for tag %s" % (perm, tag['name']))
                continue
            session.editTag2(tag['id'], perm_id=perm_id)


def handle_unlock_tag(goptions, session, args):
    "[admin] Unlock a tag"
    usage = "usage: %prog unlock-tag [options] <tag> [<tag> ...]"
    parser = OptionParser(usage=get_usage_str(usage))
    parser.add_option("--glob", action="store_true", help="Treat args as glob patterns")
    parser.add_option("-n", "--test", action="store_true", help="Test mode")
    (options, args) = parser.parse_args(args)
    if len(args) < 1:
        parser.error("Please specify a tag")
    activate_session(session, goptions)
    if options.glob:
        selected = []
        for tag in session.listTags():
            for pattern in args:
                if fnmatch.fnmatch(tag['name'], pattern):
                    selected.append(tag)
                    break
        if not selected:
            print("No tags matched")
    else:
        selected = []
        for name in args:
            tag = session.getTag(name)
            if tag is None:
                parser.error("No such tag: %s" % name)
            selected.append(tag)
    for tag in selected:
        opts = {}
        if tag['locked']:
            opts['locked'] = False
        if tag['perm_id']:
            opts['perm'] = None
        if not opts:
            print("Tag %(name)s: not locked" % tag)
            continue
        if options.test:
            print("Tag %s: skipping changes: %r" % (tag['name'], opts))
        else:
            session.editTag2(tag['id'], **opts)


def handle_add_tag_inheritance(goptions, session, args):
    """[admin] Add to a tag's inheritance"""
    usage = "usage: %prog add-tag-inheritance [options] <tag> <parent-tag>"
    parser = OptionParser(usage=get_usage_str(usage))
    parser.add_option("--priority", help="Specify priority")
    parser.add_option("--maxdepth", help="Specify max depth")
    parser.add_option("--intransitive", action="store_true", help="Set intransitive")
    parser.add_option("--noconfig", action="store_true", help="Set to packages only")
    parser.add_option("--pkg-filter", help="Specify the package filter")
    parser.add_option("--force", action="store_true",
                      help="Force adding a parent to a tag that already has that parent tag")
    (options, args) = parser.parse_args(args)

    if len(args) != 2:
        parser.error("This command takes exactly two arguments: a tag name or ID and that tag's "
                     "new parent name or ID")

    activate_session(session, goptions)

    tag = session.getTag(args[0])
    if not tag:
        parser.error("No such tag: %s" % args[0])

    parent = session.getTag(args[1])
    if not parent:
        parser.error("No such tag: %s" % args[1])

    inheritanceData = session.getInheritanceData(tag['id'])
    priority = options.priority and int(options.priority) or 0
    sameParents = [datum for datum in inheritanceData if datum['parent_id'] == parent['id']]
    samePriority = [datum for datum in inheritanceData if datum['priority'] == priority]

    if sameParents and not options.force:
        warn("Error: You are attempting to add %s as %s's parent even though it already is "
             "%s's parent."
             % (parent['name'], tag['name'], tag['name']))
        error("Please use --force if this is what you really want to do.")
    if samePriority:
        error("Error: There is already an active inheritance with that priority on %s, "
              "please specify a different priority with --priority." % tag['name'])

    new_data = {}
    new_data['parent_id'] = parent['id']
    new_data['priority'] = options.priority or 0
    if options.maxdepth and options.maxdepth.isdigit():
        new_data['maxdepth'] = int(options.maxdepth)
    else:
        new_data['maxdepth'] = None
    new_data['intransitive'] = options.intransitive or False
    new_data['noconfig'] = options.noconfig or False
    new_data['pkg_filter'] = options.pkg_filter or ''

    inheritanceData.append(new_data)
    session.setInheritanceData(tag['id'], inheritanceData)


def handle_edit_tag_inheritance(goptions, session, args):
    """[admin] Edit tag inheritance"""
    usage = "usage: %prog edit-tag-inheritance [options] <tag> <parent> <priority>"
    parser = OptionParser(usage=get_usage_str(usage))
    parser.add_option("--priority", help="Specify a new priority")
    parser.add_option("--maxdepth", help="Specify max depth")
    parser.add_option("--intransitive", action="store_true", help="Set intransitive")
    parser.add_option("--noconfig", action="store_true", help="Set to packages only")
    parser.add_option("--pkg-filter", help="Specify the package filter")
    (options, args) = parser.parse_args(args)

    if len(args) < 1:
        parser.error("This command takes at least one argument: a tag name or ID")

    if len(args) > 3:
        parser.error("This command takes at most three argument: a tag name or ID, "
                     "a parent tag name or ID, and a priority")

    activate_session(session, goptions)

    tag = session.getTag(args[0])
    if not tag:
        parser.error("No such tag: %s" % args[0])

    parent = None
    priority = None
    if len(args) > 1:
        parent = session.getTag(args[1])
        if not parent:
            parser.error("No such tag: %s" % args[1])
        if len(args) > 2:
            priority = args[2]

    data = session.getInheritanceData(tag['id'])
    if parent and data:
        data = [datum for datum in data if datum['parent_id'] == parent['id']]
    if priority and data:
        data = [datum for datum in data if datum['priority'] == priority]

    if len(data) == 0:
        error("No inheritance link found to remove.  Please check your arguments")
    elif len(data) > 1:
        print("Multiple matches for tag.")
        if not parent:
            error("Please specify a parent on the command line.")
        if not priority:
            error("Please specify a priority on the command line.")
        error("Error: Key constraints may be broken.  Exiting.")

    # len(data) == 1
    data = data[0]

    inheritanceData = session.getInheritanceData(tag['id'])
    samePriority = [datum for datum in inheritanceData if datum['priority'] == options.priority]
    if samePriority:
        error("Error: There is already an active inheritance with that priority on %s, "
              "please specify a different priority with --priority." % tag['name'])

    new_data = data.copy()
    if options.priority is not None and options.priority.isdigit():
        new_data['priority'] = int(options.priority)
    if options.maxdepth is not None:
        if options.maxdepth.isdigit():
            new_data['maxdepth'] = int(options.maxdepth)
        elif options.maxdepth.lower() == "none":
            new_data['maxdepth'] = None
        else:
            error("Invalid maxdepth: %s" % options.maxdepth)
    if options.intransitive:
        new_data['intransitive'] = options.intransitive
    if options.noconfig:
        new_data['noconfig'] = options.noconfig
    if options.pkg_filter:
        new_data['pkg_filter'] = options.pkg_filter

    # find the data we want to edit and replace it
    index = inheritanceData.index(data)
    inheritanceData[index] = new_data
    session.setInheritanceData(tag['id'], inheritanceData)


def handle_remove_tag_inheritance(goptions, session, args):
    """[admin] Remove a tag inheritance link"""
    usage = "usage: %prog remove-tag-inheritance <tag> <parent> <priority>"
    parser = OptionParser(usage=get_usage_str(usage))
    (options, args) = parser.parse_args(args)

    if len(args) < 1:
        parser.error("This command takes at least one argument: a tag name or ID")

    if len(args) > 3:
        parser.error("This command takes at most three argument: a tag name or ID, a parent tag "
                     "name or ID, and a priority")

    activate_session(session, goptions)

    tag = session.getTag(args[0])
    if not tag:
        parser.error("No such tag: %s" % args[0])

    parent = None
    priority = None
    if len(args) > 1:
        parent = session.getTag(args[1])
        if not parent:
            parser.error("No such tag: %s" % args[1])
        if len(args) > 2:
            priority = args[2]

    data = session.getInheritanceData(tag['id'])
    if parent and data:
        data = [datum for datum in data if datum['parent_id'] == parent['id']]
    if priority and data:
        data = [datum for datum in data if datum['priority'] == priority]

    if len(data) == 0:
        error("No inheritance link found to remove.  Please check your arguments")
    elif len(data) > 1:
        print("Multiple matches for tag.")
        if not parent:
            error("Please specify a parent on the command line.")
        if not priority:
            error("Please specify a priority on the command line.")
        error("Error: Key constraints may be broken.  Exiting.")

    # len(data) == 1
    data = data[0]

    inheritanceData = session.getInheritanceData(tag['id'])

    new_data = data.copy()
    new_data['delete link'] = True

    # find the data we want to edit and replace it
    index = inheritanceData.index(data)
    inheritanceData[index] = new_data
    session.setInheritanceData(tag['id'], inheritanceData)


def anon_handle_show_groups(goptions, session, args):
    "[info] Show groups data for a tag"
    usage = "usage: %prog show-groups [options] <tag>"
    parser = OptionParser(usage=get_usage_str(usage))
    parser.add_option("--comps", action="store_true", help="Print in comps format")
    parser.add_option("-x", "--expand", action="store_true", default=False,
                      help="Expand groups in comps format")
    parser.add_option("--spec", action="store_true", help="Print build spec")
    parser.add_option("--show-blocked", action="store_true", dest="incl_blocked",
                      help="Show blocked packages")
    (options, args) = parser.parse_args(args)
    if len(args) != 1:
        parser.error("Incorrect number of arguments")
    if options.incl_blocked and (options.comps or options.spec):
        parser.error("--show-blocked doesn't make sense for comps/spec output")
    ensure_connection(session, goptions)
    tag = args[0]
    callopts = {}
    if options.incl_blocked:
        callopts['incl_blocked'] = True
    groups = session.getTagGroups(tag, **callopts)
    if options.comps:
        print(koji.generate_comps(groups, expand_groups=options.expand))
    elif options.spec:
        print(koji.make_groups_spec(groups, name='buildgroups', buildgroup='build'))
    else:
        pprint.pprint(groups)


def anon_handle_list_external_repos(goptions, session, args):
    "[info] List external repos"
    usage = "usage: %prog list-external-repos [options]"
    parser = OptionParser(usage=get_usage_str(usage))
    parser.add_option("--url", help="Select by url")
    parser.add_option("--name", help="Select by name")
    parser.add_option("--id", type="int", help="Select by id")
    parser.add_option("--tag", help="Select by tag")
    parser.add_option("--used", action='store_true', help="List which tags use the repo(s)")
    parser.add_option("--inherit", action='store_true',
                      help="Follow tag inheritance when selecting by tag")
    parser.add_option("--event", type='int', metavar="EVENT#", help="Query at event")
    parser.add_option("--ts", type='int', metavar="TIMESTAMP",
                      help="Query at last event before timestamp")
    parser.add_option("--repo", type='int', metavar="REPO#",
                      help="Query at event corresponding to (nonexternal) repo")
    parser.add_option("--quiet", action="store_true", default=goptions.quiet,
                      help="Do not display the column headers")
    (options, args) = parser.parse_args(args)
    if len(args) > 0:
        parser.error("This command takes no arguments")
    ensure_connection(session, goptions)
    opts = {}
    event = koji.util.eventFromOpts(session, options)
    if event:
        opts['event'] = event['id']
        event['timestr'] = time.asctime(time.localtime(event['ts']))
        print("Querying at event %(id)i (%(timestr)s)" % event)
    if options.tag:
        format = "tag"
        opts['tag_info'] = options.tag
        opts['repo_info'] = options.id or options.name or None
        if opts['repo_info']:
            if options.inherit:
                parser.error("Can't select by repo when using --inherit")
        if options.inherit:
            del opts['repo_info']
            data = session.getExternalRepoList(**opts)
            format = "multitag"
        else:
            data = session.getTagExternalRepos(**opts)
    elif options.used:
        format = "multitag"
        opts['repo_info'] = options.id or options.name or None
        data = session.getTagExternalRepos(**opts)
    else:
        format = "basic"
        opts['info'] = options.id or options.name or None
        opts['url'] = options.url or None
        data = session.listExternalRepos(**opts)

    # There are three different output formats
    #  1) Listing just repo data (name, url)
    #  2) Listing repo data for a tag (priority, name, url)
    #  3) Listing repo data for multiple tags (tag, priority, name, url)
    if format == "basic":
        format = "%(name)-25s %(url)s"
        header1 = "%-25s %s" % ("External repo name", "URL")
        header2 = "%s %s" % ("-" * 25, "-" * 40)
    elif format == "tag":
        format = "%(priority)-3i %(external_repo_name)-25s %(merge_mode)-10s %(url)s"
        header1 = "%-3s %-25s %-10s URL" % ("Pri", "External repo name", "Mode")
        header2 = "%s %s %s %s" % ("-" * 3, "-" * 25, "-" * 10, "-" * 40)
    elif format == "multitag":
        format = "%(tag_name)-20s %(priority)-3i %(merge_mode)-10s %(external_repo_name)s"
        header1 = "%-20s %-3s %-10s %s" % ("Tag", "Pri", "Mode", "External repo name")
        header2 = "%s %s %s %s" % ("-" * 20, "-" * 3, "-" * 10, "-" * 25)
    if not options.quiet:
        print(header1)
        print(header2)
    for rinfo in data:
        # older hubs do not support merge_mode
        rinfo.setdefault('merge_mode', None)
        print(format % rinfo)


def _pick_external_repo_priority(session, tag):
    """pick priority after current ones, leaving space for later insertions"""
    repolist = session.getTagExternalRepos(tag_info=tag)
    # ordered by priority
    if not repolist:
        priority = 5
    else:
        priority = (repolist[-1]['priority'] + 7) // 5 * 5
        # at least 3 higher than current max and a multiple of 5
    return priority


def _parse_tagpri(tagpri):
    parts = tagpri.rsplit('::', 1)
    tag = parts[0]
    if len(parts) == 1:
        return tag, None
    elif parts[1] in ('auto', '-1'):
        return tag, None
    else:
        try:
            pri = int(parts[1])
        except ValueError:
            raise koji.GenericError("Invalid priority: %s" % parts[1])
        return tag, pri


def handle_add_external_repo(goptions, session, args):
    "[admin] Create an external repo and/or add one to a tag"
    usage = "usage: %prog add-external-repo [options] <name> [<url>]"
    parser = OptionParser(usage=get_usage_str(usage))
    parser.add_option("-t", "--tag", action="append", metavar="TAG",
                      help="Also add repo to tag. Use tag::N to set priority")
    parser.add_option("-p", "--priority", type='int',
                      help="Set priority (when adding to tag)")
    parser.add_option("-m", "--mode", help="Set merge mode")
    parser.add_option("-a", "--arches", metavar="ARCH1,ARCH2, ...",
                      help="Use only subset of arches from given repo")
    (options, args) = parser.parse_args(args)
    activate_session(session, goptions)
    if options.mode:
        if options.mode not in koji.REPO_MERGE_MODES:
            parser.error('Invalid mode: %s' % options.mode)
        if not options.tag:
            parser.error('The --mode option can only be used with --tag')
    if len(args) == 1:
        name = args[0]
        rinfo = session.getExternalRepo(name, strict=True)
        if not options.tag:
            parser.error("A url is required to create an external repo entry")
    elif len(args) == 2:
        name, url = args
        rinfo = session.createExternalRepo(name, url)
        print("Created external repo %(id)i" % rinfo)
    else:
        parser.error("Incorrect number of arguments")
    if options.tag:
        for tagpri in options.tag:
            tag, priority = _parse_tagpri(tagpri)
            if priority is None:
                if options.priority is not None:
                    priority = options.priority
                else:
                    priority = _pick_external_repo_priority(session, tag)
            callopts = {}
            if options.mode:
                callopts['merge_mode'] = options.mode
            if options.arches:
                callopts['arches'] = options.arches
            session.addExternalRepoToTag(tag, rinfo['name'], priority, **callopts)
            print("Added external repo %s to tag %s (priority %i)"
                  % (rinfo['name'], tag, priority))


def handle_edit_external_repo(goptions, session, args):
    "[admin] Edit data for an external repo"
    usage = "usage: %prog edit-external-repo [options] <name>"
    parser = OptionParser(usage=get_usage_str(usage))
    parser.add_option("--url", help="Change the url")
    parser.add_option("--name", help="Change the name")
    parser.add_option("-t", "--tag", metavar="TAG", help="Edit the repo properties for the tag.")
    parser.add_option("-p", "--priority", metavar="PRIORITY", type='int',
                      help="Edit the priority of the repo for the tag specified by --tag.")
    parser.add_option("-m", "--mode", metavar="MODE",
                      help="Edit the merge mode of the repo for the tag specified by --tag. "
                           "Options: %s." % ", ".join(koji.REPO_MERGE_MODES))
    parser.add_option("-a", "--arches", metavar="ARCH1,ARCH2, ...",
                      help="Use only subset of arches from given repo")
    (options, args) = parser.parse_args(args)
    if len(args) != 1:
        parser.error("Incorrect number of arguments")
    repo_opts = {}
    if options.url:
        repo_opts['url'] = options.url
    if options.name:
        repo_opts['name'] = options.name
    tag_repo_opts = {}
    if options.tag:
        if options.priority is not None:
            tag_repo_opts['priority'] = options.priority
        if options.mode:
            tag_repo_opts['merge_mode'] = options.mode
        if options.arches is not None:
            tag_repo_opts['arches'] = options.arches
        if not tag_repo_opts:
            parser.error("At least, one of priority and merge mode should be specified")
        tag_repo_opts['tag_info'] = options.tag
        tag_repo_opts['repo_info'] = args[0]
    else:
        for k in ('priority', 'mode', 'arches'):
            if getattr(options, k) is not None:
                parser.error("If %s is specified, --tag must be specified as well" % k)

    if not (repo_opts or tag_repo_opts):
        parser.error("No changes specified")

    activate_session(session, goptions)
    if repo_opts:
        session.editExternalRepo(args[0], **repo_opts)
    if tag_repo_opts:
        session.editTagExternalRepo(**tag_repo_opts)


def handle_remove_external_repo(goptions, session, args):
    "[admin] Remove an external repo from a tag or tags, or remove entirely"
    usage = "usage: %prog remove-external-repo <repo> [<tag> ...]"
    parser = OptionParser(usage=get_usage_str(usage))
    parser.add_option("--alltags", action="store_true", help="Remove from all tags")
    parser.add_option("--force", action='store_true', help="Force action")
    (options, args) = parser.parse_args(args)
    if len(args) < 1:
        parser.error("Incorrect number of arguments")
    activate_session(session, goptions)
    repo = args[0]
    tags = args[1:]
    delete = not bool(tags)
    data = session.getTagExternalRepos(repo_info=repo)
    current_tags = [d['tag_name'] for d in data]
    if options.alltags:
        delete = False
        if tags:
            parser.error("Do not specify tags when using --alltags")
        if not current_tags:
            if options.force:
                delete = True
            else:
                warn("External repo %s not associated with any tags" % repo)
                return 0
        tags = current_tags
    if delete:
        # removing entirely
        if current_tags and not options.force:
            warn("Error: external repo %s used by tag(s): %s" % (repo, ', '.join(current_tags)))
            error("Use --force to remove anyway")
        session.deleteExternalRepo(args[0])
    else:
        for tag in tags:
            if tag not in current_tags:
                print("External repo %s not associated with tag %s" % (repo, tag))
                continue
            session.removeExternalRepoFromTag(tag, repo)


# This handler is for spinning livecd images
#
def handle_spin_livecd(options, session, args):
    """[build] Create a live CD image given a kickstart file"""

    # Usage & option parsing.
    usage = "usage: %prog spin-livecd [options] <name> <version> <target> <arch> <kickstart-file>"
    parser = OptionParser(usage=get_usage_str(usage))
    parser.add_option("--wait", action="store_true",
                      help="Wait on the livecd creation, even if running in the background")
    parser.add_option("--nowait", action="store_false", dest="wait",
                      help="Don't wait on livecd creation")
    parser.add_option("--noprogress", action="store_true",
                      help="Do not display progress of the upload")
    parser.add_option("--background", action="store_true",
                      help="Run the livecd creation task at a lower priority")
    parser.add_option("--ksurl", metavar="SCMURL",
                      help="The URL to the SCM containing the kickstart file")
    parser.add_option("--ksversion", metavar="VERSION",
                      help="The syntax version used in the kickstart file")
    parser.add_option("--scratch", action="store_true",
                      help="Create a scratch LiveCD image")
    parser.add_option("--repo", action="append",
                      help="Specify a repo that will override the repo used to install "
                           "RPMs in the LiveCD. May be used multiple times. The "
                           "build tag repo associated with the target is the default.")
    parser.add_option("--release", help="Forcibly set the release field")
    parser.add_option("--volid", help="Set the volume id")
    parser.add_option("--specfile", metavar="URL",
                      help="SCM URL to spec file fragment to use to generate wrapper RPMs")
    parser.add_option("--skip-tag", action="store_true",
                      help="Do not attempt to tag package")
    (task_options, args) = parser.parse_args(args)

    # Make sure the target and kickstart is specified.
    print('spin-livecd is deprecated and will be replaced with spin-livemedia')
    if len(args) != 5:
        parser.error("Five arguments are required: a name, a version, an architecture, "
                     "a build target, and a relative path to a kickstart file.")
    if task_options.volid is not None and len(task_options.volid) > 32:
        parser.error('Volume ID has a maximum length of 32 characters')
    return _build_image(options, task_options, session, args, 'livecd')


# This handler is for spinning livemedia images
def handle_spin_livemedia(options, session, args):
    """[build] Create a livemedia image given a kickstart file"""

    # Usage & option parsing.
    usage = "usage: %prog spin-livemedia [options] <name> <version> <target> <arch> " \
            "<kickstart-file>"
    parser = OptionParser(usage=get_usage_str(usage))
    parser.add_option("--wait", action="store_true",
                      help="Wait on the livemedia creation, even if running in the background")
    parser.add_option("--nowait", action="store_false", dest="wait",
                      help="Don't wait on livemedia creation")
    parser.add_option("--noprogress", action="store_true",
                      help="Do not display progress of the upload")
    parser.add_option("--background", action="store_true",
                      help="Run the livemedia creation task at a lower priority")
    parser.add_option("--ksurl", metavar="SCMURL",
                      help="The URL to the SCM containing the kickstart file")
    parser.add_option("--install-tree-url", metavar="URL",
                      help="Provide the URL for the install tree")
    parser.add_option("--ksversion", metavar="VERSION",
                      help="The syntax version used in the kickstart file")
    parser.add_option("--scratch", action="store_true",
                      help="Create a scratch LiveMedia image")
    parser.add_option("--repo", action="append",
                      help="Specify a repo that will override the repo used to install "
                           "RPMs in the LiveMedia. May be used multiple times. The "
                           "build tag repo associated with the target is the default.")
    parser.add_option("--release", help="Forcibly set the release field")
    parser.add_option("--volid", help="Set the volume id")
    parser.add_option("--specfile", metavar="URL",
                      help="SCM URL to spec file fragment to use to generate wrapper RPMs")
    parser.add_option("--skip-tag", action="store_true", help="Do not attempt to tag package")
    parser.add_option("--can-fail", action="store", dest="optional_arches",
                      metavar="ARCH1,ARCH2,...", default="",
                      help="List of archs which are not blocking for build (separated by commas.")
    parser.add_option('--lorax_dir', metavar='DIR',
                      help='The relative path to the lorax templates '
                           'directory within the checkout of "lorax_url".')
    parser.add_option('--lorax_url', metavar='URL',
                      help='The URL to the SCM containing any custom lorax templates that are '
                           'to be used to override the default templates.')
    parser.add_option('--nomacboot', action="store_true",
                      help="Pass the nomacboot option to livemedia-creator")
    parser.add_option('--ksrepo', action="store_true",
                      help="Do not overwrite repos in the kickstart")
    parser.add_option('--squashfs-only', action="store_true",
                      help="Use a plain squashfs filesystem.")
    parser.add_option('--compress-arg', action="append", default=[], metavar="ARG OPT",
                      help="List of compressions.")
    (task_options, args) = parser.parse_args(args)

    # Make sure the target and kickstart is specified.
    if len(args) != 5:
        parser.error("Five arguments are required: a name, a version, a build target, "
                     "an architecture, and a relative path to a kickstart file.")
    if task_options.lorax_url is not None and task_options.lorax_dir is None:
        parser.error('The "--lorax_url" option requires that "--lorax_dir" also be used.')
    if task_options.volid is not None and len(task_options.volid) > 32:
        parser.error('Volume ID has a maximum length of 32 characters')
    return _build_image(options, task_options, session, args, 'livemedia')


# This handler is for spinning appliance images
#
def handle_spin_appliance(options, session, args):
    """[build] Create an appliance given a kickstart file"""

    # Usage & option parsing
    usage = "usage: %prog spin-appliance [options] <name> <version> <target> <arch> " \
            "<kickstart-file>"
    parser = OptionParser(usage=get_usage_str(usage))
    parser.add_option("--wait", action="store_true",
                      help="Wait on the appliance creation, even if running in the background")
    parser.add_option("--nowait", action="store_false", dest="wait",
                      help="Don't wait on appliance creation")
    parser.add_option("--noprogress", action="store_true",
                      help="Do not display progress of the upload")
    parser.add_option("--background", action="store_true",
                      help="Run the appliance creation task at a lower priority")
    parser.add_option("--ksurl", metavar="SCMURL",
                      help="The URL to the SCM containing the kickstart file")
    parser.add_option("--ksversion", metavar="VERSION",
                      help="The syntax version used in the kickstart file")
    parser.add_option("--scratch", action="store_true", help="Create a scratch appliance")
    parser.add_option("--repo", action="append",
                      help="Specify a repo that will override the repo used to install "
                           "RPMs in the appliance. May be used multiple times. The "
                           "build tag repo associated with the target is the default.")
    parser.add_option("--release", help="Forcibly set the release field")
    parser.add_option("--specfile", metavar="URL",
                      help="SCM URL to spec file fragment to use to generate wrapper RPMs")
    parser.add_option("--skip-tag", action="store_true", help="Do not attempt to tag package")
    parser.add_option("--vmem", metavar="VMEM", default=None,
                      help="Set the amount of virtual memory in the appliance in MB, "
                           "default is 512")
    parser.add_option("--vcpu", metavar="VCPU", default=None,
                      help="Set the number of virtual cpus in the appliance, default is 1")
    parser.add_option("--format", metavar="DISK_FORMAT", default='raw',
                      help="Disk format, default is raw. Other options are qcow, qcow2, and vmx.")

    (task_options, args) = parser.parse_args(args)

    # Make sure the target and kickstart is specified.
    print('spin-appliance is deprecated and will be replaced with image-build')
    if len(args) != 5:
        parser.error("Five arguments are required: a name, a version, an architecture, "
                     "a build target, and a relative path to a kickstart file.")
    return _build_image(options, task_options, session, args, 'appliance')


def handle_image_build_indirection(options, session, args):
    """[build] Create a disk image using other disk images via the Indirection plugin"""
    usage = "usage: %prog image-build-indirection [base_image] [utility_image] " \
            "[indirection_build_template]"
    usage += "\n       %prog image-build --config <FILE>\n"
    parser = OptionParser(usage=get_usage_str(usage))
    parser.add_option("--config",
                      help="Use a configuration file to define image-build options "
                           "instead of command line options (they will be ignored).")
    parser.add_option("--background", action="store_true",
                      help="Run the image creation task at a lower priority")
    parser.add_option("--name", help="Name of the output image")
    parser.add_option("--version", help="Version of the output image")
    parser.add_option("--release", help="Release of the output image")
    parser.add_option("--arch", help="Architecture of the output image and input images")
    parser.add_option("--target", help="Build target to use for the indirection build")
    parser.add_option("--skip-tag", action="store_true", help="Do not tag the resulting build")
    parser.add_option("--base-image-task",
                      help="ID of the createImage task of the base image to be used")
    parser.add_option("--base-image-build", help="NVR or build ID of the base image to be used")
    parser.add_option("--utility-image-task",
                      help="ID of the createImage task of the utility image to be used")
    parser.add_option("--utility-image-build",
                      help="NVR or build ID of the utility image to be used")
    parser.add_option("--indirection-template",
                      help="Name of the local file, or SCM file containing the template used to "
                           "drive the indirection plugin")
    parser.add_option("--indirection-template-url",
                      help="SCM URL containing the template used to drive the indirection plugin")
    parser.add_option("--results-loc",
                      help="Relative path inside the working space image where the results "
                           "should be extracted from")
    parser.add_option("--scratch", action="store_true", help="Create a scratch image")
    parser.add_option("--wait", action="store_true",
                      help="Wait on the image creation, even if running in the background")
    parser.add_option("--nowait", action="store_false", dest="wait",
                      help="Do not wait on the image creation")
    parser.add_option("--noprogress", action="store_true",
                      help="Do not display progress of the upload")

    (task_options, args) = parser.parse_args(args)
    if task_options.config:
        section = 'image-build-indirection'
        config = koji.read_config_files([(task_options.config, True)])
        if not config.has_section(section):
            parser.error("single section called [%s] is required" % section)

        # We avoid manually listing options
        parser_options = [opt.dest for opt in parser.option_list]
        parser_options.remove(None)  # --help has a dest of None, remove it to avoid errors
        for opt in parser_options:
            if not config.has_option(section, opt):
                continue

            setattr(task_options, opt, config.get(section, opt))

    _build_image_indirection(options, task_options, session, args)


def _build_image_indirection(options, task_opts, session, args):
    """
    A private helper function for builds using the indirection plugin of ImageFactory
    """

    # Do some sanity checks before even attempting to create the session
    if not (bool(task_opts.utility_image_task) !=
            bool(task_opts.utility_image_build)):
        raise koji.GenericError("You must specify either a utility-image task or build ID/NVR")

    if not (bool(task_opts.base_image_task) !=
            bool(task_opts.base_image_build)):
        raise koji.GenericError("You must specify either a base-image task or build ID/NVR")

    required_opts = ['name', 'version', 'arch', 'target', 'indirection_template', 'results_loc']
    optional_opts = ['indirection_template_url', 'scratch', 'utility_image_task',
                     'utility_image_build', 'base_image_task', 'base_image_build', 'release',
                     'skip_tag']

    missing = []
    for opt in required_opts:
        if not getattr(task_opts, opt, None):
            missing.append(opt)

    if len(missing) > 0:
        print("Missing the following required options: %s" %
              ' '.join(['--%s' % o.replace('_', '-') for o in missing]))
        raise koji.GenericError("Missing required options specified above")

    activate_session(session, options)

    # Set the task's priority. Users can only lower it with --background.
    priority = None
    if task_opts.background:
        # relative to koji.PRIO_DEFAULT; higher means a "lower" priority.
        priority = 5
    if _running_in_bg() or task_opts.noprogress:
        callback = None
    else:
        callback = _progress_callback

    # We do some early sanity checking of the given target.
    # Kojid gets these values again later on, but we check now as a convenience
    # for the user.

    tmp_target = session.getBuildTarget(task_opts.target)
    if not tmp_target:
        raise koji.GenericError("No such build target: %s" % tmp_target)
    dest_tag = session.getTag(tmp_target['dest_tag'])
    if not dest_tag:
        raise koji.GenericError("No such destination tag: %s" % tmp_target['dest_tag_name'])

    # Set the architecture
    task_opts.arch = koji.canonArch(task_opts.arch)

    # Upload the indirection template file to the staging area.
    # If it's a URL, it's kojid's job to go get it when it does the checkout.
    if not task_opts.indirection_template_url:
        if not task_opts.scratch:
            # only scratch builds can omit indirection_template_url
            raise koji.GenericError(
                "Non-scratch builds must provide a URL for the indirection template")
        templatefile = task_opts.indirection_template
        serverdir = unique_path('cli-image-indirection')
        session.uploadWrapper(templatefile, serverdir, callback=callback)
        task_opts.indirection_template = os.path.join('work', serverdir,
                                                      os.path.basename(templatefile))
        print('')

    hub_opts = {}
    # Just pass everything in as opts.  No posiitonal arguments at all.  Why not?
    for opt in required_opts + optional_opts:
        val = getattr(task_opts, opt, None)
        # We pass these through even if they are None
        # The builder code can then check if they are set without using getattr
        hub_opts[opt] = val

    # finally, create the task.
    task_id = session.buildImageIndirection(opts=hub_opts,
                                            priority=priority)

    if not options.quiet:
        print("Created task: %d" % task_id)
        print("Task info: %s/taskinfo?taskID=%s" % (options.weburl, task_id))
    if task_opts.wait or (task_opts.wait is None and not _running_in_bg()):
        session.logout()
        return watch_tasks(session, [task_id], quiet=options.quiet, topurl=options.topurl)


def handle_image_build(options, session, args):
    """[build] Create a disk image given an install tree"""
    formats = ('vmdk', 'qcow', 'qcow2', 'vdi', 'vpc', 'rhevm-ova',
               'vsphere-ova', 'vagrant-virtualbox', 'vagrant-libvirt',
               'vagrant-vmware-fusion', 'vagrant-hyperv', 'docker', 'raw-xz',
               'liveimg-squashfs', 'tar-gz')
    usage = "usage: %prog image-build [options] <name> <version> <target> " \
            "<install-tree-url> <arch> [<arch> ...]"
    usage += "\n       %prog image-build --config <FILE>\n"
    parser = OptionParser(usage=get_usage_str(usage))
    parser.add_option("--background", action="store_true",
                      help="Run the image creation task at a lower priority")
    parser.add_option("--config",
                      help="Use a configuration file to define image-build options "
                           "instead of command line options (they will be ignored).")
    parser.add_option("--disk-size", default=10, help="Set the disk device size in gigabytes")
    parser.add_option("--distro",
                      help="specify the RPM based distribution the image will be based "
                           "on with the format RHEL-X.Y, CentOS-X.Y, SL-X.Y, or Fedora-NN. "
                           "The packages for the Distro you choose must have been built "
                           "in this system.")
    parser.add_option("--format", default=[], action="append",
                      help="Convert results to one or more formats "
                           "(%s), this option may be used "
                           "multiple times. By default, specifying this option will "
                           "omit the raw disk image (which is 10G in size) from the "
                           "build results. If you really want it included with converted "
                           "images, pass in 'raw' as an option." % ', '.join(formats))
    parser.add_option("--kickstart", help="Path to a local kickstart file")
    parser.add_option("--ksurl", metavar="SCMURL",
                      help="The URL to the SCM containing the kickstart file")
    parser.add_option("--ksversion", metavar="VERSION",
                      help="The syntax version used in the kickstart file")
    parser.add_option("--noprogress", action="store_true",
                      help="Do not display progress of the upload")
    parser.add_option("--noverifyssl", action="store_true",
                      help="Use the noverifyssl option for the install tree and all repos. "
                           "This option is only allowed if enabled on the builder.")
    parser.add_option("--nowait", action="store_false", dest="wait",
                      help="Don't wait on image creation")
    parser.add_option("--ova-option", action="append",
                      help="Override a value in the OVA description XML. Provide a value "
                           "in a name=value format, such as 'ovf_memory_mb=6144'")
    parser.add_option("--factory-parameter", nargs=2, action="append",
                      help="Pass a parameter to Image Factory. The results are highly specific "
                           "to the image format being created. This is a two argument parameter "
                           "that can be specified an arbitrary number of times. For example: "
                           "--factory-parameter docker_cmd '[ \"/bin/echo Hello World\" ]'")
    parser.add_option("--release", help="Forcibly set the release field")
    parser.add_option("--repo", action="append",
                      help="Specify a repo that will override the repo used to install "
                           "RPMs in the image. May be used multiple times. The "
                           "build tag repo associated with the target is the default.")
    parser.add_option("--scratch", action="store_true", help="Create a scratch image")
    parser.add_option("--skip-tag", action="store_true", help="Do not attempt to tag package")
    parser.add_option("--can-fail", action="store", dest="optional_arches",
                      metavar="ARCH1,ARCH2,...", default="",
                      help="List of archs which are not blocking for build (separated by commas.")
    parser.add_option("--specfile", metavar="URL",
                      help="SCM URL to spec file fragment to use to generate wrapper RPMs")
    parser.add_option("--wait", action="store_true",
                      help="Wait on the image creation, even if running in the background")

    (task_options, args) = parser.parse_args(args)

    if task_options.config:
        section = 'image-build'
        config = koji.read_config_files([(task_options.config, True)])
        if not config.has_section(section):
            parser.error("single section called [%s] is required" % section)
        # pluck out the positional arguments first
        args = []
        for arg in ('name', 'version', 'target', 'install_tree'):
            args.append(config.get(section, arg))
            config.remove_option(section, arg)
        args.extend(config.get(section, 'arches').split(','))
        config.remove_option(section, 'arches')
        # turn comma-separated options into lists
        for arg in ('repo', 'format'):
            if config.has_option(section, arg):
                setattr(task_options, arg, config.get(section, arg).split(','))
                config.remove_option(section, arg)
        if config.has_option(section, 'can_fail'):
            setattr(task_options, 'optional_arches', config.get(section, 'can_fail').split(','))
            config.remove_option(section, 'can_fail')
        # handle everything else
        for k, v in config.items(section):
            setattr(task_options, k, v)

        # ova-options belong in their own section
        section = 'ova-options'
        if config.has_section(section):
            task_options.ova_option = []
            for k, v in config.items(section):
                task_options.ova_option.append('%s=%s' % (k, v))

        # as do factory-parameters
        section = 'factory-parameters'
        if config.has_section(section):
            task_options.factory_parameter = []
            for k, v in config.items(section):
                # We do this, rather than a dict, to match what argparse spits out
                task_options.factory_parameter.append((k, v))

    else:
        if len(args) < 5:
            parser.error("At least five arguments are required: a name, a version, "
                         "a build target, a URL to an install tree, and 1 or more architectures.")
    if not task_options.ksurl and not task_options.kickstart:
        parser.error('You must specify --kickstart')
    if not task_options.distro:
        parser.error(
            "You must specify --distro. Examples: Fedora-16, RHEL-6.4, SL-6.4 or CentOS-6.4")
    return _build_image_oz(options, task_options, session, args)


def _build_image(options, task_opts, session, args, img_type):
    """
    A private helper function that houses common CLI code for building
    images with chroot-based tools.
    """

    if img_type not in ('livecd', 'appliance', 'livemedia'):
        raise koji.GenericError('Unrecognized image type: %s' % img_type)
    activate_session(session, options)

    # Set the task's priority. Users can only lower it with --background.
    priority = None
    if task_opts.background:
        # relative to koji.PRIO_DEFAULT; higher means a "lower" priority.
        priority = 5
    if _running_in_bg() or task_opts.noprogress:
        callback = None
    else:
        callback = _progress_callback

    # We do some early sanity checking of the given target.
    # Kojid gets these values again later on, but we check now as a convenience
    # for the user.
    target = args[2]
    tmp_target = session.getBuildTarget(target)
    if not tmp_target:
        raise koji.GenericError("No such build target: %s" % target)
    dest_tag = session.getTag(tmp_target['dest_tag'])
    if not dest_tag:
        raise koji.GenericError("No such destination tag: %s" % tmp_target['dest_tag_name'])

    # Set the architecture
    if img_type == 'livemedia':
        # livemedia accepts multiple arches
        arch = [koji.canonArch(a) for a in args[3].split(",")]
    else:
        arch = koji.canonArch(args[3])

    # Upload the KS file to the staging area.
    # If it's a URL, it's kojid's job to go get it when it does the checkout.
    ksfile = args[4]

    if not task_opts.ksurl:
        serverdir = unique_path('cli-' + img_type)
        session.uploadWrapper(ksfile, serverdir, callback=callback)
        ksfile = os.path.join(serverdir, os.path.basename(ksfile))
        print('')

    hub_opts = {}
    passthru_opts = [
        'format', 'install_tree_url', 'isoname', 'ksurl',
        'ksversion', 'release', 'repo', 'scratch', 'skip_tag',
        'specfile', 'vcpu', 'vmem', 'volid', 'optional_arches',
        'lorax_dir', 'lorax_url', 'nomacboot', 'ksrepo',
        'squashfs_only', 'compress_arg',
    ]
    for opt in passthru_opts:
        val = getattr(task_opts, opt, None)
        if val is not None:
            hub_opts[opt] = val

    if 'optional_arches' in hub_opts:
        hub_opts['optional_arches'] = hub_opts['optional_arches'].split(',')
    # finally, create the task.
    task_id = session.buildImage(args[0], args[1], arch, target, ksfile,
                                 img_type, opts=hub_opts, priority=priority)

    if not options.quiet:
        print("Created task: %d" % task_id)
        print("Task info: %s/taskinfo?taskID=%s" % (options.weburl, task_id))
    if task_opts.wait or (task_opts.wait is None and not _running_in_bg()):
        session.logout()
        return watch_tasks(session, [task_id], quiet=options.quiet,
                           poll_interval=options.poll_interval, topurl=options.topurl)


def _build_image_oz(options, task_opts, session, args):
    """
    A private helper function that houses common CLI code for building
    images with Oz and ImageFactory
    """
    activate_session(session, options)

    # Set the task's priority. Users can only lower it with --background.
    priority = None
    if task_opts.background:
        # relative to koji.PRIO_DEFAULT; higher means a "lower" priority.
        priority = 5
    if _running_in_bg() or task_opts.noprogress:
        callback = None
    else:
        callback = _progress_callback

    # We do some early sanity checking of the given target.
    # Kojid gets these values again later on, but we check now as a convenience
    # for the user.
    target = args[2]
    tmp_target = session.getBuildTarget(target)
    if not tmp_target:
        raise koji.GenericError("No such build target: %s" % target)
    dest_tag = session.getTag(tmp_target['dest_tag'])
    if not dest_tag:
        raise koji.GenericError("No such destination tag: %s" % tmp_target['dest_tag_name'])

    # Set the architectures
    arches = []
    for arch in args[4:]:
        arches.append(koji.canonArch(arch))

    # Upload the KS file to the staging area.
    # If it's a URL, it's kojid's job to go get it when it does the checkout.
    if not task_opts.ksurl:
        ksfile = task_opts.kickstart
        serverdir = unique_path('cli-image')
        session.uploadWrapper(ksfile, serverdir, callback=callback)
        task_opts.kickstart = os.path.join('work', serverdir,
                                           os.path.basename(ksfile))
        print('')

    hub_opts = {}
    for opt in ('ksurl', 'ksversion', 'kickstart', 'scratch', 'repo',
                'release', 'skip_tag', 'specfile', 'distro', 'format',
                'disk_size', 'ova_option', 'factory_parameter',
                'optional_arches', 'noverifyssl'):
        val = getattr(task_opts, opt, None)
        if val is not None:
            hub_opts[opt] = val
    # finally, create the task.
    task_id = session.buildImageOz(args[0], args[1], arches, target, args[3],
                                   opts=hub_opts, priority=priority)

    if not options.quiet:
        print("Created task: %d" % task_id)
        print("Task info: %s/taskinfo?taskID=%s" % (options.weburl, task_id))
    if task_opts.wait or (task_opts.wait is None and not _running_in_bg()):
        session.logout()
        return watch_tasks(session, [task_id], quiet=options.quiet,
                           poll_interval=options.poll_interval, topurl=options.topurl)


def handle_win_build(options, session, args):
    """[build] Build a Windows package from source"""
    # Usage & option parsing
    usage = "usage: %prog win-build [options] <target> <URL> <VM>"
    parser = OptionParser(usage=get_usage_str(usage))
    parser.add_option("--winspec", metavar="URL",
                      help="SCM URL to retrieve the build descriptor from. "
                           "If not specified, the winspec must be in the root directory "
                           "of the source repository.")
    parser.add_option("--patches", metavar="URL",
                      help="SCM URL of a directory containing patches to apply "
                           "to the sources before building")
    parser.add_option("--cpus", type="int",
                      help="Number of cpus to allocate to the build VM "
                           "(requires admin access)")
    parser.add_option("--mem", type="int",
                      help="Amount of memory (in megabytes) to allocate to the build VM "
                           "(requires admin access)")
    parser.add_option("--static-mac", action="store_true",
                      help="Retain the original MAC address when cloning the VM")
    parser.add_option("--specfile", metavar="URL",
                      help="SCM URL of a spec file fragment to use to generate wrapper RPMs")
    parser.add_option("--scratch", action="store_true",
                      help="Perform a scratch build")
    parser.add_option("--repo-id", type="int", help="Use a specific repo")
    parser.add_option("--skip-tag", action="store_true", help="Do not attempt to tag package")
    parser.add_option("--background", action="store_true",
                      help="Run the build at a lower priority")
    parser.add_option("--wait", action="store_true",
                      help="Wait on the build, even if running in the background")
    parser.add_option("--nowait", action="store_false", dest="wait", help="Don't wait on build")
    parser.add_option("--quiet", action="store_true",
                      help="Do not print the task information", default=options.quiet)
    (build_opts, args) = parser.parse_args(args)
    if len(args) != 3:
        parser.error(
            "Exactly three arguments (a build target, a SCM URL, and a VM name) are required")
    activate_session(session, options)
    target = args[0]
    if target.lower() == "none" and build_opts.repo_id:
        target = None
        build_opts.skip_tag = True
    else:
        build_target = session.getBuildTarget(target)
        if not build_target:
            parser.error("No such build target: %s" % target)
        dest_tag = session.getTag(build_target['dest_tag'])
        if not dest_tag:
            parser.error("No such destination tag: %s" % build_target['dest_tag_name'])
        if dest_tag['locked'] and not build_opts.scratch:
            parser.error("Destination tag %s is locked" % dest_tag['name'])
    scmurl = args[1]
    vm_name = args[2]
    opts = {}
    for key in ('winspec', 'patches', 'cpus', 'mem', 'static_mac',
                'specfile', 'scratch', 'repo_id', 'skip_tag'):
        val = getattr(build_opts, key)
        if val is not None:
            opts[key] = val
    priority = None
    if build_opts.background:
        # relative to koji.PRIO_DEFAULT
        priority = 5
    task_id = session.winBuild(vm_name, scmurl, target, opts, priority=priority)
    if not build_opts.quiet:
        print("Created task: %d" % task_id)
        print("Task info: %s/taskinfo?taskID=%s" % (options.weburl, task_id))
    if build_opts.wait or (build_opts.wait is None and not _running_in_bg()):
        session.logout()
        return watch_tasks(session, [task_id], quiet=build_opts.quiet,
                           poll_interval=options.poll_interval, topurl=options.topurl)


def handle_free_task(goptions, session, args):
    "[admin] Free a task"
    usage = "usage: %prog free-task [options] <task_id> [<task_id> ...]"
    parser = OptionParser(usage=get_usage_str(usage))
    (options, args) = parser.parse_args(args)
    activate_session(session, goptions)
    tlist = []
    for task_id in args:
        try:
            tlist.append(int(task_id))
        except ValueError:
            parser.error("task_id must be an integer")
    if not tlist:
        parser.error("please specify at least one task_id")
    for task_id in tlist:
        session.freeTask(task_id)


def handle_cancel(goptions, session, args):
    "[build] Cancel tasks and/or builds"
    usage = "usage: %prog cancel [options] <task_id|build> [<task_id|build> ...]"
    parser = OptionParser(usage=get_usage_str(usage))
    parser.add_option("--justone", action="store_true", help="Do not cancel subtasks")
    parser.add_option("--full", action="store_true", help="Full cancellation (admin only)")
    parser.add_option("--force", action="store_true", help="Allow subtasks with --full")
    (options, args) = parser.parse_args(args)
    if len(args) == 0:
        parser.error("You must specify at least one task id or build")
    activate_session(session, goptions)
    tlist = []
    blist = []
    for arg in args:
        try:
            tlist.append(int(arg))
        except ValueError:
            try:
                koji.parse_NVR(arg)
                blist.append(arg)
            except koji.GenericError:
                parser.error("please specify only task ids (integer) or builds (n-v-r)")

    results = []
    with session.multicall(strict=False, batch=100) as m:
        if tlist:
            opts = {}
            remote_fn = m.cancelTask
            if options.justone:
                opts['recurse'] = False
            elif options.full:
                remote_fn = m.cancelTaskFull
                if options.force:
                    opts['strict'] = False
            for task_id in tlist:
                results.append(remote_fn(task_id, **opts))
        for build in blist:
            if session.hub_version >= (1, 33, 0):
                results.append(m.cancelBuild(build, strict=True))
            else:
                results.append(m.cancelBuild(build))

    err = False
    for r in results:
        if isinstance(r._result, dict):
            warn(r._result['faultString'])
            err = True
    if err:
        return 1


def handle_set_task_priority(goptions, session, args):
    "[admin] Set task priority"
    usage = "usage: %prog set-task-priority [options] --priority=<priority> <task_id> " \
            "[<task_id> ...]"
    parser = OptionParser(usage=get_usage_str(usage))
    parser.add_option("--priority", type="int", help="New priority")
    parser.add_option("--recurse", action="store_true", default=False,
                      help="Change priority of child tasks as well")
    (options, args) = parser.parse_args(args)
    if len(args) == 0:
        parser.error("You must specify at least one task id")

    if options.priority is None:
        parser.error("You must specify --priority")
    try:
        tasks = [int(a) for a in args]
    except ValueError:
        parser.error("Task numbers must be integers")

    activate_session(session, goptions)

    if not session.hasPerm('admin'):
        logged_user = session.getLoggedInUser()
        error("admin permission required (logged in as %s)" % logged_user['name'])

    for task_id in tasks:
        try:
            session.setTaskPriority(task_id, options.priority, options.recurse)
        except koji.GenericError:
            warn("Can't update task priority on closed task: %s" % task_id)


def handle_list_tasks(goptions, session, args):
    "[info] Print the list of tasks"
    usage = "usage: %prog list-tasks [options]"
    parser = OptionParser(usage=get_usage_str(usage), option_class=TimeOption)
    parser.add_option("--mine", action="store_true", help="Just print your tasks")
    parser.add_option("--user", help="Only tasks for this user")
    parser.add_option("--arch", help="Only tasks for this architecture")
    parser.add_option("--method", help="Only tasks of this method")
    parser.add_option("--channel", help="Only tasks in this channel")
    parser.add_option("--host", help="Only tasks for this host")
    parser.add_option("--quiet", action="store_true", default=goptions.quiet,
                      help="Do not display the column headers")
    parser.add_option("--before", type="time",
                      help="List tasks completed before this time, " + TimeOption.get_help())
    parser.add_option("--after", type="time",
                      help="List tasks completed after this time (same format as for --before")
    parser.add_option("--all", action="store_true",
                      help="List also finished tasks (valid only with --after)")
    (options, args) = parser.parse_args(args)
    if len(args) != 0:
        parser.error("This command takes no arguments")

    if options.all and not options.after:
        parser.error("--all must be used with --after")

    activate_session(session, goptions)
    tasklist = _list_tasks(options, session)
    if not tasklist:
        print("(no tasks)")
        return
    if not options.quiet:
        print_task_headers()
    for t in tasklist:
        if t.get('sub'):
            # this subtask will appear under another task
            continue
        print_task_recurse(t)


def handle_set_pkg_arches(goptions, session, args):
    "[admin] Set the list of extra arches for a package"
    usage = "usage: %prog set-pkg-arches [options] <arches> <tag> <package> [<package> ...]"
    parser = OptionParser(usage=get_usage_str(usage))
    parser.add_option("--force", action='store_true', help="Force operation")
    (options, args) = parser.parse_args(args)
    if len(args) < 3:
        parser.error("Please specify an archlist, a tag, and at least one package")
    activate_session(session, goptions)
    arches = koji.parse_arches(args[0])
    tag = args[1]
    with session.multicall(strict=True) as m:
        for package in args[2:]:
            m.packageListSetArches(tag, package, arches, force=options.force)


def handle_set_pkg_owner(goptions, session, args):
    "[admin] Set the owner for a package"
    usage = "usage: %prog set-pkg-owner [options] <owner> <tag> <package> [<package> ...]"
    parser = OptionParser(usage=get_usage_str(usage))
    parser.add_option("--force", action='store_true', help="Force operation")
    (options, args) = parser.parse_args(args)
    if len(args) < 3:
        parser.error("Please specify an owner, a tag, and at least one package")
    activate_session(session, goptions)
    owner = args[0]
    tag = args[1]
    with session.multicall(strict=True) as m:
        for package in args[2:]:
            m.packageListSetOwner(tag, package, owner, force=options.force)


def handle_set_pkg_owner_global(goptions, session, args):
    "[admin] Set the owner for a package globally"
    usage = "usage: %prog set-pkg-owner-global [options] <owner> <package> [<package> ...]"
    parser = OptionParser(usage=get_usage_str(usage))
    parser.add_option("--verbose", action='store_true', help="List changes")
    parser.add_option("--test", action='store_true', help="Test mode")
    parser.add_option("--old-user", "--from", action="store",
                      help="Only change ownership for packages belonging to this user")
    (options, args) = parser.parse_args(args)
    if options.old_user:
        if len(args) < 1:
            parser.error("Please specify an owner")
    elif len(args) < 2:
        parser.error("Please specify an owner and at least one package")
    activate_session(session, goptions)
    owner = args[0]
    packages = args[1:]
    user = session.getUser(owner)
    if not user:
        error("No such user: %s" % owner)
    opts = {'with_dups': True}
    old_user = None
    if options.old_user:
        old_user = session.getUser(options.old_user)
        if not old_user:
            error("No such user: %s" % options.old_user)
        opts['userID'] = old_user['id']
    to_change = []
    for package in packages:
        entries = session.listPackages(pkgID=package, **opts)
        if not entries:
            print("No data for package %s" % package)
            continue
        to_change.extend(entries)
    if not packages and options.old_user:
        entries = session.listPackages(**opts)
        if not entries:
            error("No data for user %s" % old_user['name'])
        to_change.extend(entries)
    for entry in to_change:
        if user['id'] == entry['owner_id']:
            if options.verbose:
                print("Preserving owner=%s for package %s in tag %s"
                      % (user['name'], package, entry['tag_name']))
        else:
            if options.test:
                print("Would have changed owner for %s in tag %s: %s -> %s"
                      % (entry['package_name'], entry['tag_name'], entry['owner_name'],
                         user['name']))
                continue
            if options.verbose:
                print("Changing owner for %s in tag %s: %s -> %s"
                      % (entry['package_name'], entry['tag_name'], entry['owner_name'],
                         user['name']))
            session.packageListSetOwner(entry['tag_id'], entry['package_name'], user['id'])


def anon_handle_watch_task(goptions, session, args):
    "[monitor] Track progress of particular tasks"
    usage = "usage: %prog watch-task [options] <task id> [<task id> ...]"
    parser = OptionParser(usage=get_usage_str(usage))
    parser.add_option("--quiet", action="store_true", default=goptions.quiet,
                      help="Do not print the task information")
    parser.add_option("--mine", action="store_true", help="Just watch your tasks")
    parser.add_option("--user", help="Only tasks for this user")
    parser.add_option("--arch", help="Only tasks for this architecture")
    parser.add_option("--method", help="Only tasks of this method")
    parser.add_option("--channel", help="Only tasks in this channel")
    parser.add_option("--host", help="Only tasks for this host")
    (options, args) = parser.parse_args(args)
    selection = (options.mine or
                 options.user or
                 options.arch or
                 options.method or
                 options.channel or
                 options.host)
    if args and selection:
        parser.error("Selection options cannot be combined with a task list")

    if options.mine:
        activate_session(session, goptions)
    else:
        ensure_connection(session, goptions)
    if selection:
        tasks = [task['id'] for task in _list_tasks(options, session)]
        if not tasks:
            print("(no tasks)")
            return
    else:
        tasks = []
        for task in args:
            try:
                tasks.append(int(task))
            except ValueError:
                parser.error("task id must be an integer")
        if not tasks:
            parser.error("at least one task id must be specified")

    return watch_tasks(session, tasks, quiet=options.quiet,
                       poll_interval=goptions.poll_interval, topurl=goptions.topurl)


def anon_handle_watch_logs(goptions, session, args):
    "[monitor] Watch logs in realtime"
    usage = "usage: %prog watch-logs [options] <task id> [<task id> ...]"
    parser = OptionParser(usage=get_usage_str(usage))
    parser.add_option("--log", help="Watch only a specific log")
    parser.add_option("--mine", action="store_true",
                      help="Watch logs for all your tasks, task_id arguments are forbidden in "
                           "this case.")
    parser.add_option("-f", "--follow", action="store_true", help="Follow spawned child tasks")
    (options, args) = parser.parse_args(args)

    if options.mine:
        activate_session(session, goptions)
        if args:
            parser.error("Selection options cannot be combined with a task list")
        tasks = _list_tasks(options, session)
        tasks = [t['id'] for t in tasks]
        if not tasks:
            print("You've no active tasks.")
            return
    else:
        ensure_connection(session, goptions)
        tasks = []
        for task in args:
            try:
                tasks.append(int(task))
            except ValueError:
                parser.error("task id must be an integer")
    if not tasks:
        parser.error("at least one task id must be specified")

    watch_logs(session, tasks, options, goptions.poll_interval)


def handle_make_task(goptions, session, args):
    "[admin] Create an arbitrary task"
    usage = "usage: %prog make-task [options] <method> [<arg> ...]"
    parser = OptionParser(usage=get_usage_str(usage))
    parser.add_option("--channel", help="set channel")
    parser.add_option("--priority", help="set priority")
    parser.add_option("--watch", action="store_true", help="watch the task")
    parser.add_option("--arch", help="set arch")
    (options, args) = parser.parse_args(args)
    if len(args) < 1:
        parser.error("Please specify task method at least")

    activate_session(session, goptions)
    taskopts = {}
    for key in ('channel', 'priority', 'arch'):
        value = getattr(options, key, None)
        if value is not None:
            taskopts[key] = value
    task_id = session.makeTask(method=args[0],
                               arglist=list(map(arg_filter, args[1:])),
                               **taskopts)
    print("Created task id %d" % task_id)
    if _running_in_bg() or not options.watch:
        return
    else:
        session.logout()
        return watch_tasks(session, [task_id], quiet=goptions.quiet,
                           poll_interval=goptions.poll_interval, topurl=goptions.topurl)


def handle_tag_build(opts, session, args):
    "[bind] Apply a tag to one or more builds"
    usage = "usage: %prog tag-build [options] <tag> <pkg> [<pkg> ...]"
    parser = OptionParser(usage=get_usage_str(usage))
    parser.add_option("--force", action="store_true", help="force operation")
    parser.add_option("--wait", action="store_true",
                      help="Wait on task, even if running in the background")
    parser.add_option("--nowait", action="store_false", dest="wait", help="Do not wait on task")
    (options, args) = parser.parse_args(args)
    if len(args) < 2:
        parser.error(
            "This command takes at least two arguments: a tag name/ID and one or more package "
            "n-v-r's")
    activate_session(session, opts)
    tasks = []
    for pkg in args[1:]:
        task_id = session.tagBuild(args[0], pkg, force=options.force)
        # XXX - wait on task
        tasks.append(task_id)
        print("Created task %d" % task_id)
    if options.wait or (options.wait is None and not _running_in_bg()):
        session.logout()
        return watch_tasks(session, tasks, quiet=opts.quiet,
                           poll_interval=opts.poll_interval, topurl=opts.topurl)


def handle_move_build(opts, session, args):
    "[bind] 'Move' one or more builds between tags"
    usage = "usage: %prog move-build [options] <tag1> <tag2> <pkg> [<pkg> ...]"
    parser = OptionParser(usage=get_usage_str(usage))
    parser.add_option("--force", action="store_true", help="force operation")
    parser.add_option("--wait", action="store_true",
                      help="Wait on tasks, even if running in the background")
    parser.add_option("--nowait", action="store_false", dest="wait",
                      help="Do not wait on tasks")
    parser.add_option("--all", action="store_true",
                      help="move all instances of a package, <pkg>'s are package names")
    (options, args) = parser.parse_args(args)
    if len(args) < 3:
        if options.all:
            parser.error(
                "This command, with --all, takes at least three arguments: two tags and one or "
                "more package names")
        else:
            parser.error(
                "This command takes at least three arguments: two tags and one or more package "
                "n-v-r's")
    activate_session(session, opts)
    tasks = []
    builds = []

    if options.all:
        for arg in args[2:]:
            pkg = session.getPackage(arg)
            if not pkg:
                print("No such package: %s, skipping." % arg)
                continue
            tasklist = session.moveAllBuilds(args[0], args[1], arg, options.force)
            tasks.extend(tasklist)
    else:
        for arg in args[2:]:
            build = session.getBuild(arg)
            if not build:
                print("No such build: %s, skipping." % arg)
                continue
            if build not in builds:
                builds.append(build)

        for build in builds:
            task_id = session.moveBuild(args[0], args[1], build['id'], options.force)
            tasks.append(task_id)
            print("Created task %d, moving %s" % (task_id, koji.buildLabel(build)))
    if options.wait or (options.wait is None and not _running_in_bg()):
        session.logout()
        return watch_tasks(session, tasks, quiet=opts.quiet,
                           poll_interval=opts.poll_interval, topurl=opts.topurl)


def handle_untag_build(goptions, session, args):
    "[bind] Remove a tag from one or more builds"
    usage = "usage: %prog untag-build [options] <tag> <pkg> [<pkg> ...]"
    parser = OptionParser(usage=get_usage_str(usage))
    parser.add_option("--all", action="store_true",
                      help="untag all versions of the package in this tag, pkg is package name")
    parser.add_option("--non-latest", action="store_true",
                      help="untag all versions of the package in this tag except the latest, "
                           "pkg is package name")
    parser.add_option("-n", "--test", action="store_true", help="test mode")
    parser.add_option("-v", "--verbose", action="store_true", help="print details")
    parser.add_option("--force", action="store_true", help="force operation")
    (options, args) = parser.parse_args(args)
    if options.non_latest and options.force:
        if len(args) < 1:
            parser.error("Please specify a tag")
    elif len(args) < 2:
        parser.error(
            "This command takes at least two arguments: a tag name/ID and one or more package "
            "n-v-r's or package names")
    activate_session(session, goptions)
    tag = session.getTag(args[0])
    if not tag:
        parser.error("No such tag: %s" % args[0])
    if options.all:
        result = []
        with session.multicall() as m:
            result.extend([m.queryHistory(tag=args[0], package=pkg, active=True)
                           for pkg in args[1:]])
        builds = []
        for r in result:
            builds.extend(r.result['tag_listing'])
    elif options.non_latest:
        if options.force and len(args) == 1:
            tagged = session.queryHistory(tag=args[0], active=True)['tag_listing']
            tagged = sorted(tagged, key=lambda k: (k['create_event']), reverse=True)
        else:
            result = []
            with session.multicall() as m:
                result.extend([m.queryHistory(tag=args[0], package=pkg, active=True)
                               for pkg in args[1:]])
            tagged = []
            for r in result:
                tagged.extend(r.result['tag_listing'])
            tagged = sorted(tagged, key=lambda k: (k['create_event']), reverse=True)
        # listTagged orders entries latest first
        seen_pkg = {}
        builds = []
        for binfo in tagged:
            if binfo['name'] not in seen_pkg:
                # latest for this package
                nvr = '%s-%s-%s' % (binfo['name'], binfo['version'], binfo['release'])
                if options.verbose:
                    print("Leaving latest build for package %s: %s" % (binfo['name'], nvr))
            else:
                builds.append(binfo)
            seen_pkg[binfo['name']] = 1
    else:
        # find all pkg's builds in tag
        pkgs = set([koji.parse_NVR(nvr)['name'] for nvr in args[1:]])
        result = []
        with session.multicall() as m:
            result.extend([m.queryHistory(tag=args[0], pkg=pkg, active=True) for pkg in pkgs])
        tagged = []
        for r in result:
            tagged.append(r.result['tag_listing'])
        # flatten
        tagged = list(itertools.chain(*[t for t in tagged]))
        idx = dict([('%s-%s-%s' % (b['name'], b['version'], b['release']), b) for b in tagged])

        # check exact builds
        builds = []
        for nvr in args[1:]:
            binfo = idx.get(nvr)
            if binfo:
                builds.append(binfo)
            else:
                # not in tag, see if it even exists
                binfo = session.getBuild(nvr)
                if not binfo:
                    warn("No such build: %s" % nvr)
                else:
                    warn("Build %s not in tag %s" % (nvr, tag['name']))
                if not options.force:
                    error()
    builds.reverse()
    with session.multicall(strict=True) as m:
        for binfo in builds:
            build_nvr = '%s-%s-%s' % (binfo['name'], binfo['version'], binfo['release'])
            if options.test:
                print("would have untagged %s" % build_nvr)
            else:
                if options.verbose:
                    print("untagging %s" % build_nvr)
                m.untagBuild(tag['name'], build_nvr, force=options.force)


def handle_unblock_pkg(goptions, session, args):
    "[admin] Unblock a package in the listing for tag"
    usage = "usage: %prog unblock-pkg [options] <tag> <package> [<package> ...]"
    parser = OptionParser(usage=get_usage_str(usage))
    (options, args) = parser.parse_args(args)
    if len(args) < 2:
        parser.error("Please specify a tag and at least one package")
    activate_session(session, goptions)
    tag = args[0]
    with session.multicall(strict=True) as m:
        for package in args[1:]:
            m.packageListUnblock(tag, package)


def anon_handle_download_build(options, session, args):
    "[download] Download a built package"
    usage = "usage: %prog download-build [options] <n-v-r | build_id | package>"
    parser = OptionParser(usage=get_usage_str(usage))
    parser.add_option("--arch", "-a", dest="arches", metavar="ARCH", action="append", default=[],
                      help="Only download packages for this arch (may be used multiple times)")
    parser.add_option("--type",
                      help="Download archives of the given type, rather than rpms "
                           "(maven, win, image, remote-sources)")
    parser.add_option("--latestfrom", dest="latestfrom",
                      help="Download the latest build from this tag")
    parser.add_option("--debuginfo", action="store_true", help="Also download -debuginfo rpms")
    parser.add_option("--task-id", action="store_true", help="Interperet id as a task id")
    parser.add_option("--rpm", action="store_true", help="Download the given rpm")
    parser.add_option("--key", help="Download rpms signed with the given key")
    parser.add_option("--topurl", metavar="URL", default=options.topurl,
                      help="URL under which Koji files are accessible")
    parser.add_option("--noprogress", action="store_true", help="Do not display progress meter")
    parser.add_option("-q", "--quiet", action="store_true",
                      help="Suppress output", default=options.quiet)
    (suboptions, args) = parser.parse_args(args)
    if len(args) < 1:
        parser.error("Please specify a package N-V-R or build ID")
    elif len(args) > 1:
        parser.error("Only a single package N-V-R or build ID may be specified")

    ensure_connection(session, options)
    build = args[0]

    if build.isdigit():
        if suboptions.latestfrom:
            parser.error("--latestfrom not compatible with build IDs, specify a package name.")
        build = int(build)
        if suboptions.task_id:
            builds = session.listBuilds(taskID=build)
            if not builds:
                error("No associated builds for task %s" % build)
            build = builds[0]['build_id']

    if suboptions.latestfrom:
        # We want the latest build, not a specific build
        try:
            builds = session.listTagged(suboptions.latestfrom, latest=True, package=build,
                                        type=suboptions.type)
        except koji.GenericError as data:
            error("Error finding latest build: %s" % data)
        if not builds:
            error("%s has no builds of %s" % (suboptions.latestfrom, build))
        info = builds[0]
    elif suboptions.rpm:
        rpminfo = session.getRPM(build)
        if rpminfo is None:
            error("No such rpm: %s" % build)
        info = session.getBuild(rpminfo['build_id'])
    else:
        # if we're given an rpm name without --rpm, download the containing build
        try:
            koji.parse_NVRA(build)
            rpminfo = session.getRPM(build)
            build = rpminfo['build_id']
        except Exception:
            pass
        info = session.getBuild(build)

    if info is None:
        error("No such build: %s" % build)

    if not suboptions.topurl:
        error("You must specify --topurl to download files")

    archives = []
    rpms = []
    if suboptions.type:
        archives = session.listArchives(buildID=info['id'], type=suboptions.type)
        if not archives:
            error("No %s archives available for %s" % (suboptions.type, koji.buildLabel(info)))
    else:
        arches = suboptions.arches
        if len(arches) == 0:
            arches = None
        if suboptions.rpm:
            all_rpms = [rpminfo]
        else:
            all_rpms = session.listRPMs(buildID=info['id'], arches=arches)
        if not all_rpms:
            if arches:
                error("No %s packages available for %s" %
                      (" or ".join(arches), koji.buildLabel(info)))
            else:
                error("No packages available for %s" % koji.buildLabel(info))
        for rpm in all_rpms:
            if not suboptions.debuginfo and koji.is_debuginfo(rpm['name']):
                continue
            rpms.append(rpm)

    if suboptions.key:
        with session.multicall() as m:
            results = [m.queryRPMSigs(rpm_id=r['id'], sigkey=suboptions.key) for r in rpms]
        rpm_keys = [x.result for x in results]
        for rpm, rpm_key in list(zip(rpms, rpm_keys)):
            if not rpm_key:
                nvra = "%(nvr)s-%(arch)s.rpm" % rpm
                warn("No such sigkey %s for rpm %s" % (suboptions.key, nvra))
                rpms.remove(rpm)

    size = len(rpms) + len(archives)
    number = 0

    # run the download
    for rpm in rpms:
        number += 1
        download_rpm(info, rpm, suboptions.topurl, sigkey=suboptions.key, quiet=suboptions.quiet,
                     noprogress=suboptions.noprogress, num=number, size=size)
    for archive in archives:
        number += 1
        download_archive(info, archive, suboptions.topurl, quiet=suboptions.quiet,
                         noprogress=suboptions.noprogress, num=number, size=size)


def anon_handle_download_logs(options, session, args):
    "[download] Download logs for task"

    FAIL_LOG = "task_failed.log"
    usage = "usage: %prog download-logs [options] <task_id> [<task_id> ...]"
    usage += "\n       %prog download-logs [options] --nvr <n-v-r> [<n-v-r> ...]"
    usage += "\n"
    usage += "\n"
    usage += "Note this command only downloads task logs, not build logs."
    usage += "\n"
    parser = OptionParser(usage=get_usage_str(usage))
    parser.add_option("-r", "--recurse", action="store_true",
                      help="Process children of this task as well")
    parser.add_option("--nvr", action="store_true",
                      help="Get the logs for the task associated with this build "
                           "Name-Version-Release.")
    parser.add_option("-m", "--match", action="append", metavar="PATTERN",
                      help="Get only log filenames matching PATTERN (fnmatch). "
                           "May be used multiple times.")
    parser.add_option("-c", "--continue", action="store_true", dest="cont",
                      help="Continue previous download")
    parser.add_option("-d", "--dir", metavar="DIRECTORY", default='kojilogs',
                      help="Write logs to DIRECTORY")
    (suboptions, args) = parser.parse_args(args)

    if len(args) < 1:
        parser.error("Please specify at least one task id or n-v-r")

    def write_fail_log(task_log_dir, task_id):
        """Gets output only from failed tasks"""
        try:
            result = session.getTaskResult(task_id)
            # with current code, failed task results should always be faults,
            # but that could change in the future
            content = pprint.pformat(result)
        except (six.moves.xmlrpc_client.Fault, koji.GenericError):
            etype, e = sys.exc_info()[:2]
            content = ''.join(traceback.format_exception_only(etype, e))
        full_filename = os.path.normpath(os.path.join(task_log_dir, FAIL_LOG))
        koji.ensuredir(os.path.dirname(full_filename))
        sys.stdout.write("Writing: %s\n" % full_filename)
        with open(full_filename, 'wt') as fo:
            fo.write(content)

    def download_log(task_log_dir, task_id, filename, blocksize=102400, volume=None):
        # Create directories only if there is any log file to write to
        # For each non-default volume create special sub-directory
        if volume not in (None, 'DEFAULT'):
            full_filename = os.path.normpath(os.path.join(task_log_dir, volume, filename))
        else:
            full_filename = os.path.normpath(os.path.join(task_log_dir, filename))
        koji.ensuredir(os.path.dirname(full_filename))
        contents = 'IGNORE ME!'
        if suboptions.cont and os.path.exists(full_filename):
            sys.stdout.write("Continuing: %s\n" % full_filename)
            fd = open(full_filename, 'ab')
            offset = fd.tell()
        else:
            sys.stdout.write("Downloading: %s\n" % full_filename)
            fd = open(full_filename, 'wb')
            offset = 0
        try:
            while contents:
                contents = session.downloadTaskOutput(task_id, filename, offset=offset,
                                                      size=blocksize, volume=volume)
                offset += len(contents)
                if contents:
                    fd.write(contents)
        finally:
            fd.close()

    def save_logs(task_id, match, parent_dir='.', recurse=True):
        assert task_id == int(task_id), "Task id must be number: %r" % task_id
        task_info = session.getTaskInfo(task_id)
        if task_info is None:
            error("No such task: %d" % task_id)
        files = list_task_output_all_volumes(session, task_id)
        logs = []  # list of tuples (filename, volume)
        for filename in files:
            if not filename.endswith(".log"):
                continue
            if match and not koji.util.multi_fnmatch(filename, match):
                continue
            logs += [(filename, volume) for volume in files[filename]]

        task_log_dir = os.path.join(parent_dir,
                                    "%s-%s" % (task_info["arch"], task_id))

        count = 0
        state = koji.TASK_STATES[task_info['state']]
        if state == 'FAILED':
            if not match or koji.util.multi_fnmatch(FAIL_LOG, match):
                write_fail_log(task_log_dir, task_id)
                count += 1
        elif state not in ['CLOSED', 'CANCELED']:
            warn("Task %s is %s\n" % (task_id, state))

        for log_filename, log_volume in logs:
            download_log(task_log_dir, task_id, log_filename, volume=log_volume)
            count += 1

        if count == 0 and not recurse:
            warn("No logs found for task %i. Perhaps try --recurse?\n" % task_id)

        if recurse:
            child_tasks = session.getTaskChildren(task_id)
            for child_task in child_tasks:
                save_logs(child_task['id'], match, task_log_dir, recurse)

    ensure_connection(session, options)
    task_id = None
    build_id = None
    for arg in args:
        if suboptions.nvr:
            suboptions.recurse = True
            binfo = session.getBuild(arg)
            if binfo is None:
                error("There is no build with n-v-r: %s" % arg)
            if binfo.get('task_id'):
                task_id = binfo['task_id']
                sys.stdout.write("Using task ID: %s\n" % task_id)
            elif binfo.get('build_id'):
                build_id = binfo['build_id']
                sys.stdout.write("Using build ID: %s\n" % build_id)
        else:
            try:
                task_id = int(arg)
            except ValueError:
                error("Task id must be number: %r" % arg)
        if task_id:
            save_logs(task_id, suboptions.match, suboptions.dir, suboptions.recurse)
        elif build_id:
            logs = session.getBuildLogs(build_id)
            match = suboptions.match
            for log in logs:
                url = os.path.join(options.topurl, log['path'])
                filepath = os.path.join(os.getcwd(), '%s/%s/%s' % (suboptions.dir,
                                                                   arg, log['name']))
                if not filepath.endswith(".log"):
                    continue
                if match and not koji.util.multi_fnmatch(log['name'], match):
                    continue
                download_file(url, filepath)


def anon_handle_download_task(options, session, args):
    "[download] Download the output of a build task"
    usage = "usage: %prog download-task <task_id>\n" \
            "Default behavior without --all option downloads .rpm files only for build " \
            "and buildArch tasks.\n"
    parser = OptionParser(usage=get_usage_str(usage))
    parser.add_option("--arch", dest="arches", metavar="ARCH", action="append", default=[],
                      help="Only download packages for this arch (may be used multiple times), "
                           "only for build and buildArch task methods")
    parser.add_option("--logs", dest="logs", action="store_true", default=False,
                      help="Also download build logs")
    parser.add_option("--topurl", metavar="URL", default=options.topurl,
                      help="URL under which Koji files are accessible")
    parser.add_option("--noprogress", action="store_true", help="Do not display progress meter")
    parser.add_option("--wait", action="store_true",
                      help="Wait for running tasks to finish, even if running in the background")
    parser.add_option("--nowait", action="store_false", dest="wait",
                      help="Do not wait for running tasks to finish")
    parser.add_option("-q", "--quiet", action="store_true",
                      help="Suppress output", default=options.quiet)
    parser.add_option("--all", action="store_true",
                      help="Download all files, all methods instead of build and buildArch")
    parser.add_option("--dirpertask", action="store_true", help="Download files to dir per task")
    parser.add_option("--parentonly", action="store_true", help="Download parent's files only")
    parser.add_option("--filter", dest="filter", action="append", default=[],
                      help="Regex pattern to filter files")
    parser.add_option("--skip", dest="skip", action="append", default=[],
                      help="Regex pattern to skip files")

    (suboptions, args) = parser.parse_args(args)
    if len(args) == 0:
        parser.error("Please specify a task ID")
    elif len(args) > 1:
        parser.error("Only one task ID may be specified")

    base_task_id = int(args.pop())
    if len(suboptions.arches) > 0:
        suboptions.arches = ",".join(suboptions.arches).split(",")

    if suboptions.filter != [] and suboptions.skip != []:
        parser.error("Only filter or skip may be specified. Not both.")

    ensure_connection(session, options)

    # get downloadable tasks

    base_task = session.getTaskInfo(base_task_id)
    if not base_task:
        error('No such task: %d' % base_task_id)

    if (suboptions.wait or (suboptions.wait is None and not _running_in_bg())) and \
            base_task['state'] not in (
            koji.TASK_STATES['CLOSED'],
            koji.TASK_STATES['CANCELED'],
            koji.TASK_STATES['FAILED']):
        watch_tasks(session, [base_task_id], quiet=suboptions.quiet,
                    poll_interval=options.poll_interval, topurl=options.topurl)
        base_task = session.getTaskInfo(base_task_id)

    list_tasks = [base_task]
    if not suboptions.parentonly:
        list_tasks.extend(session.getTaskChildren(base_task_id))
    list_tasks = sorted(list_tasks, key=lambda k: k['id'])

    required_tasks = {}
    for task in list_tasks:
        if task["id"] not in required_tasks:
            required_tasks[task["id"]] = task

    for task_id in sorted(required_tasks):
        task_state = koji.TASK_STATES.get(required_tasks[task_id]["state"])
        if task_state != "CLOSED":
            if task_id == base_task_id:
                start_error_msg = "Task"
            else:
                start_error_msg = "Child task"
            if task_state == 'FAILED':
                error("%s %d failed. You can use save-failed-tree plugin for FAILED tasks."
                      % (start_error_msg, task_id))
            elif task_state == 'CANCELED':
                error("%s %d was canceled." % (start_error_msg, task_id))
            else:
                error("%s %d has not finished yet." % (start_error_msg, task_id))

    # get files for download
    downloads = []
    build_methods_list = ['buildArch', 'build']
    rpm_file_types = ['rpm', 'src.rpm']
    for task in list_tasks:
        taskarch = task['arch']
        task_id = str(task['id'])
        files = list_task_output_all_volumes(session, task["id"])
        for filename in files:
            if suboptions.filter != []:
                res = True
                for filt_item in suboptions.filter:
                    res = re.search(filt_item, filename)
                    if not res:
                        break
                if not res:
                    continue
            if suboptions.skip != []:
                res = False
                for filt_item in suboptions.skip:
                    res = re.search(filt_item, filename)
                    if res:
                        break
                if res:
                    continue

            if filename.endswith('src.rpm'):
                filetype = 'src.rpm'
            else:
                filetype = filename.rsplit('.', 1)[1]
            if suboptions.all and not (task['method'] in build_methods_list and
                                       filetype in rpm_file_types):
                if filetype != 'log':
                    for volume in files[filename]:
                        if suboptions.dirpertask:
                            new_filename = '%s/%s' % (task_id, filename)
                        else:
                            if taskarch not in filename and filetype != 'src.rpm':
                                part_filename = filename[:-len('.%s' % filetype)]
                                new_filename = "%s.%s.%s" % (part_filename,
                                                             taskarch, filetype)
                            else:
                                new_filename = filename
                        downloads.append((task, filename, volume, new_filename, task_id))
            elif task['method'] in build_methods_list:
                if filetype in rpm_file_types:
                    filearch = filename.split(".")[-2]
                    for volume in files[filename]:
                        if len(suboptions.arches) == 0 or filearch in suboptions.arches:
                            if suboptions.dirpertask:
                                new_filename = '%s/%s' % (task_id, filename)
                            else:
                                new_filename = filename
                            downloads.append((task, filename, volume, new_filename,
                                              task_id))

            if filetype == 'log' and suboptions.logs:
                for volume in files[filename]:
                    if suboptions.dirpertask:
                        new_filename = '%s/%s' % (task_id, filename)
                    else:
                        if taskarch not in filename:
                            part_filename = filename[:-len('.log')]
                            new_filename = "%s.%s.log" % (part_filename, taskarch)
                        else:
                            new_filename = filename
                    downloads.append((task, filename, volume, new_filename, task_id))

    if len(downloads) == 0:
        print("No files for download found.")
        return

    # perform the download
    number = 0
    pathinfo = koji.PathInfo(topdir=suboptions.topurl)
    files_downloaded = []
    dirpertask_msg = False
    for (task, filename, volume, new_filename, task_id) in downloads:
        if suboptions.dirpertask:
            koji.ensuredir(task_id)
        number += 1
        if volume not in (None, 'DEFAULT'):
            if suboptions.dirpertask:
                koji.ensuredir('%s/%s' % (task_id, volume))
                new_filename = os.path.join(task_id, volume, filename)
            else:
                koji.ensuredir(volume)
                new_filename = os.path.join(volume, new_filename)
        if '..' in filename:
            error('Invalid file name: %s' % filename)
        url = '%s/%s/%s' % (pathinfo.work(volume), pathinfo.taskrelpath(task["id"]), filename)
        if (new_filename, volume) not in files_downloaded:
            download_file(url, new_filename, quiet=suboptions.quiet,
                          noprogress=suboptions.noprogress, size=len(downloads), num=number)
            files_downloaded.append((new_filename, volume))
        else:
            if not suboptions.quiet:
                print("Downloading [%d/%d]: %s" % (number, len(downloads), new_filename))
                print("File %s already downloaded, skipping" % new_filename)
            dirpertask_msg = True
    if dirpertask_msg:
        warn("Duplicate files, for download all duplicate files use --dirpertask.")


def anon_handle_wait_repo(options, session, args):
    "[monitor] Wait for a repo to be regenerated"
    usage = "usage: %prog wait-repo [options] <tag>"
    parser = OptionParser(usage=get_usage_str(usage))
    parser.add_option("--build", metavar="NVR", dest="builds", action="append", default=[],
                      help="Check that the given build is in the newly-generated repo "
                           "(may be used multiple times)")
    parser.add_option("--target", action="store_true",
                      help="Interpret the argument as a build target name")
    parser.add_option("--timeout", type="int", default=120,
                      help="Amount of time to wait (in minutes) before giving up "
                           "(default: 120)")
    parser.add_option("--quiet", action="store_true", default=options.quiet,
                      help="Suppress output, success or failure will be indicated by the return "
                           "value only")
    (suboptions, args) = parser.parse_args(args)

    builds = [koji.parse_NVR(build) for build in suboptions.builds]
    if len(args) < 1:
        parser.error("Please specify a tag name")
    elif len(args) > 1:
        parser.error("Only one tag may be specified")

    tag = args[0]

    ensure_connection(session, options)
    if suboptions.target:
        target_info = session.getBuildTarget(tag)
        if not target_info:
            parser.error("No such build target: %s" % tag)
        tag = target_info['build_tag_name']
        tag_id = target_info['build_tag']
    else:
        tag_info = session.getTag(tag)
        if not tag_info:
            parser.error("No such tag: %s" % tag)
        targets = session.getBuildTargets(buildTagID=tag_info['id'])
        if not targets:
            warn("%(name)s is not a build tag for any target" % tag_info)
            targets = session.getBuildTargets(destTagID=tag_info['id'])
            if targets:
                maybe = {}.fromkeys([t['build_tag_name'] for t in targets])
                maybe = sorted(maybe.keys())
                warn("Suggested tags: %s" % ', '.join(maybe))
            error()
        tag_id = tag_info['id']

    for nvr in builds:
        data = session.getLatestBuilds(tag_id, package=nvr["name"])
        if len(data) == 0:
            warn("No %s builds in tag %s" % (nvr["name"], tag))
        else:
            present_nvr = [x["nvr"] for x in data][0]
            expected_nvr = '%(name)s-%(version)s-%(release)s' % nvr
            if present_nvr != expected_nvr:
                warn("nvr %s is not current in tag %s\n  latest build in %s is %s" %
                     (expected_nvr, tag, tag, present_nvr))

    success, msg = wait_repo(session, tag_id, builds,
                             poll_interval=options.poll_interval, timeout=suboptions.timeout)
    if success:
        if not suboptions.quiet:
            print(msg)
    else:
        error('' if suboptions.quiet else msg)


def handle_regen_repo(options, session, args):
    "[admin] Force a repo to be regenerated"
    usage = "usage: %prog regen-repo [options] <tag>"
    parser = OptionParser(usage=get_usage_str(usage))
    parser.add_option("--target", action="store_true",
                      help="Interpret the argument as a build target name")
    parser.add_option("--wait", action="store_true",
                      help="Wait on for regen to finish, even if running in the background")
    parser.add_option("--nowait", action="store_false", dest="wait",
                      help="Don't wait on for regen to finish")
    parser.add_option("--debuginfo", action="store_true", help="Include debuginfo rpms in repo")
    parser.add_option("--source", "--src", action="store_true",
                      help="Include source rpms in each of repos")
    parser.add_option("--separate-source", "--separate-src", action="store_true",
                      help="Include source rpms in separate src repo")
    (suboptions, args) = parser.parse_args(args)
    if len(args) == 0:
        parser.error("A tag name must be specified")
    elif len(args) > 1:
        if suboptions.target:
            parser.error("Only a single target may be specified")
        else:
            parser.error("Only a single tag name may be specified")
    activate_session(session, options)
    tag = args[0]
    repo_opts = {}
    if suboptions.target:
        info = session.getBuildTarget(tag)
        if not info:
            parser.error("No such build target: %s" % tag)
        tag = info['build_tag_name']
        info = session.getTag(tag, strict=True)
    else:
        info = session.getTag(tag)
        if not info:
            parser.error("No such tag: %s" % tag)
        tag = info['name']
        targets = session.getBuildTargets(buildTagID=info['id'])
        if not targets:
            warn("%s is not a build tag" % tag)
    if not info['arches']:
        warn("Tag %s has an empty arch list" % info['name'])
    if suboptions.debuginfo:
        repo_opts['debuginfo'] = True
    if suboptions.source:
        repo_opts['src'] = True
    if suboptions.separate_source:
        repo_opts['separate_src'] = True
    task_id = session.newRepo(tag, **repo_opts)
    print("Regenerating repo for tag: %s" % tag)
    print("Created task: %d" % task_id)
    print("Task info: %s/taskinfo?taskID=%s" % (options.weburl, task_id))
    if suboptions.wait or (suboptions.wait is None and not _running_in_bg()):
        session.logout()
        return watch_tasks(session, [task_id], quiet=options.quiet,
                           poll_interval=options.poll_interval, topurl=options.topurl)


def handle_dist_repo(options, session, args):
    """Create a yum repo with distribution options"""
    usage = "usage: %prog dist-repo [options] <tag> <key_id> [<key_id> ...]\n\n" \
            "In normal mode, dist-repo behaves like any other koji task.\n" \
            "Sometimes you want to limit running distRepo tasks per tag to only\n" \
            "one. For such behaviour admin (with 'tag' permission) needs to\n" \
            "modify given tag's extra field 'distrepo.cancel_others' to True'\n" \
            "via 'koji edit-tag -x distrepo.cancel_others=True'\n"
    usage += "\n(Specify the --help option for a list of other options)"
    parser = OptionParser(usage=usage)
    parser.add_option('--allow-missing-signatures', action='store_true',
                      default=False,
                      help='For RPMs not signed with a desired key, fall back to the primary copy')
    parser.add_option("-a", "--arch", action='append', default=[],
                      help="Indicate an architecture to consider. The default is all "
                           "architectures associated with the given tag. This option may "
                           "be specified multiple times.")
    parser.add_option("--with-src", action='store_true', help='Also generate a src repo')
    parser.add_option("--split-debuginfo", action='store_true', default=False,
                      help='Split debuginfo info a separate repo for each arch')
    parser.add_option('--comps', help='Include a comps file in the repodata')
    parser.add_option('--delta-rpms', metavar='REPO', default=[], action='append',
                      help='Create delta rpms. REPO can be the id of another dist repo '
                           'or the name of a tag that has a dist repo. May be specified '
                           'multiple times.')
    parser.add_option('--event', type='int', help='Use tag content at event')
    parser.add_option("--volume", help="Generate repo on given volume")
    parser.add_option('--non-latest', dest='latest', default=True,
                      action='store_false', help='Include older builds, not just the latest')
    parser.add_option('--multilib', default=None, metavar="CONFIG",
                      help='Include multilib packages in the repository using the given '
                           'config file')
    parser.add_option("--noinherit", action='store_true', default=False,
                      help='Do not consider tag inheritance')
    parser.add_option("--wait", action="store_true",
                      help="Wait for the task to complete, even if running in the background")
    parser.add_option("--nowait", action="store_false", dest="wait",
                      help="Do not wait for the task to complete")
    parser.add_option('--skip-missing-signatures', action='store_true', default=False,
                      help='Skip RPMs not signed with the desired key(s)')
    parser.add_option('--zck', action='store_true', default=False,
                      help='Generate zchunk files as well as the standard repodata')
    parser.add_option('--zck-dict-dir', action='store', default=None,
                      help='Directory containing compression dictionaries for use by zchunk '
                           '(on builder)')
    parser.add_option("--write-signed-rpms", action='store_true', default=False,
                      help='Write a signed rpms for given tag')
    parser.add_option("--skip-stat", action='store_true', default=None, dest='skip_stat',
                      help="Skip rpm stat during createrepo (override default builder setting)")
    parser.add_option("--no-skip-stat", action='store_false', default=None, dest='skip_stat',
                      help="Don't skip rpm stat during createrepo "
                           "(override default builder setting)")
    task_opts, args = parser.parse_args(args)
    if len(args) < 1:
        parser.error('You must provide a tag to generate the repo from')
    if len(args) < 2 and not task_opts.allow_missing_signatures:
        parser.error('Please specify one or more GPG key IDs (or --allow-missing-signatures)')
    if task_opts.allow_missing_signatures and task_opts.skip_missing_signatures:
        parser.error('allow_missing_signatures and skip_missing_signatures are mutually exclusive')
    activate_session(session, options)
    stuffdir = unique_path('cli-dist-repo')
    if task_opts.comps:
        if not os.path.exists(task_opts.comps):
            parser.error('could not find %s' % task_opts.comps)
        session.uploadWrapper(task_opts.comps, stuffdir,
                              callback=_progress_callback)
        print('')
        task_opts.comps = os.path.join(stuffdir,
                                       os.path.basename(task_opts.comps))
    old_repos = []
    if len(task_opts.delta_rpms) > 0:
        for repo in task_opts.delta_rpms:
            if repo.isdigit():
                rinfo = session.repoInfo(int(repo), strict=True)
            else:
                # get dist repo for tag
                rinfo = session.getRepo(repo, dist=True)
                if not rinfo:
                    # maybe there is an expired one
                    rinfo = session.getRepo(repo,
                                            state=koji.REPO_STATES['EXPIRED'], dist=True)
                if not rinfo:
                    parser.error("Can't find repo for tag: %s" % repo)
            old_repos.append(rinfo['id'])
    tag = args[0]
    keys = args[1:]
    taginfo = session.getTag(tag)
    if not taginfo:
        parser.error('No such tag: %s' % tag)
    allowed_arches = taginfo['arches'] or ''
    if not allowed_arches:
        for tag_inh in session.getFullInheritance(tag):
            allowed_arches = session.getTag(tag_inh['parent_id'])['arches'] or ''
            if allowed_arches:
                break
    if len(task_opts.arch) == 0:
        task_opts.arch = allowed_arches.split()
        if not task_opts.arch:
            parser.error('No arches given and no arches associated with tag')
    else:
        for a in task_opts.arch:
            if not allowed_arches:
                warn('Tag %s has an empty arch list' % taginfo['name'])
            elif a not in allowed_arches:
                warn('%s is not in the list of tag arches' % a)
    if task_opts.multilib:
        if not os.path.exists(task_opts.multilib):
            parser.error('could not find %s' % task_opts.multilib)
        if 'x86_64' in task_opts.arch and 'i686' not in task_opts.arch:
            parser.error('The multilib arch (i686) must be included')
        if 's390x' in task_opts.arch and 's390' not in task_opts.arch:
            parser.error('The multilib arch (s390) must be included')
        if 'ppc64' in task_opts.arch and 'ppc' not in task_opts.arch:
            parser.error('The multilib arch (ppc) must be included')
        session.uploadWrapper(task_opts.multilib, stuffdir,
                              callback=_progress_callback)
        task_opts.multilib = os.path.join(stuffdir,
                                          os.path.basename(task_opts.multilib))
        print('')
    if 'noarch' in task_opts.arch:
        task_opts.arch.remove('noarch')
    if task_opts.with_src and 'src' not in task_opts.arch:
        task_opts.arch.append('src')
    if not task_opts.arch:
        parser.error('No arches left.')

    opts = {
        'arch': task_opts.arch,
        'comps': task_opts.comps,
        'delta': old_repos,
        'event': task_opts.event,
        'volume': task_opts.volume,
        'inherit': not task_opts.noinherit,
        'latest': task_opts.latest,
        'multilib': task_opts.multilib,
        'split_debuginfo': task_opts.split_debuginfo,
        'skip_missing_signatures': task_opts.skip_missing_signatures,
        'allow_missing_signatures': task_opts.allow_missing_signatures,
        'zck': task_opts.zck,
        'zck_dict_dir': task_opts.zck_dict_dir,
        'write_signed_rpms': task_opts.write_signed_rpms,
    }
    if task_opts.skip_stat is not None:
        opts['createrepo_skip_stat'] = task_opts.skip_stat
    task_id = session.distRepo(tag, keys, **opts)
    print("Creating dist repo for tag " + tag)
    if task_opts.wait or (task_opts.wait is None and not _running_in_bg()):
        session.logout()
        return watch_tasks(session, [task_id], quiet=options.quiet,
                           poll_interval=options.poll_interval, topurl=options.topurl)


_search_types = ('package', 'build', 'tag', 'target', 'user', 'host', 'rpm',
                 'maven', 'win')


def anon_handle_search(goptions, session, args):
    "[search] Search the system"
    usage = "usage: %prog search [options] <search_type> <pattern>"
    usage += '\nAvailable search types: %s' % ', '.join(_search_types)
    parser = OptionParser(usage=get_usage_str(usage))
    parser.add_option("-r", "--regex", action="store_true", help="treat pattern as regex")
    parser.add_option("--exact", action="store_true", help="exact matches only")
    (options, args) = parser.parse_args(args)
    if len(args) < 1:
        parser.error("Please specify search type")
    if len(args) < 2:
        parser.error("Please specify search pattern")
    type = args[0]
    if type not in _search_types:
        parser.error("No such search type: %s" % type)
    pattern = args[1]
    matchType = 'glob'
    if options.regex:
        matchType = 'regexp'
    elif options.exact:
        matchType = 'exact'
    ensure_connection(session, goptions)
    data = session.search(pattern, type, matchType)
    for row in data:
        print(row['name'])


def handle_moshimoshi(options, session, args):
    "[misc] Introduce yourself"
    usage = "usage: %prog moshimoshi [options]"
    parser = OptionParser(usage=get_usage_str(usage))
    (opts, args) = parser.parse_args(args)
    if len(args) != 0:
        parser.error("This command takes no arguments")
    activate_session(session, options)
    u = session.getLoggedInUser()
    if not u:
        print("Not authenticated")
        u = {'name': 'anonymous user'}
    print("%s, %s!" % (_printable_unicode(random.choice(greetings)), u["name"]))
    print("")
    print("You are using the hub at %s (Koji %s)" % (session.baseurl, session.hub_version_str))
    authtype = u.get('authtype', getattr(session, 'authtype', None))
    if authtype == koji.AUTHTYPES['NORMAL']:
        print("Authenticated via password")
    elif authtype == koji.AUTHTYPES['GSSAPI']:
        print("Authenticated via GSSAPI")
    elif authtype == koji.AUTHTYPES['KERBEROS']:
        print("Authenticated via Kerberos principal %s" % session.krb_principal)
    elif authtype == koji.AUTHTYPES['SSL']:
        print("Authenticated via client certificate %s" % options.cert)


def anon_handle_list_notifications(goptions, session, args):
    "[monitor] List user's notifications and blocks"
    usage = "usage: %prog list-notifications [options]"
    parser = OptionParser(usage=get_usage_str(usage))
    parser.add_option("--mine", action="store_true", help="Just print your notifications")
    parser.add_option("--user", help="Only notifications for this user")
    (options, args) = parser.parse_args(args)

    if len(args) != 0:
        parser.error("This command takes no arguments")
    if not options.mine and not options.user:
        parser.error("Use --user or --mine.")

    if options.user:
        ensure_connection(session, goptions)
        user = session.getUser(options.user)
        if not user:
            error("No such user: %s" % options.user)
        user_id = user['id']
    else:
        activate_session(session, goptions)
        user_id = None

    mask = "%(id)6s %(tag)-25s %(package)-25s %(email)-20s %(success)-12s"
    headers = {'id': 'ID',
               'tag': 'Tag',
               'package': 'Package',
               'email': 'E-mail',
               'success': 'Success-only'}
    head = mask % headers
    notifications = session.getBuildNotifications(user_id)
    if notifications:
        print('Notifications')
        print(head)
        print('-' * len(head))
        for notification in notifications:
            if notification['tag_id']:
                notification['tag'] = session.getTag(notification['tag_id'])['name']
            else:
                notification['tag'] = '*'
            if notification['package_id']:
                notification['package'] = session.getPackage(notification['package_id'])['name']
            else:
                notification['package'] = '*'
            notification['success'] = ['no', 'yes'][notification['success_only']]
            print(mask % notification)
    else:
        print('No notifications')

    print('')

    mask = "%(id)6s %(tag)-25s %(package)-25s"
    head = mask % headers
    blocks = session.getBuildNotificationBlocks(user_id)
    if blocks:
        print('Notification blocks')
        print(head)
        print('-' * len(head))
        for notification in blocks:
            if notification['tag_id']:
                notification['tag'] = session.getTag(notification['tag_id'])['name']
            else:
                notification['tag'] = '*'
            if notification['package_id']:
                notification['package'] = session.getPackage(notification['package_id'])['name']
            else:
                notification['package'] = '*'
            print(mask % notification)
    else:
        print('No notification blocks')


def handle_add_notification(goptions, session, args):
    "[monitor] Add user's notification"
    usage = "usage: %prog add-notification [options]"
    parser = OptionParser(usage=get_usage_str(usage))
    parser.add_option("--user", help="Add notifications for this user (admin-only)")
    parser.add_option("--package", help="Add notifications for this package")
    parser.add_option("--tag", help="Add notifications for this tag")
    parser.add_option("--success-only", action="store_true", default=False,
                      help="Enabled notification on successful events only")
    (options, args) = parser.parse_args(args)

    if len(args) != 0:
        parser.error("This command takes no arguments")

    if not options.package and not options.tag:
        parser.error("Command need at least one from --tag or --package options.")

    activate_session(session, goptions)

    if options.user and not session.hasPerm('admin'):
        parser.error("--user requires admin permission")

    if options.user:
        user_id = session.getUser(options.user)['id']
    else:
        user_id = session.getLoggedInUser()['id']

    if options.package:
        package_id = session.getPackageID(options.package)
        if package_id is None:
            parser.error("No such package: %s" % options.package)
    else:
        package_id = None

    if options.tag:
        try:
            tag_id = session.getTagID(options.tag, strict=True)
        except koji.GenericError:
            parser.error("No such tag: %s" % options.tag)
    else:
        tag_id = None

    session.createNotification(user_id, package_id, tag_id, options.success_only)


def handle_remove_notification(goptions, session, args):
    "[monitor] Remove user's notifications"
    usage = "usage: %prog remove-notification [options] <notification_id> [<notification_id> ...]"
    parser = OptionParser(usage=get_usage_str(usage))
    (options, args) = parser.parse_args(args)

    activate_session(session, goptions)

    if len(args) < 1:
        parser.error("At least one notification id has to be specified")

    try:
        n_ids = [int(x) for x in args]
    except ValueError:
        parser.error("All notification ids has to be integers")

    for n_id in n_ids:
        session.deleteNotification(n_id)
        if not goptions.quiet:
            print("Notification %d successfully removed." % n_id)


def handle_edit_notification(goptions, session, args):
    "[monitor] Edit user's notification"
    usage = "usage: %prog edit-notification [options] <notification_id>"
    parser = OptionParser(usage=get_usage_str(usage))
    parser.add_option("--package", help="Notifications for this package, '*' for all")
    parser.add_option("--tag", help="Notifications for this tag, '*' for all")
    parser.add_option("--success-only", action="store_true", default=None,
                      dest='success_only', help="Notify only on successful events")
    parser.add_option("--no-success-only", action="store_false",
                      default=None, dest='success_only', help="Notify on all events")
    (options, args) = parser.parse_args(args)

    if len(args) != 1:
        parser.error("Only argument is notification ID")

    try:
        n_id = int(args[0])
    except ValueError:
        parser.error("Notification ID has to be numeric")

    if not options.package and not options.tag and options.success_only is None:
        parser.error("Command need at least one option")

    activate_session(session, goptions)

    old = session.getBuildNotification(n_id)

    if options.package == '*':
        package_id = None
    elif options.package:
        package_id = session.getPackageID(options.package)
        if package_id is None:
            parser.error("No such package: %s" % options.package)
    else:
        package_id = old['package_id']

    if options.tag == '*':
        tag_id = None
    elif options.tag:
        try:
            tag_id = session.getTagID(options.tag, strict=True)
        except koji.GenericError:
            parser.error("No such tag: %s" % options.tag)
    else:
        tag_id = old['tag_id']

    if options.success_only is not None:
        success_only = options.success_only
    else:
        success_only = old['success_only']

    session.updateNotification(n_id, package_id, tag_id, success_only)


def handle_block_notification(goptions, session, args):
    "[monitor] Block user's notifications"
    usage = "usage: %prog block-notification [options]"
    parser = OptionParser(usage=get_usage_str(usage))
    parser.add_option("--user", help="Block notifications for this user (admin-only)")
    parser.add_option("--package", help="Block notifications for this package")
    parser.add_option("--tag", help="Block notifications for this tag")
    parser.add_option("--all", action="store_true", help="Block all notification for this user")
    (options, args) = parser.parse_args(args)

    if len(args) != 0:
        parser.error("This command takes no arguments")

    if not options.package and not options.tag and not options.all:
        parser.error("One of --tag, --package or --all must be specified.")

    activate_session(session, goptions)

    if options.user and not session.hasPerm('admin'):
        parser.error("--user requires admin permission")

    if options.user:
        user_id = session.getUser(options.user, strict=True)['id']
    else:
        logged_in_user = session.getLoggedInUser()
        if logged_in_user:
            user_id = logged_in_user['id']
        else:
            parser.error("Please login with authentication or specify --user")

    if options.package:
        package_id = session.getPackageID(options.package)
        if package_id is None:
            parser.error("No such package: %s" % options.package)
    else:
        package_id = None

    if options.tag:
        try:
            tag_id = session.getTagID(options.tag, strict=True)
        except koji.GenericError:
            parser.error("No such tag: %s" % options.tag)
    else:
        tag_id = None

    for block in session.getBuildNotificationBlocks(user_id):
        if block['package_id'] == package_id and block['tag_id'] == tag_id:
            parser.error('Notification already exists.')

    session.createNotificationBlock(user_id, package_id, tag_id)


def handle_unblock_notification(goptions, session, args):
    "[monitor] Unblock user's notification"
    usage = "usage: %prog unblock-notification [options] <notification_id> [<notification_id> ...]"
    parser = OptionParser(usage=get_usage_str(usage))
    (options, args) = parser.parse_args(args)

    activate_session(session, goptions)

    if len(args) < 1:
        parser.error("At least one notification block id has to be specified")

    try:
        n_ids = [int(x) for x in args]
    except ValueError:
        parser.error("All notification block ids has to be integers")

    for n_id in n_ids:
        session.deleteNotificationBlock(n_id)
        if not goptions.quiet:
            print("Notification block %d successfully removed." % n_id)


def handle_version(goptions, session, args):
    """Report client and hub versions"""
    ensure_connection(session, goptions)
    print('Client: %s' % koji.__version__)
    try:
        version = session.getKojiVersion()
        print("Hub:    %s" % version)
    except koji.GenericError:
        print("Hub:    Can't determine (older than 1.23)")


def anon_handle_userinfo(goptions, session, args):
    """[admin] Show information about a user"""
    usage = "usage: %prog userinfo [options] <username> [<username> ...]"
    parser = OptionParser(usage=get_usage_str(usage))
    (options, args) = parser.parse_args(args)
    if len(args) < 1:
        parser.error("You must specify at least one username")

    ensure_connection(session, goptions)

    with session.multicall() as m:
        userinfos = [m.getUser(user, groups=True) for user in args]
    try:
        # hub < 1.34 doesn't support groups option, it also raises an exception on access,
        # so later it would fail the result iteration cycle
        userinfos[0].result
    except koji.ParameterError:
        with session.multicall() as m:
            userinfos = [m.getUser(user) for user in args]

    user_infos = []
    for username, userinfo in zip(args, userinfos):
        if userinfo.result is None:
            warn("No such user: %s\n" % username)
            continue
        user_infos.append(userinfo.result)
    user_infos = list(filter(None, user_infos))

    calls = []
    with session.multicall() as m:
        for user in user_infos:
            results = []
            if not user:
                warn("No such user: %s\n" % user)
                continue
            results.append(m.getUserPerms(user['id']))
            results.append(m.listPackages(userID=user['id'], with_dups=True,
                                          queryOpts={'countOnly': True}))
            results.append(m.listTasks(opts={'owner': user['id'], 'parent': None},
                                       queryOpts={'countOnly': True}))
            results.append(m.listBuilds(userID=user['id'], queryOpts={'countOnly': True}))
            calls.append(results)

    for userinfo, (perms, pkgs, tasks, builds) in zip(user_infos, calls):
        print("User name: %s" % userinfo['name'])
        print("User ID: %d" % userinfo['id'])
        if 'krb_principals' in userinfo:
            print("krb principals:")
            for krb in userinfo['krb_principals']:
                print("  %s" % krb)
        if perms.result:
            print("Permissions:")
            for perm in perms.result:
                print("  %s" % perm)
        if userinfo.get('groups'):
            print("Groups:")
            for group in sorted(userinfo['groups']):
                print("  %s" % group)
        print("Status: %s" % koji.USER_STATUS[userinfo['status']])
        print("Usertype: %s" % koji.USERTYPES[userinfo['usertype']])
        print("Number of packages: %d" % pkgs.result)
        print("Number of tasks: %d" % tasks.result)
        print("Number of builds: %d" % builds.result)
        print('')


def anon_handle_repoinfo(goptions, session, args):
    "[info] Print basic information about a repo"
    usage = "usage: %prog repoinfo [options] <repo-id> [<repo-id> ...]"
    parser = OptionParser(usage=get_usage_str(usage))
    parser.add_option("--buildroots", action="store_true",
                      help="Prints list of buildroot IDs")
    (options, args) = parser.parse_args(args)
    if len(args) < 1:
        parser.error("Please specify a repo ID")
    ensure_connection(session, goptions)

    kojipath = koji.PathInfo(topdir=goptions.topurl)

    with session.multicall() as m:
        result = [m.repoInfo(repo_id, strict=False) for repo_id in args]

    for repo_id, repoinfo in zip(args, result):
        rinfo = repoinfo.result
        if not rinfo:
            warn("No such repo: %s\n" % repo_id)
            continue
        print('ID: %s' % rinfo['id'])
        print('Tag ID: %s' % rinfo['tag_id'])
        print('Tag name: %s' % rinfo['tag_name'])
        print('State: %s' % koji.REPO_STATES[rinfo['state']])
        print("Created: %s" % koji.formatTimeLong(rinfo['create_ts']))
        print('Created event: %s' % rinfo['create_event'])
        url = kojipath.repo(rinfo['id'], rinfo['tag_name'])
        print('URL: %s' % url)
        if rinfo['dist']:
            repo_json = os.path.join(
                kojipath.distrepo(rinfo['id'], rinfo['tag_name']), 'repo.json')
        else:
            repo_json = os.path.join(
                kojipath.repo(rinfo['id'], rinfo['tag_name']), 'repo.json')
        print('Repo json: %s' % repo_json)
        print("Dist repo?: %s" % (rinfo['dist'] and 'yes' or 'no'))
        print('Task ID: %s' % rinfo['task_id'])
        try:
            repo_buildroots = session.listBuildroots(repoID=rinfo['id'])
            count_buildroots = len(repo_buildroots)
            print('Number of buildroots: %i' % count_buildroots)
            if options.buildroots and count_buildroots > 0:
                repo_buildroots_id = [repo_buildroot['id'] for repo_buildroot in repo_buildroots]
                print('Buildroots ID:')
                for r_bldr_id in repo_buildroots_id:
                    print(' ' * 15 + '%s' % r_bldr_id)
        except koji.ParameterError:
            # repoID option added in 1.33
            if options.buildroots:
                warn("--buildroots option is available with hub 1.33 or newer")


def _format_ts(ts):
    if ts:
        return time.strftime("%y-%m-%d %H:%M:%S", time.localtime(ts))
    else:
        return ''


def anon_handle_scheduler_info(goptions, session, args):
    """[monitor] Show information about scheduling"""
    usage = "usage: %prog schedulerinfo [options]"
    parser = OptionParser(usage=get_usage_str(usage))
    parser.add_option("-t", "--task", action="store", type=int, default=None,
                      help="Limit data to given task id")
    parser.add_option("--host", action="store", default=None,
                      help="Limit data to given builder id")
    parser.add_option("--state", action="store", type='choice', default=None,
                      choices=[x for x in koji.TASK_STATES.keys()],
                      help="Limit data to task state")
    parser.add_option("--limit", action="store", type=int, default=100,
                      help="Limit data to last N items [default: %default]")
    (options, args) = parser.parse_args(args)
    if len(args) > 0:
        parser.error("This command takes no arguments")

    ensure_connection(session, goptions)

    host_id = None
    if options.host:
        try:
            host_id = int(options.host)
        except ValueError:
            host_id = session.getHost(options.host, strict=True)['id']

    # get the data
    clauses = []
    if options.task:
        clauses.append(('task_id', options.task))
    if options.host:
        clauses.append(('host_id', options.host))
    if options.state:
        clauses.append(('state', koji.TASK_STATES[options.state]))

    fields = ('id', 'task_id', 'host_name', 'state', 'create_ts', 'start_ts', 'completion_ts')
    kwargs = {'clauses': clauses, 'fields': fields}
    if session.hub_version < (1, 34, 0):
        error("Hub version is %s and doesn't support scheduler methods "
              "introduced in 1.34." % session.hub_version_str)
    if options.limit is not None:
        if session.hub_version >= (1, 34, 1):
            kwargs['opts'] = {'order': '-id', 'limit': options.limit}
    runs = session.scheduler.getTaskRuns(**kwargs)

    if options.limit is not None:
        if session.hub_version >= (1, 34, 1):
            # server did it for us, but we need to reverse
            runs = reversed(runs)
        else:
            # emulate limit
            runs = runs[-options.limit:]
    if session.hub_version < (1, 34, 1):
        # emulate order
        runs.sort(key=lambda r: r['id'])

    mask = '%(task_id)-9s %(host_name)-20s %(state)-7s ' \
           '%(create_ts)-17s %(start_ts)-17s %(completion_ts)-17s'
    if not goptions.quiet:
        header = mask % {
            'task_id': 'Task',
            'host_name': 'Host',
            'state': 'State',
            'create_ts': 'Created',
            'start_ts': 'Started',
            'completion_ts': 'Ended',
        }
        print(header)
        print('-' * len(header))
    for run in runs:
        run['state'] = koji.TASK_STATES[run['state']]
        for ts in ('create_ts', 'start_ts', 'completion_ts'):
            run[ts] = _format_ts(run[ts])
        print(mask % run)

    if host_id:
        print('Host data for %s:' % options.host)
        host_data = session.scheduler.getHostData(hostID=host_id)
        if len(host_data) > 0:
            print(host_data[0]['data'])
        else:
            print('-')


def handle_scheduler_logs(goptions, session, args):
    "[monitor] Query scheduler logs"
    usage = "usage: %prog scheduler-logs <options>"
    parser = OptionParser(usage=get_usage_str(usage))
    parser.add_option("--task", type="int", action="store",
                      help="Filter by task ID")
    parser.add_option("--host", type="str", action="store",
                      help="Filter by host (name/ID)")
    parser.add_option("--from", type="float", action="store", dest="from_ts",
                      help="Logs from given timestamp")
    parser.add_option("--to", type="float", action="store", dest="to_ts",
                      help="Logs until given timestamp (included)")
    parser.add_option("--limit", action="store", type=int, default=None,
                      help="Limit data to last N items. [default: %default]")
    (options, args) = parser.parse_args(args)
    if len(args) != 0:
        parser.error("There are no arguments for this command")
    if options.from_ts and options.to_ts and options.limit is not None:
        parser.error("If both --from and --to are used, --limit shouldn't be used")

    clauses = []
    if options.task:
        clauses.append(['task_id', options.task])
    if options.host:
        try:
            host_id = int(options.host)
        except ValueError:
            host_id = session.getHost(options.host)['id']
        clauses.append(['host_id', host_id])
    if options.from_ts:
        clauses.append(['msg_ts', '>=', options.from_ts])
    if options.to_ts:
        clauses.append(['msg_ts', '<', options.to_ts])

    fields = ('id', 'task_id', 'host_id', 'host_name', 'msg_ts', 'msg')
    kwargs = {'clauses': clauses, 'fields': fields}
    if session.hub_version < (1, 34, 0):
        error("Hub version is %s and doesn't support scheduler methods "
              "introduced in 1.34." % session.hub_version_str)
    if options.limit is not None:
        if session.hub_version >= (1, 34, 1):
            kwargs['opts'] = {'order': '-id', 'limit': options.limit}
    logs = session.scheduler.getLogMessages(**kwargs)

    if options.limit is not None:
        if session.hub_version >= (1, 34, 1):
            # server did it for us, but we need to reverse
            # don't use reversed() as it will be exhausted after modification loop later
            logs.reverse()
        else:
            # emulate limit
            logs = logs[-options.limit:]
    if session.hub_version < (1, 34, 1):
        # emulate order
        logs.sort(key=lambda r: r['id'])

    for log in logs:
        log['time'] = time.asctime(time.localtime(log['msg_ts']))

    mask = ("%(task_id)-10s %(host_name)-20s %(time)-25s %(msg)-30s")
    if not goptions.quiet:
        h = mask % {
            'task_id': 'Task',
            'host_name': 'Host',
            'time': 'Time',
            'msg': 'Message',
        }
        print(h)
        print('-' * len(h))

    for log in logs:
        print(mask % log)


def handle_promote_build(goptions, session, args):
    "[misc] Promote a draft build"
    usage = "usage: %prog promote-build [options] <draft-build>"
    parser = OptionParser(usage=get_usage_str(usage))
    parser.add_option('-f', '--force', action='store_true', default=False,
                      help='force operation')
    (options, args) = parser.parse_args(args)
    if len(args) != 1:
        parser.error("Please specify a draft build")
    draft_build = args[0]
    try:
        draft_build = int(draft_build)
    except ValueError:
        pass
    activate_session(session, goptions)
    if options.force and not session.hasPerm('admin'):
        parser.error("--force requires admin privilege")
    binfo = session.getBuild(draft_build)
    if not binfo:
        error("No such build: %s" % draft_build)
    if not binfo.get('draft'):
        error("Not a draft build: %s" % draft_build)
    rinfo = session.promoteBuild(binfo['id'], force=options.force)
    print("%s has been promoted to %s" % (binfo['nvr'], rinfo['nvr']))
