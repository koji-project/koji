# Copyright © 2019 Red Hat, Inc.
#
# SPDX-License-Identifier: GPL-2.0-or-later
import sys

import koji
import koji.policy
from koji.context import context
from koji.plugin import callback, export
sys.path.insert(0, "/usr/share/koji-hub/")
from kojihub import (  # noqa: E402
    QueryProcessor,
    _create_build_target,
    _create_tag,
    _delete_build_target,
    _delete_tag,
    _edit_tag,
    assert_policy,
    get_build_target,
    readInheritanceData,
    get_tag,
    get_user,
    nextval,
    policy_get_user
)

CONFIG_FILE = "/etc/koji-hub/plugins/sidetag.conf"
CONFIG = None


def is_sidetag(taginfo, raise_error=False):
    """Check, that given tag is sidetag"""
    result = bool(taginfo['extra'].get('sidetag'))
    if not result and raise_error:
        raise koji.GenericError("Not a sidetag: %(name)s" % taginfo)

    return result


def is_sidetag_owner(taginfo, user, raise_error=False):
    """Check, that given user is owner of the sidetag"""
    result = (taginfo['extra'].get('sidetag') and
              (taginfo['extra'].get('sidetag_user_id') == user['id'] or
               context.session.hasPerm('admin')))
    if not result and raise_error:
        raise koji.ActionNotAllowed("This is not your sidetag")

    return result


# Policy tests
class SidetagTest(koji.policy.MatchTest):
    """Checks, if tag is a sidetag"""
    name = 'is_sidetag'

    def run(self, data):
        tag = get_tag(data['tag'])
        return is_sidetag(tag)


class SidetagOwnerTest(koji.policy.MatchTest):
    """Checks, if user is a real owner of sidetag"""
    name = 'is_sidetag_owner'

    def run(self, data):
        user = policy_get_user(data)
        tag = get_tag(data['tag'])
        return is_sidetag_owner(tag, user)


# API calls
@export
def createSideTag(basetag, debuginfo=False):
    """Create a side tag.

    :param basetag: name or ID of base tag
    :type basetag: str or int

    :param debuginfo: should buildroot repos contain debuginfo?
    :type debuginfo: bool
    """

    # Any logged-in user is able to request creation of side tags,
    # as long the request meets the policy.
    context.session.assertLogin()
    user = get_user(context.session.user_id, strict=True)

    basetag = get_tag(basetag, strict=True)

    query = QueryProcessor(
        tables=["tag_extra"],
        clauses=["key='sidetag_user_id'", "value=%(user_id)s", "active IS TRUE"],
        columns=["COUNT(*)"],
        aliases=["user_tags"],
        values={"user_id": str(user["id"])},
    )
    user_tags = query.executeOne()
    if user_tags is None:
        # should not ever happen
        raise koji.GenericError("Unknown db error")

    # Policy is a very flexible mechanism, that can restrict for which
    # tags sidetags can be created, or which users can create sidetags etc.
    assert_policy(
        "sidetag", {"tag": basetag["id"], "number_of_tags": user_tags["user_tags"]}
    )

    # ugly, it will waste one number in tag_id_seq, but result will match with
    # id assigned by _create_tag
    tag_id = nextval("tag_id_seq") + 1
    sidetag_name = "%s-side-%s" % (basetag["name"], tag_id)
    extra = {
        "sidetag": True,
        "sidetag_user": user["name"],
        "sidetag_user_id": user["id"],
    }
    if debuginfo:
        extra['with_debuginfo'] = True
    sidetag_id = _create_tag(
        sidetag_name,
        parent=basetag["id"],
        arches=basetag["arches"],
        extra=extra,
    )
    _create_build_target(sidetag_name, sidetag_id, sidetag_id)

    return {"name": sidetag_name, "id": sidetag_id}


@export
def removeSideTag(sidetag):
    """Remove a side tag

    :param sidetag: id or name of sidetag
    :type sidetag: int or str
    """
    context.session.assertLogin()
    user = get_user(context.session.user_id, strict=True)
    sidetag = get_tag(sidetag, strict=True)

    # sanity/access
    is_sidetag(sidetag, raise_error=True)
    is_sidetag_owner(sidetag, user, raise_error=True)

    _remove_sidetag(sidetag)


def _remove_sidetag(sidetag):
    # check target
    target = get_build_target(sidetag["name"])
    if not target:
        raise koji.GenericError("Target is missing for sidetag")
    if target["build_tag"] != sidetag["id"] or target["dest_tag"] != sidetag["id"]:
        raise koji.GenericError("Target does not match sidetag")

    _delete_build_target(target["id"])
    _delete_tag(sidetag["id"])


@export
def listSideTags(basetag=None, user=None, queryOpts=None):
    """List all sidetags with additional filters

    :param basetag: filter by basteag id or name
    :type basetag: int or str
    :param user: filter by userid or username
    :type user: int or str
    :param queryOpts: additional query options
                      {countOnly, order, offset, limit}
    :type queryOpts: dict

    :returns: list of dicts: id, name, user_id, user_name
    """
    # te1.sidetag
    # te2.user_id
    # te3.basetag
    if user is not None:
        user_id = str(get_user(user, strict=True)["id"])
    else:
        user_id = None
    if basetag is not None:
        basetag_id = get_tag(basetag, strict=True)["id"]
    else:
        basetag_id = None

    joins = [
        "LEFT JOIN tag_extra AS te1 ON tag.id = te1.tag_id",
        "LEFT JOIN tag_extra AS te2 ON tag.id = te2.tag_id",
        "LEFT JOIN users ON CAST(te2.value AS INTEGER) = users.id",
    ]
    clauses = [
        "te1.active IS TRUE",
        "te1.key = 'sidetag'",
        "te1.value = 'true'",
        "te2.active IS TRUE",
        "te2.key = 'sidetag_user_id'"
    ]
    if user_id:
        clauses.append("te2.value = %(user_id)s")
    if basetag_id:
        joins.append("LEFT JOIN tag_inheritance ON tag.id = tag_inheritance.tag_id")
        clauses.extend(
            [
                "tag_inheritance.active IS TRUE",
                "tag_inheritance.parent_id = %(basetag_id)s",
            ]
        )

    query = QueryProcessor(
        tables=["tag"],
        clauses=clauses,
        columns=["tag.id", "tag.name", "te2.value", "users.name"],
        aliases=["id", "name", "user_id", "user_name"],
        joins=joins,
        values={"basetag_id": basetag_id, "user_id": user_id},
        opts=queryOpts,
    )
    return query.execute()


@export
def editSideTag(sidetag, debuginfo=None, rpm_macros=None, remove_rpm_macros=None):
    """Restricted ability to modify sidetags, parent tag must have:
    sidetag_debuginfo_allowed: 1
    sidetag_rpm_macros_allowed: 1
    in extra, if modifying functions should work. For blocking/unblocking
    further policy must be compatible with these operations.

    :param sidetag: sidetag id or name
    :type sidetag: int or str
    :param debuginfo: set or disable debuginfo repo generation
    :type debuginfo: bool
    :param rpm_macros: add/update rpms macros in extra
    :type rpm_macros: dict
    :param remove_rpm_macros: remove rpm macros from extra
    :type remove_rpm_macros: list of str
    """

    context.session.assertLogin()
    user = get_user(context.session.user_id, strict=True)
    sidetag = get_tag(sidetag, strict=True)

    # sanity/access
    is_sidetag(sidetag, raise_error=True)
    is_sidetag_owner(sidetag, user, raise_error=True)

    parent_id = readInheritanceData(sidetag['id'])[0]['parent_id']
    parent = get_tag(parent_id)

    if debuginfo is not None and not parent['extra'].get('sidetag_debuginfo_allowed'):
        raise koji.GenericError("Debuginfo setting is not allowed in parent tag.")

    if (rpm_macros is not None or remove_rpm_macros is not None) \
            and not parent['extra'].get('sidetag_rpm_macros_allowed'):
        raise koji.GenericError("RPM macros change is not allowed in parent tag.")

    kwargs = {'extra': {}}
    if debuginfo is not None:
        kwargs['extra']['with_debuginfo'] = bool(debuginfo)
    if rpm_macros is not None:
        for macro, value in rpm_macros.items():
            kwargs['extra']['rpm.macro.%s' % macro] = value
    if remove_rpm_macros is not None:
        kwargs['remove_extra'] = ['rpm.macro.%s' % m for m in remove_rpm_macros]

    _edit_tag(sidetag['id'], **kwargs)


def handle_sidetag_untag(cbtype, *args, **kws):
    """Remove a side tag when its last build is untagged

    Note, that this is triggered only in case, that some build exists. For
    never used tags, some other policy must be applied. Same holds for users
    which don't untag their builds.
    """
    if "tag" not in kws:
        # shouldn't happen, but...
        return
    tag = get_tag(kws["tag"]["id"], strict=False)
    if not tag:
        # also shouldn't happen, but just in case
        return
    if not is_sidetag(tag):
        return
    # is the tag now empty?
    query = QueryProcessor(
        tables=["tag_listing"],
        clauses=["tag_id = %(tag_id)s", "active IS TRUE"],
        values={"tag_id": tag["id"]},
        opts={"countOnly": True},
    )
    if query.execute():
        return
    # looks like we've just untagged the last build from a side tag
    try:
        # XXX: are we double updating tag_listing?
        _remove_sidetag(tag)
    except koji.GenericError:
        pass


# read config and register
if not CONFIG:
    CONFIG = koji.read_config_files(CONFIG_FILE)
    if CONFIG.has_option("sidetag", "remove_empty") and CONFIG.getboolean(
        "sidetag", "remove_empty"
    ):
        handle_sidetag_untag = callback("postUntag")(handle_sidetag_untag)
