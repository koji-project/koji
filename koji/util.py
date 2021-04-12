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

from __future__ import absolute_import, division

import base64
import calendar
import datetime
import errno
import hashlib
import logging
import os
import os.path
import re
import resource
import shutil
import stat
import struct
import sys
import time
import warnings
from fnmatch import fnmatch
from zlib import adler32

import six
from six.moves import range, zip

import koji
from koji.xmlrpcplus import DateTime


# BEGIN kojikamid dup #

def md5_constructor(*args, **kwargs):
    if hasattr(hashlib._hashlib, 'get_fips_mode') and hashlib._hashlib.get_fips_mode():
        # do not care about FIPS we need md5 for signatures and older hashes
        # It is still used for *some* security
        kwargs['usedforsecurity'] = False
    return hashlib.md5(*args, **kwargs)

# END kojikamid dup #


# imported from kojiweb and kojihub
def deprecated(message):
    """Print deprecation warning"""
    with warnings.catch_warnings():
        warnings.simplefilter('always', DeprecationWarning)
        warnings.warn(message, DeprecationWarning)


def _changelogDate(cldate):
    return time.strftime('%a %b %d %Y',
                         time.strptime(koji.formatTime(cldate), '%Y-%m-%d %H:%M:%S'))


def formatChangelog(entries):
    """Format a list of changelog entries (dicts)
    into a string representation."""
    result = ''
    for entry in entries:
        result += """* %s %s
%s

""" % (_changelogDate(entry['date']),
            koji._fix_print(entry['author']),
            koji._fix_print(entry['text']))
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
    return calendar.timegm(
        datetime.datetime(*(date + time)).timetuple())


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
    mins = int(elapsed // 60)
    secs = int(elapsed % 60)
    return '%s:%02i' % (mins, secs)


def printList(lst):
    """Print the contents of the list comma-separated"""
    if len(lst) == 0:
        return ''
    elif len(lst) == 1:
        return lst[0]
    elif len(lst) == 2:
        return ' and '.join(lst)
    else:
        ret = ', '.join(lst[:-1])
        ret += ', and '
        ret += lst[-1]
        return ret


def base64encode(s, as_bytes=False):
    """Helper function to encode string or bytes as base64

    This function returns a string unless as_bytes is True
    """
    if six.PY2:
        return base64.b64encode(s)

    if isinstance(s, str):
        s = s.encode('utf8')
    data = base64.b64encode(s)
    if as_bytes:
        return data
    else:
        # ascii is always good enough for base64 encoded data
        return data.decode('ascii')


# We don't need a decode wrapper, but we define this for naming consistency
base64decode = base64.b64decode


def decode_bytes(data, fallback='iso8859-15'):
    """Decode a bytes-like object that is expected to be a valid string

    First utf8 is tried, then the fallback (defaults to iso8859-15).
    The fallback behavior can be disabled by setting the option to None.
    """
    try:
        return data.decode('utf8')
    except UnicodeDecodeError:
        if fallback:
            return data.decode(fallback)
        raise


def multi_fnmatch(s, patterns):
    """Returns true if s matches any pattern in the list

    If patterns is a string, it will be split() first
    """
    if isinstance(patterns, six.string_types):
        patterns = patterns.split()
    for pat in patterns:
        if fnmatch(s, pat):
            return True
    return False


def dslice(dict_, keys, strict=True):
    """Returns a new dictionary containing only the specified keys"""
    ret = {}
    for key in keys:
        if strict or key in dict_:
            # for strict we skip the has_key check and let the dict generate the KeyError
            ret[key] = dict_[key]
    return ret


def dslice_ex(dict_, keys, strict=True):
    """Returns a new dictionary with only the specified keys removed"""
    ret = dict_.copy()
    for key in keys:
        if strict or key in ret:
            del ret[key]
    return ret


class DataWalker(object):

    def __init__(self, data, callback, kwargs=None):
        self.data = data
        self.callback = callback
        if kwargs is None:
            kwargs = {}
        self.kwargs = kwargs

    def walk(self):
        return self._walk(self.data)

    def _walk(self, value):
        # recurse if needed
        if isinstance(value, tuple):
            value = tuple([self._walk(x) for x in value])
        elif isinstance(value, list):
            value = [self._walk(x) for x in value]
        elif isinstance(value, dict):
            ret = {}
            for k in value:
                k = self._walk(k)
                v = self._walk(value[k])
                ret[k] = v
            value = ret
        # finally, let callback filter the value
        return self.callback(value, **self.kwargs)


def encode_datetime(value):
    """Convert datetime objects to strings"""
    if isinstance(value, datetime.datetime):
        return value.isoformat(' ')
    elif isinstance(value, DateTime):
        return datetime.datetime(*value.timetuple()[:6]).isoformat(' ')
    else:
        return value


def encode_datetime_recurse(value):
    walker = DataWalker(value, encode_datetime)
    return walker.walk()


def call_with_argcheck(func, args, kwargs=None):
    """Call function, raising ParameterError if args do not match"""
    if kwargs is None:
        kwargs = {}
    try:
        return func(*args, **kwargs)
    except TypeError as e:
        if sys.exc_info()[2].tb_next is None:
            # The stack is only one high, so the error occurred in this function.
            # Therefore, we assume the TypeError is due to a parameter mismatch
            # in the above function call.
            raise koji.ParameterError(str(e))
        raise


def apply_argspec(argspec, args, kwargs=None):
    """Apply an argspec to the given args and return a dictionary"""
    if kwargs is None:
        kwargs = {}
    f_args, f_varargs, f_varkw, f_defaults = argspec
    data = dict(zip(f_args, args))
    if len(args) > len(f_args):
        if not f_varargs:
            raise koji.ParameterError('too many args')
        data[f_varargs] = tuple(args[len(f_args):])
    elif f_varargs:
        data[f_varargs] = ()
    if f_varkw:
        data[f_varkw] = {}
    for arg in kwargs:
        if arg in data:
            raise koji.ParameterError('duplicate keyword argument %r' % arg)
        if arg in f_args:
            data[arg] = kwargs[arg]
        elif not f_varkw:
            raise koji.ParameterError("unexpected keyword argument %r" % arg)
        else:
            data[f_varkw][arg] = kwargs[arg]
    if f_defaults:
        for arg, val in zip(f_args[-len(f_defaults):], f_defaults):
            data.setdefault(arg, val)
    for n, arg in enumerate(f_args):
        if arg not in data:
            raise koji.ParameterError('missing required argument %r (#%i)'
                                      % (arg, n))
    return data


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
        for val in six.itervalues(super(LazyDict, self)):
            yield lazy_eval(val)

    def iteritems(self):
        for key, val in six.iteritems(super(LazyDict, self)):
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
        raise TypeError('object does not support lazy attributes')
    value = LazyValue(func, args, kwargs=kwargs, cache=cache)
    setattr(object, name, value)


class _RetryRmtree(Exception):
    """This exception is used internally by rmtree"""
    # We raise this exception only when it makes sense for rmtree to retry from the top


def rmtree(path, logger=None):
    """Delete a directory tree without crossing fs boundaries"""
    # implemented to avoid forming long paths
    # see: https://pagure.io/koji/issue/201
    logger = logger or logging.getLogger('koji')
    try:
        st = os.lstat(path)
    except FileNotFoundError:
        logger.warning("No such file/dir %s for removal" % path)
        return
    if not stat.S_ISDIR(st.st_mode):
        raise koji.GenericError("Not a directory: %s" % path)
    dev = st.st_dev
    cwd = os.getcwd()

    try:
        # retry loop
        while True:
            try:
                os.chdir(path)
            except OSError as e:
                if e.errno in (errno.ENOENT, errno.ESTALE):
                    # likely racing with another rmtree
                    # if the dir doesn't exist, we're done
                    return
                raise
            try:
                _rmtree(dev)
            except _RetryRmtree:
                # reset and retry
                os.chdir(cwd)
                continue
            break
    finally:
        os.chdir(cwd)

    # a successful _rmtree call should leave us with an empty directory
    try:
        os.rmdir(path)
    except OSError as e:
        if e.errno != errno.ENOENT:
            raise


def _rmtree(dev):
    """Remove all contents of CWD"""
    # This implementation avoids forming long paths and recursion. Otherwise
    # we will have errors with very deep directory trees.
    # - to avoid forming long paths we change directory as we go
    # - to avoid recursion we maintain our own stack
    dirstack = []
    # Each entry in dirstack is a list of subdirs for that level
    # As we descend into the tree, we append a new entry to dirstack
    # When we ascend back up after removal, we pop them off
    while True:
        dirs = _stripcwd(dev)

        # if cwd has no subdirs, walk back up until we find some
        while not dirs and dirstack:
            try:
                os.chdir('..')
            except OSError as e:
                if e.errno in (errno.ENOENT, errno.ESTALE):
                    # likely in a race with another rmtree
                    # however, we cannot proceed from here, so we return to the top
                    raise _RetryRmtree(str(e))
                raise
            dirs = dirstack.pop()

            # now that we've ascended back up by one, the first dir entry is
            # one we've just cleared, so we should remove it
            empty_dir = dirs.pop()
            try:
                os.rmdir(empty_dir)
            except OSError:
                # If this happens, either something else is writing to the dir,
                # or there is a bug in our code.
                # For now, we ignore this and proceed, but we'll still fail at
                # the top level rmdir
                pass

        if not dirs:
            # we are done
            break

        # otherwise we descend into the next subdir
        subdir = dirs[-1]
        # note: we do not pop here because we need to remember to remove subdir later
        try:
            os.chdir(subdir)
        except OSError as e:
            if e.errno == errno.ENOENT:
                # likely in a race with another rmtree
                # we'll ignore this and continue
                # since subdir doesn't exist, we'll pop it off and forget about it
                dirs.pop()
                continue  # with dirstack unchanged
            raise
        dirstack.append(dirs)


def _stripcwd(dev):
    """Unlink all files in cwd and return list of subdirs"""
    dirs = []
    try:
        fdirs = os.listdir('.')
    except OSError as e:
        # cwd has been removed by others, just return an empty list
        if e.errno in (errno.ENOENT, errno.ESTALE):
            return dirs
        raise
    for fn in fdirs:
        try:
            st = os.lstat(fn)
        except OSError as e:
            if e.errno == errno.ENOENT:
                continue
            raise
        if st.st_dev != dev:
            # don't cross fs boundary
            continue
        if stat.S_ISDIR(st.st_mode):
            dirs.append(fn)
        else:
            try:
                os.unlink(fn)
            except OSError:
                # we'll still fail at the top level
                pass
    return dirs


def safer_move(src, dst):
    """Rename if possible, copy+rm otherwise

    Behavior is similar to shutil.move

    Unlike move, src is /always/ moved from src to dst. If dst is an existing
    directory, then an error is raised.
    """
    if os.path.exists(dst):
        raise koji.GenericError("Destination exists: %s" % dst)
    elif os.path.islink(dst):
        raise koji.GenericError("Destination is a symlink: %s" % dst)
    # TODO - use locking to do a better job of catching races
    shutil.move(src, dst)


def move_and_symlink(src, dst, relative=True, create_dir=False):
    """Move src to dest and create symlink instead of original file"""
    if create_dir:
        koji.ensuredir(os.path.dirname(dst))
    safer_move(src, dst)
    if relative:
        dst = os.path.relpath(dst, os.path.dirname(src))
    os.symlink(dst, src)


def joinpath(path, *paths):
    """A wrapper around os.path.join that limits directory traversal"""

    # note that the first path is left alone

    newpaths = []
    for _p in paths:
        p = os.path.normpath(_p)
        if p == '..' or p.startswith('../') or p.startswith('/'):
            raise ValueError('Invalid path segment: %s' % _p)
        newpaths.append(p)

    return os.path.join(path, *newpaths)


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
    if ts is not None:
        return session.getLastEvent(before=ts)
    repo = getattr(opts, 'repo')
    if repo is not None:
        rinfo = session.repoInfo(repo, strict=True)
        return {'id': rinfo['create_event'],
                'ts': rinfo['create_ts']}
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


def check_sigmd5(filename):
    """Compare header's sigmd5 with actual md5 of hdr+payload without need of rpm"""
    with open(filename, 'rb') as f:
        leadsize = 96
        # skip magic + reserved
        o = leadsize + 8
        f.seek(o)
        data = f.read(8)
        indexcount, storesize = struct.unpack('!II', data)
        for idx in range(indexcount):
            data = f.read(16)
            tag, data_type, offset, count = struct.unpack('!IIII', data)
            if tag == 1004:  # SIGMD5
                assert(data_type == 7)  # binary data
                assert(count == 16)     # 16 bytes of md5
                break
        # seek to location of md5
        f.seek(o + 8 + indexcount * 16 + offset)
        sigmd5 = f.read(16)

        # seek to start of header
        sigsize = 8 + 16 * indexcount + storesize
        o += sigsize + (8 - (sigsize % 8)) % 8
        f.seek(o)

        # compute md5 of rest of file
        md5 = md5_constructor()
        while True:
            d = f.read(1024**2)
            if not d:
                break
            md5.update(d)

        return sigmd5 == md5.digest()


def parseStatus(rv, prefix):
    if isinstance(prefix, (list, tuple)):
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
        if len(limits) not in (1, 2):
            logger.error("Invalid resource limit: %s=%s", key, opts[key])
            continue
        if len(limits) == 1:
            limits.append(orig[1])
        logger.warning('Setting resource limit: %s = %r', key, limits)
        try:
            resource.setrlimit(rcode, tuple(limits))
        except ValueError as e:
            logger.error("Unable to set %s: %s", key, e)


class adler32_constructor(object):

    # mimicing the hashlib constructors
    def __init__(self, arg=''):
        if six.PY3 and isinstance(arg, str):
            arg = bytes(arg, 'utf-8')
        self._value = adler32(arg) & 0xffffffff
        # the bitwise and works around a bug in some versions of python
        # see: https://bugs.python.org/issue1202

    def update(self, arg):
        if six.PY3 and isinstance(arg, str):
            arg = bytes(arg, 'utf-8')
        self._value = adler32(arg, self._value) & 0xffffffff

    def digest(self):
        return self._value

    def hexdigest(self):
        return "%08x" % self._value

    def copy(self):
        dup = adler32_constructor()
        dup._value = self._value
        return dup

    digest_size = 4
    block_size = 1  # I think


def tsort(parts):
    """Given a partial ordering, return a totally ordered list.

    part is a dict of partial orderings.  Each value is a set,
    which the key depends on.

    The return value is a list of sets, each of which has only
    dependencies on items in previous entries in the list."""
    parts = parts.copy()
    result = []
    while True:
        level = set([name for name, deps in six.iteritems(parts) if not deps])
        if not level:
            break
        result.append(level)
        parts = dict([(name, deps - level) for name, deps in six.iteritems(parts)
                      if name not in level])
    if parts:
        raise ValueError('total ordering not possible')
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
        raise AttributeError(name)


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
            raise ValueError("Environment variables must be in NAME=VALUE format")
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
    config = koji.read_config_files(confs)
    builds = {}
    for package in config.sections():
        buildtype = 'maven'
        if config.has_option(package, 'type'):
            buildtype = config.get(package, 'type')
        if buildtype == 'maven':
            params = maven_params(config, package, chain=chain, scratch=scratch)
        elif buildtype == 'wrapper':
            params = wrapper_params(config, package, chain=chain, scratch=scratch)
            if len(params.get('buildrequires')) != 1:
                raise ValueError("A wrapper-rpm must depend on exactly one package")
        else:
            raise ValueError("Unsupported build type: %s" % buildtype)
        if 'scmurl' not in params:
            raise ValueError("%s is missing the scmurl parameter" % package)
        builds[package] = params
    if not builds:
        if not isinstance(confs, (list, tuple)):
            confs = [confs]
        raise ValueError("No sections found in: %s" % ', '.join(confs))
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
            raise ValueError("Section %s does not exist in: %s" % (section, ', '.join(confs)))
    elif len(builds) > 1:
        raise ValueError(
            "Multiple sections in: %s, you must specify the section" % ', '.join(confs))
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
        tsort(depmap)
    except ValueError:
        raise ValueError('No possible build order, missing/circular dependencies')
    return builds


def to_list(lst):
    """
    Helper function for py2/py3 compatibility used e.g. in
    list(dict.keys())

    Don't use it for structures like list(zip(x, y)), where six.moves.zip is
    used, so it is always an iterator.
    """

    if isinstance(lst, list):
        return lst
    else:
        return list(lst)
