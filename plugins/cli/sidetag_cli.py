# coding: utf-8
# Copyright © 2019 Red Hat, Inc.
#
# SPDX-License-Identifier: GPL-2.0-or-later

from __future__ import absolute_import

from argparse import ArgumentParser

import koji
from koji.plugin import export_cli
from koji_cli.commands import anon_handle_wait_repo
from koji_cli.lib import _, activate_session, arg_filter


@export_cli
def handle_add_sidetag(options, session, args):
    "Create sidetag"
    usage = _("%(prog)s add-sidetag [options] <basetag>")
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
    parser.add_argument(
        "--suffix", action="store", help=_("Suffix from hub-supported ones")
    )

    opts = parser.parse_args(args)

    activate_session(session, options)

    kwargs = {"debuginfo": opts.debuginfo}
    if opts.suffix:
        kwargs['suffix'] = opts.suffix
    try:
        tag = session.createSideTag(opts.basetag, **kwargs)
    except koji.ActionNotAllowed:
        parser.error(_("Policy violation"))
    except koji.ParameterError as ex:
        if 'suffix' in str(ex):
            parser.error(_("Hub is older and doesn't support --suffix, please run it without it"))
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
    usage = _("%(prog)s remove-sidetag [options] <sidetag> ...")
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
    usage = _("%(prog)s list-sidetags [options]")
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


@export_cli
def handle_edit_sidetag(options, session, args):
    "Edit sidetag"
    usage = _("%(prog)s edit-sidetag [options]")
    usage += _("\n(Specify the --help global option for a list of other help options)")
    parser = ArgumentParser(usage=usage)
    parser.add_argument("sidetag", help="name of sidetag")
    parser.add_argument("--debuginfo", action="store_true", default=None,
                        help=_("Generate debuginfo repository"))
    parser.add_argument("--no-debuginfo", action="store_false", dest="debuginfo")
    parser.add_argument("--rpm-macro", action="append", default=[], metavar="key=value",
                        dest="rpm_macros", help=_("Set tag-specific rpm macros"))
    parser.add_argument("--remove-rpm-macro", action="append", default=[], metavar="key",
                        dest="remove_rpm_macros", help=_("Remove rpm macros"))

    opts = parser.parse_args(args)

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

    session.editSideTag(opts.sidetag, **kwargs)
