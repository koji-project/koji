# coding: utf-8
# Copyright © 2019 Red Hat, Inc.
#
# SPDX-License-Identifier: GPL-2.0-or-later

from __future__ import absolute_import

from argparse import ArgumentParser

import koji
from koji.plugin import export_cli
from koji_cli.commands import anon_handle_wait_repo
from koji_cli.lib import _, activate_session


@export_cli
def handle_add_sidetag(options, session, args):
    "Create sidetag"
    usage = _("usage: %(prog)s add-sidetag [options] <basetag>")
    usage += _("\n(Specify the --help global option for a list of other help options)")
    parser = ArgumentParser(usage=usage)
    parser.add_argument("basetag", help="name of basetag")
    parser.add_argument(
        "-q",
        "--quiet",
        action="store_true",
        help=_("Do not print tag name"),
        default=options.quiet,
    )
    parser.add_argument(
        "-w", "--wait", action="store_true", help=_("Wait until repo is ready.")
    )
    parser.add_argument(
        "--debuginfo", action="store_true", help=_("Buildroot repo will contain debuginfos")
    )

    opts = parser.parse_args(args)

    activate_session(session, options)

    try:
        tag = session.createSideTag(opts.basetag, debuginfo=opts.debuginfo)
    except koji.ActionNotAllowed:
        parser.error(_("Policy violation"))

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
    usage = _("usage: %(prog)s remove-sidetag [options] <sidetag> ...")
    usage += _("\n(Specify the --help global option for a list of other help options)")
    parser = ArgumentParser(usage=usage)
    parser.add_argument("sidetags", help="name of sidetag", nargs="+")
    opts = parser.parse_args(args)

    activate_session(session, options)

    session.multicall = True
    for sidetag in opts.sidetags:
        session.removeSideTag(sidetag)
    session.multiCall(strict=True)


@export_cli
def handle_list_sidetags(options, session, args):
    "List sidetags"
    usage = _("usage: %(prog)s list-sidetags [options]")
    usage += _("\n(Specify the --help global option for a list of other help options)")
    parser = ArgumentParser(usage=usage)
    parser.add_argument("--basetag", action="store", help=_("Filter on basetag"))
    parser.add_argument("--user", action="store", help=_("Filter on user"))
    parser.add_argument("--mine", action="store_true", help=_("Filter on user"))

    opts = parser.parse_args(args)

    if opts.mine and opts.user:
        parser.error(_("Specify only one from --user --mine"))

    if opts.mine:
        activate_session(session, options)
        user = session.getLoggedInUser()["name"]
    else:
        user = opts.user

    for tag in session.listSideTags(basetag=opts.basetag, user=user):
        print(tag["name"])
