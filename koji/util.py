# Copyright (c) 2005-2007 Red Hat
#
#    Koji is free software; you can redistribute it and/or
#    modify it under the terms of the GNU Lesser General Public
#    License as published by the Free Software Foundation; 
#    version 2.1 of the License.
#
#    This software is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
#    Lesser General Public License for more details.
#
#    You should have received a copy of the GNU Lesser General Public
#    License along with this software; if not, write to the Free Software
#    Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301  USA

import time
import koji

def _changelogDate(cldate):
    return time.strftime('%a %b %d %Y', time.strptime(koji.formatTime(cldate), '%Y-%m-%d %H:%M:%S'))

def formatChangelog(entries):
    """Format a list of changelog entries (dicts)
    into a string representation."""
    result = ''
    for entry in entries:
        result += """* %s %s
%s

""" % (_changelogDate(entry['date']), entry['author'], entry['text'])

    return result

def checkForBuilds(session, tag, builds, event):
    """Check that the builds existed in tag at the time of the event."""
    for build in builds:
        tagged_list = session.listTagged(tag, event=event, package=build['name'], inherit=True)
        for tagged in tagged_list:
            if tagged['version'] == build['version'] and tagged['release'] == build['release']:
                break
        else:
            return False

    return True

def duration(start):
    """Return the duration between start and now in MM:SS format"""
    elapsed = time.time() - start
    mins = int(elapsed / 60)
    secs = int(elapsed % 60)
    return '%s:%02i' % (mins, secs)

def printList(l):
    """Print the contents of the list comma-separated"""
    if len(l) == 0:
        return ''
    elif len(l) == 1:
        return l[0]
    elif len(l) == 2:
        return ' and '.join(l)
    else:
        ret = ', '.join(l[:-1])
        ret += ', and '
        ret += l[-1]
        return ret

def eventFromOpts(session, opts):
    """Determine event id from standard cli options

    Standard options are:
        event: an event id (int)
        ts: an event timestamp (int)
        repo: pull event from given repo
    """
    event_id = getattr(opts, 'event')
    if event_id:
        return session.getEvent(event_id)
    ts = getattr(opts, 'ts')
    if ts:
        return session.getLastEvent(before=ts)
    repo = getattr(opts, 'repo')
    if repo:
        rinfo = session.repoInfo(repo)
        if rinfo:
            return {'id' : rinfo['create_event'],
                    'ts' : rinfo['create_ts'] }
    return None
