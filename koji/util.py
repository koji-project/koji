# Copyright (c) 2005-2014 Red Hat, Inc.
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
#
# Authors:
#       Mike McLean <mikem@redhat.com>
#       Mike Bonnet <mikeb@redhat.com>

import calendar
from fnmatch import fnmatch
import koji
import logging
import os
import os.path
import re
import resource
import stat
import sys
import time
import ConfigParser
from zlib import adler32

try:
    from hashlib import md5 as md5_constructor
except ImportError:
    from md5 import new as md5_constructor
try:
    from hashlib import sha1 as sha1_constructor
except ImportError:
    from sha import new as sha1_constructor

def _changelogDate(cldate):
    return time.strftime('%a %b %d %Y', time.strptime(koji.formatTime(cldate), '%Y-%m-%d %H:%M:%S'))

def formatChangelog(entries):
    """Format a list of changelog entries (dicts)
    into a string representation."""
    result = ''
    for entry in entries:
        result += """* %s %s
%s

""" % (_changelogDate(entry['date']), entry['author'].encode("utf-8"),
       entry['text'].encode("utf-8"))

    return result

DATE_RE = re.compile(r'(\d+)-(\d+)-(\d+)')
TIME_RE = re.compile(r'(\d+):(\d+):(\d+)')

def parseTime(val):
    """
    Parse a string time in either "YYYY-MM-DD HH24:MI:SS" or "YYYY-MM-DD"
    format into floating-point seconds since the epoch.  If the time portion
    is not specified, it will be padded with zeros.  The string time is treated
    as UTC.  If the time string cannot be parsed into a valid date, None will be
    returned.
    """
    result = DATE_RE.search(val)
    if not result:
        return None
    else:
        date = [int(r) for r in result.groups()]
    time = [0, 0, 0]
    rest = val[result.end():].strip()
    result = TIME_RE.search(rest)
    if result:
        time = [int(r) for r in result.groups()]
    return calendar.timegm(date + time + [0, 0, 0])

def checkForBuilds(session, tag, builds, event, latest=False):
    """Check that the builds existed in tag at the time of the event.
       If latest=True, check that the builds are the latest in tag."""
    for build in builds:
        if latest:
            tagged_list = session.getLatestBuilds(tag, event=event, package=build['name'])
        else:
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

def multi_fnmatch(s, patterns):
    """Returns true if s matches any pattern in the list

    If patterns is a string, it will be split() first
    """
    if isinstance(patterns, basestring):
        patterns = patterns.split()
    for pat in patterns:
        if fnmatch(s, pat):
            return True
    return False

def dslice(dict, keys, strict=True):
    """Returns a new dictionary containing only the specified keys"""
    ret = {}
    for key in keys:
        if strict or dict.has_key(key):
            #for strict we skip the has_key check and let the dict generate the KeyError
            ret[key] = dict[key]
    return ret

def dslice_ex(dict, keys, strict=True):
    """Returns a new dictionary with only the specified keys removed"""
    ret = dict.copy()
    for key in keys:
        if strict or ret.has_key(key):
            del ret[key]
    return ret

def call_with_argcheck(func, args, kwargs=None):
    """Call function, raising ParameterError if args do not match"""
    if kwargs is None:
        kwargs = {}
    try:
        return func(*args, **kwargs)
    except TypeError, e:
        if sys.exc_info()[2].tb_next is None:
            # The stack is only one high, so the error occurred in this function.
            # Therefore, we assume the TypeError is due to a parameter mismatch
            # in the above function call.
            raise koji.ParameterError, str(e)
        raise


class HiddenValue(object):
    """A wrapper that prevents a value being accidentally printed"""

    def __init__(self, value):
        if isinstance(value, HiddenValue):
            self.value = value.value
        else:
            self.value = value

    def __str__(self):
        return "[value hidden]"

    def __repr__(self):
        return "HiddenValue()"


class LazyValue(object):
    """Used to represent a value that is generated by a function call at access time
    """

    def __init__(self, func, args, kwargs=None, cache=False):
        if kwargs is None:
            kwargs = {}
        self.func = func
        self.args = args
        self.kwargs = kwargs
        self.cache = cache

    def get(self):
        if hasattr(self, '_value'):
            return self._value
        value = self.func(*self.args, **self.kwargs)
        if self.cache:
            self._value = value
        return value


class LazyString(LazyValue):
    """Lazy values that should be expanded when printed"""

    def __str__(self):
        return str(self.get())


def lazy_eval(value):
    if isinstance(value, LazyValue):
        return value.get()
    return value


class LazyDict(dict):
    """A container for lazy data

    fields can refer to function calls, which can optionally be cached
    """

    def __getitem__(self, key):
        return lazy_eval(super(LazyDict, self).__getitem__(key))

    def lazyset(self, key, func, args, kwargs=None, cache=False):
        self[key] = LazyValue(func, args, kwargs=kwargs, cache=cache)

    def get(self, *args, **kwargs):
        return lazy_eval(super(LazyDict, self).get(*args, **kwargs))

    def copy(self):
        return LazyDict(self)

    def values(self):
        return [lazy_eval(val) for val in super(LazyDict, self).values()]

    def items(self):
        return [(key, lazy_eval(val)) for key, val in super(LazyDict, self).items()]

    def itervalues(self):
        for val in super(LazyDict, self).itervalues():
            yield lazy_eval(val)

    def iteritems(self):
        for key, val in super(LazyDict, self).iteritems():
            yield key, lazy_eval(val)

    def pop(self, key, *args, **kwargs):
        return lazy_eval(super(LazyDict, self).pop(key, *args, **kwargs))

    def popitem(self):
        key, val = super(LazyDict, self).popitem()
        return key, lazy_eval(val)


class LazyRecord(object):
    """A object whose attributes can reference lazy data

    Use lazysetattr to set lazy attributes, or just set them to a LazyValue
    object directly"""

    def __init__(self, base=None):
        if base is not None:
            self.__dict__.update(base.__dict__)
        self._base_record = base

    def __getattribute__(self, name):
        try:
            val = object.__getattribute__(self, name)
        except AttributeError:
            base = object.__getattribute__(self, '_base_record')
            val = getattr(base, name)
        return lazy_eval(val)


def lazysetattr(object, name, func, args, kwargs=None, cache=False):
    if not isinstance(object, LazyRecord):
        raise TypeError, 'object does not support lazy attributes'
    value = LazyValue(func, args, kwargs=kwargs, cache=cache)
    setattr(object, name, value)


def rmtree(path):
    """Delete a directory tree without crossing fs boundaries"""
    st = os.lstat(path)
    if not stat.S_ISDIR(st.st_mode):
        raise koji.GenericError, "Not a directory: %s" % path
    dev = st.st_dev
    dirlist = []
    for dirpath, dirnames, filenames in os.walk(path):
        dirlist.append(dirpath)
        newdirs = []
        dirsyms = []
        for fn in dirnames:
            path = os.path.join(dirpath, fn)
            st = os.lstat(path)
            if st.st_dev != dev:
                # don't cross fs boundary
                continue
            if stat.S_ISLNK(st.st_mode):
                #os.walk includes symlinks to dirs here
                dirsyms.append(fn)
                continue
            newdirs.append(fn)
        #only walk our filtered dirs
        dirnames[:] = newdirs
        for fn in filenames + dirsyms:
            path = os.path.join(dirpath, fn)
            st = os.lstat(path)
            if st.st_dev != dev:
                #shouldn't happen, but just to be safe...
                continue
            os.unlink(path)
    dirlist.reverse()
    for dirpath in dirlist:
        if os.listdir(dirpath):
            # dir not empty. could happen if a mount was present
            continue
        os.rmdir(dirpath)

def _relpath(path, start=getattr(os.path, 'curdir', '.')):
    """Backport of os.path.relpath for python<2.6"""

    sep = getattr(os.path, 'sep', '/')
    pardir = getattr(os.path, 'pardir', '..')
    if not path:
        raise ValueError("no path specified")
    start_list = [x for x in os.path.abspath(start).split(sep) if x]
    path_list = [x for x in os.path.abspath(path).split(sep) if x]
    i = -1
    for i in range(min(len(start_list), len(path_list))):
        if start_list[i] != path_list[i]:
            break
    else:
        i += 1
    rel_list = [pardir] * (len(start_list)-i) + path_list[i:]
    if not rel_list:
        return getattr(os.path, 'curdir', '.')
    return os.path.join(*rel_list)

relpath = getattr(os.path, 'relpath', _relpath)

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

def filedigestAlgo(hdr):
    """
    Get the file digest algorithm used in hdr.
    If there is no algorithm flag in the header,
    default to md5.  If the flag contains an unknown,
    non-None value, return 'unknown'.
    """
    # need to use the header ID hard-coded into Koji so we're not dependent on the
    # version of rpm installed on the hub
    digest_algo_id = hdr[koji.RPM_TAG_FILEDIGESTALGO]
    if not digest_algo_id:
        # certain versions of rpm return an empty list instead of None
        # for missing header fields
        digest_algo_id = None
    digest_algo = koji.RPM_FILEDIGESTALGO_IDS.get(digest_algo_id, 'unknown')
    return digest_algo.lower()

def parseStatus(rv, prefix):
    if isinstance(prefix, list) or isinstance(prefix, tuple):
        prefix = ' '.join(prefix)
    if os.WIFSIGNALED(rv):
        return '%s was killed by signal %i' % (prefix, os.WTERMSIG(rv))
    elif os.WIFEXITED(rv):
        return '%s exited with status %i' % (prefix, os.WEXITSTATUS(rv))
    else:
        return '%s terminated for unknown reasons' % prefix

def isSuccess(rv):
    """Return True if rv indicates successful completion
    (exited with status 0), False otherwise."""
    if os.WIFEXITED(rv) and os.WEXITSTATUS(rv) == 0:
        return True
    else:
        return False

def setup_rlimits(opts, logger=None):
    logger = logger or logging.getLogger("koji")
    for key in opts:
        if not key.startswith('RLIMIT_') or not opts[key]:
            continue
        rcode = getattr(resource, key, None)
        if rcode is None:
            continue
        orig = resource.getrlimit(rcode)
        try:
            limits = [int(x) for x in opts[key].split()]
        except ValueError:
            logger.error("Invalid resource limit: %s=%s", key, opts[key])
            continue
        if len(limits) not in (1,2):
            logger.error("Invalid resource limit: %s=%s", key, opts[key])
            continue
        if len(limits) == 1:
            limits.append(orig[1])
        logger.warn('Setting resource limit: %s = %r', key, limits)
        try:
            resource.setrlimit(rcode, tuple(limits))
        except ValueError, e:
            logger.error("Unable to set %s: %s", key, e)

class adler32_constructor(object):

    #mimicing the hashlib constructors
    def __init__(self, arg=''):
        self._value = adler32(arg) & 0xffffffffL
        #the bitwise and works around a bug in some versions of python
        #see: http://bugs.python.org/issue1202

    def update(self, arg):
        self._value = adler32(arg, self._value) & 0xffffffffL

    def digest(self):
        return self._value

    def hexdigest(self):
        return "%08x" % self._value

    def copy(self):
        dup = adler32_constructor()
        dup._value = self._value
        return dup

    digest_size = 4
    block_size = 1      #I think

def tsort(parts):
    """Given a partial ordering, return a totally ordered list.

    part is a dict of partial orderings.  Each value is a set,
    which the key depends on.

    The return value is a list of sets, each of which has only
    dependencies on items in previous entries in the list."""
    parts = parts.copy()
    result = []
    while True:
        level = set([name for name, deps in parts.iteritems() if not deps])
        if not level:
            break
        result.append(level)
        parts = dict([(name, deps - level) for name, deps in parts.iteritems()
                      if name not in level])
    if parts:
        raise ValueError, 'total ordering not possible'
    return result

class MavenConfigOptAdapter(object):
    """
    Wrap a ConfigParser so it looks like a optparse.Values instance
    used by maven-build.
    """
    MULTILINE = ['properties', 'envs']
    MULTIVALUE = ['goals', 'profiles', 'packages',
                   'jvm_options', 'maven_options', 'buildrequires']

    def __init__(self, conf, section):
        self._conf = conf
        self._section = section

    def __getattr__(self, name):
        if self._conf.has_option(self._section, name):
            value = self._conf.get(self._section, name)
            if name in self.MULTIVALUE:
                value = value.split()
            elif name in self.MULTILINE:
                value = value.splitlines()
            return value
        raise AttributeError, name

def maven_opts(values, chain=False, scratch=False):
    """
    Convert the argument (an optparse.Values object) to a dict of build options
    suitable for passing to maven-build or maven-chain.
    """
    opts = {}
    for key in ('scmurl', 'patches', 'specfile', 'goals', 'profiles', 'packages',
                'jvm_options', 'maven_options'):
        val = getattr(values, key, None)
        if val:
            opts[key] = val
    props = {}
    for prop in getattr(values, 'properties', []):
        fields = prop.split('=', 1)
        if len(fields) != 2:
            fields.append(None)
        props[fields[0]] = fields[1]
    if props:
        opts['properties'] = props
    envs = {}
    for env in getattr(values, 'envs', []):
        fields = env.split('=', 1)
        if len(fields) != 2:
            raise ValueError, "Environment variables must be in NAME=VALUE format"
        envs[fields[0]] = fields[1]
    if envs:
        opts['envs'] = envs
    if chain:
        val = getattr(values, 'buildrequires', [])
        if val:
            opts['buildrequires'] = val
    if scratch and not chain:
        opts['scratch'] = True
    return opts

def maven_params(config, package, chain=False, scratch=False):
    values = MavenConfigOptAdapter(config, package)
    return maven_opts(values, chain=chain, scratch=scratch)

def wrapper_params(config, package, chain=False, scratch=False):
    params = {}
    values = MavenConfigOptAdapter(config, package)
    params['type'] = getattr(values, 'type', None)
    params['scmurl'] = getattr(values, 'scmurl', None)
    params['buildrequires'] = getattr(values, 'buildrequires', [])
    if not scratch:
        params['create_build'] = True
    return params

def parse_maven_params(confs, chain=False, scratch=False):
    """
    Parse .ini files that contain parameters to launch a Maven build.

    Return a map whose keys are package names and values are config parameters.
    """
    if not isinstance(confs, (list, tuple)):
        confs = [confs]
    config = ConfigParser.ConfigParser()
    for conf in confs:
        conf_fd = file(conf)
        config.readfp(conf_fd)
        conf_fd.close()
    builds = {}
    for package in config.sections():
        params = {}
        buildtype = 'maven'
        if config.has_option(package, 'type'):
            buildtype = config.get(package, 'type')
        if buildtype == 'maven':
            params = maven_params(config, package, chain=chain, scratch=scratch)
        elif buildtype == 'wrapper':
            params = wrapper_params(config, package, chain=chain, scratch=scratch)
            if len(params.get('buildrequires')) != 1:
                raise ValueError, "A wrapper-rpm must depend on exactly one package"
        else:
            raise ValueError, "Unsupported build type: %s" % buildtype
        if not 'scmurl' in params:
            raise ValueError, "%s is missing the scmurl parameter" % package
        builds[package] = params
    if not builds:
        raise ValueError, "No sections found in: %s" % ', '.join(confs)
    return builds

def parse_maven_param(confs, chain=False, scratch=False, section=None):
    """
    Parse .ini files that contain parameters to launch a Maven build.

    Return a map that contains a single entry corresponding to the given
    section of the .ini file.  If the config file only contains a single
    section, section does not need to be specified.
    """
    if not isinstance(confs, (list, tuple)):
        confs = [confs]
    builds = parse_maven_params(confs, chain=chain, scratch=scratch)
    if section:
        if section in builds:
            builds = {section: builds[section]}
        else:
            raise ValueError, "Section %s does not exist in: %s" % (section, ', '.join(confs))
    elif len(builds) > 1:
        raise ValueError, "Multiple sections in: %s, you must specify the section" % ', '.join(confs)
    return builds

def parse_maven_chain(confs, scratch=False):
    """
    Parse maven-chain config.

    confs is a path to a config file or a list of paths to config files.

    Return a map whose keys are package names and values are config parameters.
    """
    builds = parse_maven_params(confs, chain=True, scratch=scratch)
    depmap = {}
    for package, params in builds.items():
        depmap[package] = set(params.get('buildrequires', []))
    try:
        order = tsort(depmap)
    except ValueError, e:
        raise ValueError, 'No possible build order, missing/circular dependencies'
    return builds
