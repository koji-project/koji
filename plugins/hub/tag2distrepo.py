# Koji tag2distrepo hub plugin
# Copyright (c) 2019 Red Hat, Inc.
# This callback automatically schedules distrepo tasks based on a tags config
#
# Authors:
#   Patrick Uiterwijk <puiterwijk@redhat.com>

from __future__ import absolute_import
from koji.plugin import callback
from kojihub import dist_repo_init, make_task, readTaggedRPMS, write_signed_rpm
import logging


@callback('postTag', 'postUntag')
def tag2distrepo(cbtype, tag, build, user, force=False, strict=True):
    logger = logging.getLogger('koji.plugin.tag2distrepo')

    if not tag['extra'].get("tag2distrepo.enabled"):
        logger.debug("No tag2distrepo enabled for tag %s" % tag['name'])
        return
    if not tag['arches']:
        raise ValueError(
            "Tag %s has no arches configured but tag2distrepo is enabled" % tag['name'])

    keys = tag['extra'].get("tag2distrepo.keys", '').split()
    inherit = tag['extra'].get("tag2distrepo.inherit", False)
    latest = tag['extra'].get("tag2distrepo.latest", False)
    split_debuginfo = tag['extra'].get("tag2distrepo.split_debuginfo", False)

    if keys:
        logger.debug("Ensuring signed RPMs are written out")
        [rpms, _] = readTaggedRPMS(tag['id'], rpmsigs=True)
        for rpm in rpms:
            for key in keys:
                if rpm['sigkey'] == key:
                    write_signed_rpm(rpm['id'], key, False)

    task_opts = {
        'arch': tag['arches'].split(),
        'comp': None,
        'delta': [],
        'event': None,
        'inherit': inherit,
        'latest': latest,
        'multilib': False,
        'split_debuginfo': split_debuginfo,
        'skip_missing_signatures': False,
        'allow_missing_signatures': not keys,
    }
    logger.debug(
        "Scheduling distRepo for tag %s, keys %s",
        tag['name'],
        keys,
    )

    repo_id, event_id = dist_repo_init(tag['name'], keys, task_opts)
    task_opts['event'] = event_id
    task_id = make_task(
        'distRepo',
        [tag['name'], repo_id, keys, task_opts],
        priority=15,
        channel='createrepo',
    )
    logger.info("distRepo task %d scheduled for tag %s" % (task_id, tag['name']))
