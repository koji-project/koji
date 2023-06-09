# coding: utf-8
# Copyright © 2019 Red Hat, Inc.
#
# SPDX-License-Identifier: GPL-2.0-or-later

from __future__ import absolute_import

from optparse import OptionParser

import koji
from koji.plugin import export_cli
from koji_cli.commands import anon_handle_wait_repo
from koji_cli.lib import activate_session, arg_filter


@export_cli
def handle_add_sidetag(options, session, args):
    "Create sidetag"
    usage = "%prog add-sidetag [options] <basetag>"
    usage += "\n(Specify the --help global option for a list of other help options)"
    parser = OptionParser(usage=usage)
    parser.add_option("-q", "--quiet", action="store_true", help="Do not print tag name",
                      default=options.quiet)
    parser.add_option("-w", "--wait", action="store_true", help="Wait until repo is ready.")
    parser.add_option("--debuginfo", action="store_true",
                      help="Buildroot repo will contain debuginfos")
    parser.add_option("--suffix", action="store", help="Suffix from hub-supported ones")

    (opts, args) = parser.parse_args(args)

    if len(args) != 1:
        parser.error("Only argument is basetag")
    basetag = args[0]

    activate_session(session, options)

    kwargs = {"debuginfo": opts.debuginfo}
    if opts.suffix:
        kwargs['suffix'] = opts.suffix
    try:
        tag = session.createSideTag(basetag, **kwargs)
    except koji.ActionNotAllowed:
        parser.error("Policy violation")
    except koji.ParameterError as ex:
        if 'suffix' in str(ex):
            parser.error("Hub is older and doesn't support --suffix, please run it without it")
        else:
            raise

    if not opts.quiet:
        print(tag["name"])

    if opts.wait:
        args = ["--target", tag["name"]]
        if opts.quiet:
            args.append("--quiet")
        anon_handle_wait_repo(options, session, args)


@export_cli
def handle_remove_sidetag(options, session, args):
    "Remove sidetag"
    usage = "%prog remove-sidetag [options] <sidetag> ..."
    usage += "\n(Specify the --help global option for a list of other help options)"
    parser = OptionParser(usage=usage)
    (opts, args) = parser.parse_args(args)

    if len(args) < 1:
        parser.error("Sidetag argument is required")

    activate_session(session, options)

    session.multicall = True
    for sidetag in args:
        session.removeSideTag(sidetag)
    session.multiCall(strict=True)


@export_cli
def handle_list_sidetags(options, session, args):
    "List sidetags"
    usage = "%prog list-sidetags [options]"
    usage += "\n(Specify the --help global option for a list of other help options)"
    parser = OptionParser(usage=usage)
    parser.add_option("--basetag", action="store", help="Filter on basetag")
    parser.add_option("--user", action="store", help="Filter on user")
    parser.add_option("--mine", action="store_true", help="Filter on user")

    (opts, args) = parser.parse_args(args)

    if len(args) > 0:
        parser.error("This command takes no arguments")

    if opts.mine and opts.user:
        parser.error("Specify only one from --user --mine")

    if opts.mine:
        activate_session(session, options)
        user = session.getLoggedInUser()["name"]
    else:
        user = opts.user

    for tag in session.listSideTags(basetag=opts.basetag, user=user):
        print(tag["name"])


@export_cli
def handle_edit_sidetag(options, session, args):
    "Edit sidetag"
    usage = "%prog edit-sidetag [options] <sidetag>"
    usage += "\n(Specify the --help global option for a list of other help options)"
    parser = OptionParser(usage=usage)
    parser.add_option("--debuginfo", action="store_true", default=None,
                      help="Generate debuginfo repository")
    parser.add_option("--no-debuginfo", action="store_false", dest="debuginfo")
    parser.add_option("--rpm-macro", action="append", default=[], metavar="key=value",
                      dest="rpm_macros", help="Set tag-specific rpm macros")
    parser.add_option("--remove-rpm-macro", action="append", default=[], metavar="key",
                      dest="remove_rpm_macros", help="Remove rpm macros")

    (opts, args) = parser.parse_args(args)

    if len(args) != 1:
        parser.error("Only argument is sidetag")
    sidetag = args[0]

    if opts.debuginfo is None and not opts.rpm_macros and not opts.remove_rpm_macros:
        parser.error("At least one option needs to be specified")

    activate_session(session, options)

    kwargs = {}
    if opts.debuginfo is not None:
        kwargs['debuginfo'] = opts.debuginfo

    if opts.rpm_macros:
        rpm_macros = {}
        for xopt in opts.rpm_macros:
            key, value = xopt.split('=', 1)
            value = arg_filter(value)
            rpm_macros[key] = value
        kwargs['rpm_macros'] = rpm_macros

    if opts.remove_rpm_macros:
        kwargs['remove_rpm_macros'] = opts.remove_rpm_macros

    session.editSideTag(sidetag, **kwargs)
