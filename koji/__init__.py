# Python module
# Common functions

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
#
# Authors:
#       Mike McLean <mikem@redhat.com>

import sys
try:
    import krbV
except ImportError:
    sys.stderr.write("Warning: Could not install krbV module. Kerberos support will be disabled.\n")
    sys.stderr.flush()
import base64
import commands
import datetime
from fnmatch import fnmatch
import logging
import logging.handlers
import md5
import os
import os.path
import pwd
import re
import rpm
import signal
import socket
import tempfile
import time
import traceback
import urllib
import urllib2
import urlparse
import xmlrpclib
from xmlrpclib import loads, Fault
import ssl.XMLRPCServerProxy

def _(args):
    """Stub function for translation"""
    return args

## Constants ##

RPM_HEADER_MAGIC = '\x8e\xad\xe8'
RPM_TAG_HEADERSIGNATURES = 62
RPM_SIGTAG_MD5 = 1004
RPM_SIGTAG_GPG = 1005

class Enum(dict):
    """A simple class to track our enumerated constants

    Can quickly map forward or reverse
    """

    def __init__(self,*args):
        self._order = tuple(*args)
        super(Enum,self).__init__([(value,n) for n,value in enumerate(self._order)])

    def __getitem__(self,key):
        if isinstance(key,int) or isinstance(key,slice):
            return self._order.__getitem__(key)
        else:
            return super(Enum,self).__getitem__(key)

    def get(self,key,default=None):
        try:
            return self.__getitem__(key)
        except (IndexError,KeyError):
            return default

    def getnum(self,key,default=None):
        try:
            value = self.__getitem__(key)
        except (IndexError,KeyError):
            return default
        if isinstance(key,int):
            return key
        else:
            return value

    def getvalue(self,key,default=None):
        try:
            value = self.__getitem__(key)
        except (IndexError,KeyError):
            return default
        if isinstance(key,int):
            return value
        else:
            return key

    def _notImplemented(self,*args,**opts):
        raise NotImplementedError

    #read-only
    __setitem__ = _notImplemented
    __delitem__ = _notImplemented
    clear = _notImplemented
    pop = _notImplemented
    popitem = _notImplemented
    update = _notImplemented
    setdefault = _notImplemented

API_VERSION = 1

TASK_STATES = Enum((
    'FREE',
    'OPEN',
    'CLOSED',
    'CANCELED',
    'ASSIGNED',
    'FAILED',
))

BUILD_STATES = Enum((
    'BUILDING',
    'COMPLETE',
    'DELETED',
    'FAILED',
    'CANCELED',
))

USERTYPES = Enum((
    'NORMAL',
    'HOST',
    'GROUP',
))

USER_STATUS = Enum((
    'NORMAL',
    'BLOCKED',
))

# authtype values
# normal == username/password
AUTHTYPE_NORMAL = 0
AUTHTYPE_KERB = 1
AUTHTYPE_SSL = 2

#dependency types
DEP_REQUIRE = 0
DEP_PROVIDE = 1
DEP_OBSOLETE = 2
DEP_CONFLICT = 3

#dependency flags
RPMSENSE_LESS = 2
RPMSENSE_GREATER = 4
RPMSENSE_EQUAL = 8

# repo states
REPO_STATES = Enum((
    'INIT',
    'READY',
    'EXPIRED',
    'DELETED',
    'PROBLEM',
))
# for backwards compatibility
REPO_INIT = REPO_STATES['INIT']
REPO_READY = REPO_STATES['READY']
REPO_EXPIRED = REPO_STATES['EXPIRED']
REPO_DELETED = REPO_STATES['DELETED']
REPO_PROBLEM = REPO_STATES['PROBLEM']

# buildroot states
BR_STATES = Enum((
    'INIT',
    'WAITING',
    'BUILDING',
    'EXPIRED',
))

#PARAMETERS
BASEDIR = '/mnt/koji'
# default task priority
PRIO_DEFAULT = 20

#Exceptions
class GenericError(Exception):
    """Base class for our custom exceptions"""
    faultCode = 1000
    fromFault = False
    def __str__(self):
        try:
            return str(self.args[0]['args'][0])
        except:
            try:
                return str(self.args[0])
            except:
                return str(self.__dict__)

class LockConflictError(GenericError):
    """Raised when there is a lock conflict"""
    faultCode = 1001

class AuthError(GenericError):
    """Raised when there is an error in authentication"""
    faultCode = 1002

class TagError(GenericError):
    """Raised when a tagging operation fails"""
    faultCode = 1003

class ActionNotAllowed(GenericError):
    """Raised when the session does not have permission to take some action"""
    faultCode = 1004

class BuildError(GenericError):
    """Raised when a build fails"""
    faultCode = 1005

class AuthLockError(AuthError):
    """Raised when a lock prevents authentication"""
    faultCode = 1006

class AuthExpired(AuthError):
    """Raised when a session has expired"""
    faultCode = 1007

class SequenceError(AuthError):
    """Raised when requests are received out of sequence"""
    faultCode = 1008

class RetryError(AuthError):
    """Raised when a request is received twice and cannot be rerun"""
    faultCode = 1009

class PreBuildError(BuildError):
    """Raised when a build fails during pre-checks"""
    faultCode = 1010

class PostBuildError(BuildError):
    """Raised when a build fails during post-checks"""
    faultCode = 1011

class BuildrootError(BuildError):
    """Raised when there is an error with the buildroot"""
    faultCode = 1012

class FunctionDeprecated(GenericError):
    """Raised by a deprecated function"""
    faultCode = 1013

#A function to get create an exception from a fault
def convertFault(fault):
    """Convert a fault to the corresponding Exception type, if possible"""
    code = getattr(fault,'faultCode',None)
    if code is None:
        return fault
    for v in globals().values():
        if type(v) == type(Exception) and issubclass(v,GenericError) and \
                code == getattr(v,'faultCode',None):
            ret = v(fault.faultString)
            ret.fromFault = True
            return ret
    #otherwise...
    return fault

def listFaults():
    """Return a list of faults

    Returns a list of dictionaries whose keys are:
        faultCode: the numeric code used in fault conversion
        name: the name of the exception
        desc: the description of the exception (docstring)
    """
    ret = []
    for n,v in globals().items():
        if type(v) == type(Exception) and issubclass(v,GenericError):
            code = getattr(v,'faultCode',None)
            if code is None:
                continue
            info = {}
            info['faultCode'] = code
            info['name'] = n
            info['desc'] = getattr(v,'__doc__',None)
            ret.append(info)
    ret.sort(lambda a,b: cmp(a['faultCode'],b['faultCode']))
    return ret

#functions for encoding/decoding optional arguments

def encode_args(*args,**opts):
    """The function encodes optional arguments as regular arguments.

    This is used to allow optional arguments in xmlrpc calls
    Returns a tuple of args
    """
    if opts:
        opts['__starstar'] = True
        args = args + (opts,)
    return args

def decode_args(*args):
    """Decodes optional arguments from a flat argument list

    Complementary to encode_args
    Returns a tuple (args,opts) where args is a tuple and opts is a dict
    """
    opts = {}
    if len(args) > 0:
        last = args[-1]
        if type(last) == dict and last.get('__starstar',False):
            del last['__starstar']
            opts = last
            args = args[:-1]
    return args,opts

#commonly used functions

def safe_xmlrpc_loads(s):
    """Load xmlrpc data from a string, but catch faults"""
    try:
        return loads(s)
    except Fault, f:
        return f

def ensuredir(directory):
    """Create directory, if necessary."""
    if os.path.isdir(directory):
        return
    try:
        os.makedirs(directory)
    except OSError:
        #thrown when dir already exists (could happen in a race)
        if not os.path.isdir(directory):
            #something else must have gone wrong
            raise

def daemonize():
    """Detach and run in background"""
    pid = os.fork()
    if pid:
        os._exit(0)
    os.setsid()
    signal.signal(signal.SIGHUP, signal.SIG_IGN)
    #fork again
    pid = os.fork()
    if pid:
        os._exit(0)
    os.chdir("/")
    #redirect stdin/stdout/sterr
    fd0 = os.open('/dev/null', os.O_RDONLY)
    fd1 = os.open('/dev/null', os.O_RDWR)
    fd2 = os.open('/dev/null', os.O_RDWR)
    os.dup2(fd0,0)
    os.dup2(fd1,1)
    os.dup2(fd2,2)
    os.close(fd0)
    os.close(fd1)
    os.close(fd2)

def multibyte(data):
    """Convert a list of bytes to an integer (network byte order)"""
    sum = 0
    n = len(data)
    for i in xrange(n):
        sum += data[i] << (8 * (n - i - 1))
    return sum

def find_rpm_sighdr(path):
    """Finds the offset and length of the signature header."""
    # see Maximum RPM Appendix A: Format of the RPM File

    # The lead is a fixed sized section (96 bytes) that is mostly obsolete
    sig_start = 96
    sigsize = rpm_hdr_size(path, sig_start)
    return (sig_start, sigsize)

def rpm_hdr_size(f, ofs=None):
    """Returns the length (in bytes) of the rpm header

    f = filename or file object
    ofs = offset of the header
    """
    if isinstance(f, (str, unicode)):
        fo = file(f, 'rb')
    else:
        fo = f
    if ofs != None:
        fo.seek(ofs, 0)
    magic = fo.read(3)
    if magic != RPM_HEADER_MAGIC:
        raise GenericError, "Invalid rpm: bad magic: %r" % magic

    # skip past section magic and such
    #   (3 bytes magic, 1 byte version number, 4 bytes reserved)
    fo.seek(ofs + 8, 0)

    # now read two 4-byte integers which tell us
    #  - # of index entries
    #  - bytes of data in header
    data = [ ord(x) for x in fo.read(8) ]
    il = multibyte(data[0:4])
    dl = multibyte(data[4:8])

    #this is what the section data says the size should be
    hdrsize = 8 + 16 * il + dl

    # hdrsize rounded up to nearest 8 bytes
    hdrsize = hdrsize + ( 8 - ( hdrsize % 8 ) ) % 8

    # add eight bytes for section header
    hdrsize = hdrsize + 8

    if not isinstance(f, (str, unicode)):
        fo.close()
    return hdrsize


class RawHeader(object):

    # see Maximum RPM Appendix A: Format of the RPM File

    def __init__(self, data):
        if data[0:3] != RPM_HEADER_MAGIC:
            raise GenericError, "Invalid rpm header: bad magic: %r" % (data[0:3],)
        self.header = data
        self._index()

    def version(self):
        #fourth byte is the version
        return ord(data[3])

    def _index(self):
        # read two 4-byte integers which tell us
        #  - # of index entries  (each 16 bytes long)
        #  - bytes of data in header
        data = [ ord(x) for x in self.header[8:12] ]
        il = multibyte(data[:4])
        dl = multibyte(data[4:8])

        #read the index (starts at offset 16)
        index = {}
        for i in xrange(il):
            entry = []
            for j in xrange(4):
                ofs = 16 + i*16 + j*4
                data = [ ord(x) for x in self.header[ofs:ofs+4] ]
                entry.append(multibyte(data))
            #print "Tag: %d, Type: %d, Offset: %x, Count: %d" % tuple(entry)
            index[entry[0]] = entry
        self.datalen = dl
        self.index = index

    def dump(self):
        print "HEADER DUMP:"
        #calculate start of store
        il = len(self.index)
        store = 16 + il * 16
        #print "start is: %d" % start
        #print "index length: %d" % il
        print "Store at offset %d (%0x)" % (store,store)
        #sort entries by offset, dtype
        #also rearrange: tag, dtype, offset, count -> offset, dtype, tag, count
        order = [(x[2], x[1], x[0], x[3]) for x in self.index.itervalues()]
        order.sort()
        next = store
        #map some rpmtag codes
        tags = {}
        for name, code in rpm.__dict__.iteritems():
            if name.startswith('RPMTAG_') and isinstance(code, int):
                tags[code] = name[7:].lower()
        for entry in order:
            #tag, dtype, offset, count = entry
            offset, dtype, tag, count = entry
            pos = store + offset
            if next is not None:
                if pos > next:
                    print "** HOLE between entries"
                    print "Hex: %s" % hex_string(self.header[next:pos])
                    print "Data: %r" % self.header[next:pos]
                elif pos < next:
                    print "** OVERLAPPING entries"
            print "Tag: %d [%s], Type: %d, Offset: %x, Count: %d" \
                    % (tag, tags.get(tag, '?'), dtype, offset, count)
            if dtype == 0:
                #null
                print "[NULL entry]"
                next = pos
            elif dtype == 1:
                #char
                for i in xrange(count):
                    print "Char: %r" % self.header[pos]
                    pos += 1
                next = pos
            elif dtype >= 2 and dtype <= 5:
                #integer
                n = 1 << (dtype - 2)
                for i in xrange(count):
                    data = [ ord(x) for x in self.header[pos:pos+n] ]
                    print "%r" % data
                    num = multibyte(data)
                    print "Int(%d): %d" % (n, num)
                    pos += n
                next = pos
            elif dtype == 6:
                # string (null terminated)
                end = self.header.find('\0', pos)
                print "String(%d): %r" % (end-pos, self.header[pos:end])
                next = end + 1
            elif dtype == 7:
                print "Data: %s" % hex_string(self.header[pos:pos+count])
                next = pos+count
            elif dtype == 8:
                # string array
                for i in xrange(count):
                    end = self.header.find('\0', pos)
                    print "String(%d): %r" % (end-pos, self.header[pos:end])
                    pos = end + 1
                next = pos
            elif dtype == 9:
                # unicode string array
                for i in xrange(count):
                    end = self.header.find('\0', pos)
                    print "i18n(%d): %r" % (end-pos, self.header[pos:end])
                    pos = end + 1
                next = pos
            else:
                print "Skipping data type %x" % dtype
                next = None
        if next is not None:
            pos = store + self.datalen
            if next < pos:
                print "** HOLE at end of data block"
                print "Hex: %s" % hex_string(self.header[next:pos])
                print "Data: %r" % self.header[next:pos]
            elif pos > next:
                print "** OVERFLOW in data block"

    def __getitem__(self, key):
        tag, dtype, offset, count = self.index[key]
        assert tag == key
        return self._getitem(dtype, offset, count)

    def _getitem(self, dtype, offset, count):
        #calculate start of store
        il = len(self.index)
        store = 16 + il * 16
        pos = store + offset
        if dtype >= 2 and dtype <= 5:
            n = 1 << (dtype - 2)
            # n-byte integer
            data = [ ord(x) for x in self.header[pos:pos+n] ]
            return multibyte(data)
        elif dtype == 6:
            # string (null terminated)
            end = self.header.find('\0', pos)
            return self.header[pos:end]
        elif dtype == 7:
            #raw data
            return self.header[pos:pos+count]
        else:
            #XXX - not all valid data types are handled
            raise GenericError, "Unable to read header data type: %x" % dtype

    def get(self, key, default=None):
        entry = self.index.get(key)
        if entry is None:
            return default
        else:
            return self._getitem(*entry[1:])


def rip_rpm_sighdr(src):
    """Rip the signature header out of an rpm"""
    (start, size) = find_rpm_sighdr(src)
    fo = file(src, 'rb')
    fo.seek(start, 0)
    sighdr = fo.read(size)
    fo.close()
    return sighdr

def rip_rpm_hdr(src):
    """Rip the main header out of an rpm"""
    (start, size) = find_rpm_sighdr(src)
    start += size
    size = rpm_hdr_size(src, start)
    fo = file(src, 'rb')
    fo.seek(start, 0)
    hdr = fo.read(size)
    fo.close()
    return hdr

def get_sighdr_key(sighdr):
    """Parse the sighdr and return the sigkey"""
    sig = RawHeader(sighdr).get(RPM_SIGTAG_GPG)
    if sig is None:
        return None
    else:
        return hex_string(sig[13:17])

def splice_rpm_sighdr(sighdr, src, dst=None, bufsize=8192):
    """Write a copy of an rpm with signature header spliced in"""
    (start, size) = find_rpm_sighdr(src)
    if dst is None:
        (fd, dst) = tempfile.mkstemp()
        os.close(fd)
    src_fo = file(src, 'rb')
    dst_fo = file(dst, 'wb')
    dst_fo.write(src_fo.read(start))
    dst_fo.write(sighdr)
    src_fo.seek(size, 1)
    while True:
        buf = src_fo.read(bufsize)
        if not buf:
            break
        dst_fo.write(buf)
    src_fo.close()
    dst_fo.close()
    return dst

def get_rpm_header(f):
    """Return the rpm header."""
    ts = rpm.TransactionSet()
    ts.setVSFlags(rpm._RPMVSF_NOSIGNATURES|rpm._RPMVSF_NODIGESTS)
    if isinstance(f, (str, unicode)):
        fo = file(f, "r")
    else:
        fo = f
    hdr = ts.hdrFromFdno(fo.fileno())
    if fo is not f:
        fo.close()
    return hdr

def get_header_field(hdr,name):
    """Extract named field from an rpm header"""
    idx = getattr(rpm,"RPMTAG_%s" % name.upper(),None)
    if idx is None:
        raise GenericError, "No such rpm header field: %s" % name
    return hdr[idx]

def get_header_fields(X,fields):
    """Extract named fields from an rpm header and return as a dictionary

    X may be either the rpm header or the rpm filename
    """
    if type(X) == str:
        hdr = get_rpm_header(X)
    else:
        hdr = X
    ret = {}
    for f in fields:
        ret[f] = get_header_field(hdr,f)
    return ret

def parse_NVR(nvr):
    """split N-V-R into dictionary of data"""
    ret = {}
    p2 = nvr.rfind("-",0)
    if p2 == -1 or p2 == len(nvr) - 1:
        raise GenericError("invalid format: %s" % nvr)
    p1 = nvr.rfind("-",0,p2)
    if p1 == -1 or p1 == p2 - 1:
        raise GenericError("invalid format: %s" % nvr)
    ret['release'] = nvr[p2+1:]
    ret['version'] = nvr[p1+1:p2]
    ret['name'] = nvr[:p1]
    epochIndex = ret['name'].find(':')
    if epochIndex == -1:
        ret['epoch'] = ''
    else:
        ret['epoch'] = ret['name'][:epochIndex]
        ret['name'] = ret['name'][epochIndex + 1:]
    return ret

def parse_NVRA(nvra):
    """split N-V-R.A.rpm into dictionary of data"""
    if nvra.endswith(".rpm"):
        nvra = nvra[:-4]
    p3 = nvra.rfind(".")
    if p3 == -1 or p3 == len(nvra) - 1:
        raise GenericError("invalid format: %s" % nvra)
    arch = nvra[p3+1:]
    ret = parse_NVR(nvra[:p3])
    ret['arch'] = arch
    if arch == 'src':
        ret['src'] = True
    else:
        ret['src'] = False
    return ret

def canonArch(arch):
    """Given an arch, return the "canonical" arch"""
    #XXX - this could stand to be smarter, and we should probably
    #   have some other related arch-mangling functions.
    if fnmatch(arch,'i?86') or arch == 'athlon':
        return 'i386'
    elif fnmatch(arch,'ppc64*'):
        return 'ppc64'
    elif arch == 'ia32e':
        return 'x86_64'
    else:
        return arch

def hex_string(s):
    """Converts a string to a string of hex digits"""
    return ''.join([ '%02x' % ord(x) for x in s ])


def make_groups_spec(grplist,name='buildsys-build',buildgroup=None):
    """Return specfile contents representing the group"""
    if buildgroup is None:
        buildgroup=name
    data = [
"""#
# This specfile represents buildgroups for mock
# Autogenerated by the build system
#
Summary: The base set of packages for a mock chroot\n""",
"""Name: %s\n""" % name,
"""Version: 1
Release: 1
License: GPL
Group: Development/Build Tools
BuildRoot: %{_tmppath}/%{name}-%{version}-%{release}-root
BuildArch: noarch

#package requirements
"""]
    #add a requires entry for all the packages in buildgroup, and in
    #groups required by buildgroup
    need = [buildgroup]
    seen_grp = {}
    seen_pkg = {}
    #index groups
    groups = dict([(g['name'],g) for g in grplist])
    for group_name in need:
        if seen_grp.has_key(group_name):
            continue
        seen_grp[group_name] = 1
        group = groups.get(group_name)
        if group is None:
            data.append("#MISSING GROUP: %s\n" % group_name)
            continue
        data.append("#Group: %s\n" % group_name)
        pkglist = list(group['packagelist'])
        pkglist.sort(lambda a,b: cmp(a['package'], b['package']))
        for pkg in pkglist:
            pkg_name = pkg['package']
            if seen_pkg.has_key(pkg_name):
                continue
            data.append("Requires: %s\n" % pkg_name)
        for req in group['grouplist']:
            req_name = req['name']
            if seen_grp.has_key(req_name):
                continue
            need.append(req_name)
    data.append("""
%description
This is a meta-package that requires a defined group of packages

%prep
%build
%install
%clean

%files
%defattr(-,root,root,-)
%doc
""")
    return ''.join(data)

def generate_comps(groups):
    """Generate comps content from groups data"""
    def boolean_text(x):
        if x:
            return "true"
        else:
            return "false"
    data = [
"""<?xml version="1.0"?>
<!DOCTYPE comps PUBLIC "-//Red Hat, Inc.//DTD Comps info//EN" "comps.dtd">

<!-- Auto-generated by the build system -->
<comps>
""" ]
    groups = list(groups)
    groups.sort(lambda a,b:cmp(a['name'],b['name']))
    for g in groups:
        group_id = g['name']
        name = g['display_name']
        description = g['description']
        langonly = boolean_text(g['langonly'])
        default = boolean_text(g['is_default'])
        uservisible = boolean_text(g['uservisible'])
        data.append(
"""  <group>
    <id>%(group_id)s</id>
    <name>%(name)s</name>
    <description>%(description)s</description>
    <default>%(default)s</default>
    <uservisible>%(uservisible)s</uservisible>
""" % locals())
        if g['biarchonly']:
            data.append(
"""    <biarchonly>%s</biarchonly>
""" % boolean_text(True))

        #print grouplist, if any
        if g['grouplist']:
            data.append(
"""    <grouplist>
""")
            grouplist = list(g['grouplist'])
            grouplist.sort(lambda a,b:cmp(a['name'],b['name']))
            for x in grouplist:
                #['req_id','type','is_metapkg','name']
                name = x['name']
                thetype = x['type']
                tag = "groupreq"
                if x['is_metapkg']:
                    tag = "metapkg"
                if thetype:
                    data.append(
"""      <%(tag)s type="%(thetype)s">%(name)s</%(tag)s>
""" % locals())
                else:
                    data.append(
"""      <%(tag)s>%(name)s</%(tag)s>
""" % locals())
            data.append(
"""    </grouplist>
""")

        #print packagelist, if any
        if g['packagelist']:
            data.append(
"""    <packagelist>
""")
            packagelist = list(g['packagelist'])
            packagelist.sort(lambda a,b:cmp(a['package'],b['package']))
            for p in packagelist:
                #['package_id','type','basearchonly','requires','name']
                name = p['package']
                opts = 'type="%s"' % p['type']
                if p['basearchonly']:
                    opts += ' basearchonly="%s"' % boolean_text(True)
                if p['requires']:
                    opts += ' requires="%s"' % p['requires']
                data.append(
"""      <packagereq %(opts)s>%(name)s</packagereq>
""" % locals())
            data.append(
"""    </packagelist>
""")
        data.append(
"""  </group>
""")
    data.append(
"""</comps>
""")
    return ''.join(data)


def genMockConfig(name, arch, managed=False, repoid=None, tag_name=None, **opts):
    """Generate a mock config

    Returns a string containing the config
    """
    mockdir = opts.get('mockdir', '/var/lib/mock')
    url = opts.get('url')
    if not url:
        if not (repoid and tag_name):
            raise GenericError, "please provide a url or repo/tag"
        topurl = opts.get('topurl')
        if topurl:
            #XXX - PathInfo isn't quite right for this, but it will do for now
            pathinfo = PathInfo(topdir=topurl)
            repodir = pathinfo.repo(repoid,tag_name)
            url = "%s/%s" % (repodir,arch)
        else:
            pathinfo = PathInfo(topdir=opts.get('topdir', '/mnt/koji'))
            repodir = pathinfo.repo(repoid,tag_name)
            url = "file://%s/%s" % (repodir,arch)
    if managed:
        buildroot_id = opts.get('buildroot_id')

    # FIXME - get more of this into a config
    config_opts = {
        'root' : name,
        'basedir' : mockdir,
        'chroot' : '/usr/sbin/mock-helper chroot',
        'mount' : '/usr/sbin/mock-helper mount',
        'umount' : '/usr/sbin/mock-helper umount',
        'rm' : '/usr/sbin/mock-helper rm',
        'mknod' : '/usr/sbin/mock-helper mknod',
        'yum' : '/usr/sbin/mock-helper yum',
        'runuser' : '/sbin/runuser',
        'buildgroup' : 'build',
        'chroot_dep_package' : 'buildsys-build',
        'chrootuser' : 'kojibuilder',
        'chrootgroup' : 'kojibuilder',
        'chroothome' : '/builddir',
        'clean' : True,
        'target_arch' : arch,
    }

    config_opts['yum.conf'] = """
[main]
cachedir=/var/cache/yum
debuglevel=1
logfile=/var/log/yum.log
reposdir=/dev/null
retries=20
obsoletes=1
gpgcheck=0
assumeyes=1

# repos

[core]
name=core
baseurl=%(url)s
""" % locals()
    #XXX - this needs to be configurable

    macros = {
        '_topdir' : '%s/build' % config_opts['chroothome'],
        '_rpmfilename' : '%%{NAME}-%%{VERSION}-%%{RELEASE}.%%{ARCH}.rpm',
        'vendor' : opts.get('vendor', 'Koji'),
        'packager' : opts.get('packager', 'Koji'),
        '_host_cpu' : arch,
        '_host': '%s-%s' % (arch, opts.get('mockhost', 'koji-linux-gnu')),
        #TODO - track some of these in the db instead?
    }
    if opts.has_key('distribution'):
        macros['distribution'] = opts.get('distribution')
    config_opts['macros'] = '\n'.join(["%%%s %s" % (k, v) for k,v in macros.iteritems()])

    parts = ["""#!/usr/bin/python -tt
# Auto-generated by the build system
"""]
    if managed:
        parts.append("""
# Koji buildroot id: %(buildroot_id)s
# Koji buildroot name: %(name)s
# Koji repo id: %(repoid)s
# Koji tag: %(tag_name)s""" % locals())

    parts.append("""
import os
config_opts['chrootuid'] = os.geteuid()
config_opts['chrootgid'] = os.getegid()
""")
    for (key,value) in config_opts.iteritems():
        parts.append("config_opts[%r] = %r\n" % (key,value))
    return ''.join(parts)

def get_sequence_value(cursor, sequence):
    cursor.execute("""SELECT nextval(%(sequence)s)""", locals())
    return cursor.fetchone()[0]

# From Python Cookbook 2nd Edition, Recipe 8.6
def format_exc_plus():
    """ Format the usual traceback information, followed by a listing of
        all the local variables in each frame.
    """
    tb = sys.exc_info()[2]
    while tb.tb_next:
        tb = tb.tb_next
    stack = []
    f = tb.tb_frame
    while f:
        stack.append(f)
        f = f.f_back
    stack.reverse()
    rv = ''.join(traceback.format_exception(sys.exc_type, sys.exc_value, sys.exc_traceback))
    rv += "Locals by frame, innermost last\n"
    for frame in stack:
        rv += "Frame %s in %s at line %s\n" % (frame.f_code.co_name,
                                               frame.f_code.co_filename,
                                               frame.f_lineno)
        for key, value in frame.f_locals.items():
            rv += "  %20s = " % key
            # we must _absolutely_ avoid propagating eceptions, and str(value)
            # COULD cause any exception, so we MUST catch any...:
            try:
                rv += "%s\n" % value
            except:
                rv += "<ERROR WHILE PRINTING VALUE>\n"
    return rv

def openRemoteFile(relpath, topurl=None, topdir=None):
    """Open a file on the main server (read-only)

    This is done either via a mounted filesystem (nfs) or http, depending
    on options"""
    if topurl:
        url = "%s/%s" % (topurl, relpath)
        fo = urllib2.urlopen(url)
    elif topdir:
        fn = "%s/%s" % (topdir, relpath)
        fo = open(fn)
    else:
        raise koji.GenericError, "No access method for remote file: %s" % relpath
    return fo


class PathInfo(object):

    def __init__(self,topdir=None):
        if topdir is None:
            self.topdir = BASEDIR
        else:
            self.topdir = topdir

    def build(self,build):
        """Return the directory where a build belongs"""
        return self.topdir + ("/packages/%(name)s/%(version)s/%(release)s" % build)

    def rpm(self,rpminfo):
        """Return the path (relative to build_dir) where an rpm belongs"""
        return "%(arch)s/%(name)s-%(version)s-%(release)s.%(arch)s.rpm" % rpminfo

    def signed(self, rpminfo, sigkey):
        """Return the path (relative to build dir) where a signed rpm lives"""
        return "data/signed/%s/" % sigkey + self.rpm(rpminfo)

    def sighdr(self, rpminfo, sigkey):
        """Return the path (relative to build_dir) where a cached sig header lives"""
        return "data/sigcache/%s/" % sigkey + self.rpm(rpminfo) + ".sig"

    def build_logs(self, build):
        """Return the path for build logs"""
        return "%s/data/logs" % self.build(build)

    def repo(self,repo_id,tag_str):
        """Return the directory where a repo belongs"""
        return self.topdir + ("/repos/%(tag_str)s/%(repo_id)s" % locals())

    def repocache(self,tag_str):
        """Return the directory where a repo belongs"""
        return self.topdir + ("/repos/%(tag_str)s/cache" % locals())

    def work(self):
        """Return the work dir"""
        return self.topdir + '/work'

    def scratch(self):
        """Return the main scratch dir"""
        return self.topdir + '/scratch'

pathinfo = PathInfo()

class VirtualMethod(object):
    # some magic to bind an XML-RPC method to an RPC server.
    # supports "nested" methods (e.g. examples.getStateName)
    # supports named arguments (if server does)
    def __init__(self, func, name):
        self.__func = func
        self.__name = name
    def __getattr__(self, name):
        return type(self)(self.__func, "%s.%s" % (self.__name, name))
    def __call__(self, *args, **opts):
        return self.__func(self.__name,args,opts)


class ClientSession(object):

    def __init__(self, baseurl, opts=None, sinfo=None):
        assert baseurl, "baseurl argument must not be empty"
        if opts == None:
            opts = {}
        else:
            opts = opts.copy()
        self.opts = opts
        self.proxyOpts = {'allow_none':1}
        if self.opts.get('debug_xmlrpc'):
            self.proxyOpts['verbose'] = 1
        if self.opts.get('certs'):
            self.proxyOpts['certs'] = self.opts['certs']
            self.proxyClass = ssl.XMLRPCServerProxy.PlgXMLRPCServerProxy
        else:
            self.proxyClass = xmlrpclib.ServerProxy
        if self.opts.get('timeout'):
            self.proxyOpts['timeout'] = self.opts['timeout']
        self.baseurl = baseurl
        self.setSession(sinfo)
        self.multicall = False
        self._calls = []
        self.logger = logging.getLogger('koji')

    def setSession(self,sinfo):
        """Set the session info

        If sinfo is None, logout."""
        if sinfo is None:
            self.logged_in = False
            self.callnum = None
            # undo state changes made by ssl_login()
            if self.baseurl.startswith('https:'):
                self.baseurl = self.baseurl.replace('https:', 'http:')
            self.opts.pop('certs', None)
            self.proxyOpts.pop('certs', None)
            self.opts.pop('timeout', None)
            self.proxyOpts.pop('timeout', None)
            self.proxyClass = xmlrpclib.ServerProxy
            url = self.baseurl
        else:
            self.logged_in = True
            self.callnum = 0
            url = "%s?%s" %(self.baseurl,urllib.urlencode(sinfo))
        self.sinfo = sinfo
        self.proxy = self.proxyClass(url,**self.proxyOpts)

    def login(self,opts=None):
        sinfo = self.callMethod('login',self.opts['user'], self.opts['password'],opts)
        if not sinfo:
            return False
        self.setSession(sinfo)
        return True

    def subsession(self):
        "Create a subsession"
        sinfo = self.callMethod('subsession')
        return type(self)(self.baseurl,self.opts,sinfo)

    def krb_login(self, principal=None, keytab=None, ccache=None, proxyuser=None):
        """Log in using Kerberos.  If principal is not None and keytab is
        not None, then get credentials for the given principal from the given keytab.
        If both are None, authenticate using existing local credentials (as obtained
        from kinit).  ccache is the absolute path to use for the credential cache. If
        not specified, the default ccache will be used.  If proxyuser is specified,
        log in the given user instead of the user associated with the Kerberos
        principal.  The principal must be in the "ProxyPrincipals" list on
        the server side."""
        ctx = krbV.default_context()

        if ccache != None:
            ccache = krbV.CCache(name='FILE:' + ccache, context=ctx)
        else:
            ccache = ctx.default_ccache()

        if principal != None:
            if keytab != None:
                cprinc = krbV.Principal(name=principal, context=ctx)
                keytab = krbV.Keytab(name=keytab, context=ctx)
                ccache.init(cprinc)
                ccache.init_creds_keytab(principal=cprinc, keytab=keytab)
            else:
                raise AuthError, 'cannot specify a principal without a keytab'
        else:
            # We're trying to log ourself in.  Connect using existing credentials.
            cprinc = ccache.principal()

        sprinc = krbV.Principal(name=self._serverPrincipal(), context=ctx)

        ac = krbV.AuthContext(context=ctx)
        ac.flags = krbV.KRB5_AUTH_CONTEXT_DO_SEQUENCE|krbV.KRB5_AUTH_CONTEXT_DO_TIME
        ac.rcache = ctx.default_rcache()

        # create and encode the authentication request
        (ac, req) = ctx.mk_req(server=sprinc, client=cprinc,
                               auth_context=ac, ccache=ccache,
                               options=krbV.AP_OPTS_MUTUAL_REQUIRED)
        req_enc = base64.encodestring(req)

        # ask the server to authenticate us
        (rep_enc, sinfo_enc, addrinfo) = self.callMethod('krbLogin', req_enc, proxyuser)

        # Set the addrinfo we received from the server
        # (necessary before calling rd_priv())
        # addrinfo is in (serveraddr, serverport, clientaddr, clientport)
        # format, so swap the pairs because clientaddr is now the local addr
        ac.addrs = tuple((addrinfo[2], addrinfo[3], addrinfo[0], addrinfo[1]))

        # decode and read the reply from the server
        rep = base64.decodestring(rep_enc)
        ctx.rd_rep(rep, auth_context=ac)

        # decode and decrypt the login info
        sinfo_priv = base64.decodestring(sinfo_enc)
        sinfo_str = ac.rd_priv(sinfo_priv)
        sinfo = dict(zip(['session-id', 'session-key'], sinfo_str.split()))

        if not sinfo:
            self.logger.warn('No session info received')
            return False
        self.setSession(sinfo)

        return True

    def _serverPrincipal(self):
        """Get the Kerberos principal of the server we're connecting
        to, based on baseurl.  Assume the last two components of the
        server name are the Kerberos realm."""
        servername = urlparse.urlparse(self.baseurl)[1]
        portspec = servername.find(':')
        if portspec != -1:
            servername = servername[:portspec]

        parts = servername.split('.')
        if len(parts) < 2:
            domain = servername.upper()
        else:
            domain = '.'.join(parts[-2:]).upper()

        return 'host/%s@%s' % (servername, domain)

    def ssl_login(self, cert, ca, serverca, proxyuser=None):
        if not self.baseurl.startswith('https:'):
            self.baseurl = self.baseurl.replace('http:', 'https:')
        
        certs = {}
        certs['key_and_cert'] = cert
        certs['ca_cert'] = ca
        certs['peer_ca_cert'] = serverca

        # 60 second timeout during login
        self.proxy = ssl.XMLRPCServerProxy.PlgXMLRPCServerProxy(self.baseurl, certs, timeout=60, **self.proxyOpts)
        sinfo = self.callMethod('sslLogin', proxyuser)
        if not sinfo:
            raise AuthError, 'unable to obtain a session'

        self.proxyClass = ssl.XMLRPCServerProxy.PlgXMLRPCServerProxy
        self.opts['certs'] = self.proxyOpts['certs'] = certs
        # 12 hour connection timeout.  Some Koji operations can take a long time to return,
        # but after 12 hours we can assume something is seriously wrong.
        self.opts['timeout'] = self.proxyOpts['timeout'] = 60 * 60 * 12
        self.setSession(sinfo)

        return True
        
    def logout(self):
        if not self.logged_in:
            return
        try:
            self.proxy.logout()
        except AuthExpired:
            #this can happen when an exclusive session is forced
            pass
        self.setSession(None)

    def _forget(self):
        """Forget session information, but do not close the session

        This is intended to be used after a fork to prevent the subprocess
        from affecting the session accidentally."""
        if not self.logged_in:
            return
        self.setSession(None)

    #we've had some trouble with this method causing strange problems
    #(like infinite recursion). Possibly triggered by initialization failure,
    #and possibly due to some interaction with __getattr__.
    #Re-enabling with a small improvement
    def __del__(self):
        if self.__dict__:
            try:
                self.logout()
            except:
                pass

    def callMethod(self,name,*args,**opts):
        """compatibility wrapper for _callMethod"""
        return self._callMethod(name, args, opts)

    def _callMethod(self, name, args, kwargs):
        #pass named opts in a way the server can understand
        args = encode_args(*args,**kwargs)

        if self.multicall:
            self._calls.append({'methodName': name, 'params': args})
        else:
            if self.logged_in:
                sinfo = self.sinfo.copy()
                sinfo['callnum'] = self.callnum
                self.callnum += 1
                url = "%s?%s" %(self.baseurl,urllib.urlencode(sinfo))
                proxy = self.proxyClass(url,**self.proxyOpts)
            else:
                proxy = self.proxy
            tries = 0
            debug = self.opts.get('debug',False)
            max_retries = self.opts.get('max_retries',30)
            interval = self.opts.get('retry_interval',20)
            while tries <= max_retries:
                tries += 1
                try:
                    return proxy.__getattr__(name)(*args)
                except Fault, fault:
                    raise convertFault(fault)
                except (socket.error,socket.sslerror,xmlrpclib.ProtocolError),e:
                    if not self.logged_in:
                        raise
                    elif debug:
                        self.logger.debug("Try #%d for call %d (%s) failed: %s" % (tries, self.callnum, name, e))
                time.sleep(interval)
            raise RetryError, "reached maximum number of retries, last call failed with: %s" % sys.exc_info()[1]

    def multiCall(self):
        """Execute a multicall (multiple function calls passed to the server
        and executed at the same time, with results being returned in a batch).
        Before calling this method, the self.multicall field must have
        been set to True, and then one or more methods must have been called on
        the current session (those method calls will return None).  On executing
        the multicall, the self.multicall field will be reset to False
        (so subsequent method calls will be executed immediately)
        and results will be returned in a list.  The list will contain one element
        for each method added to the multicall, in the order it was added to the multicall.
        Each element of the list will be either a one-element list containing the result of the
        method call, or a map containing "faultCode" and "faultString" keys, describing the
        error that occurred during the method call."""
        if not self.multicall:
            raise GenericError, 'ClientSession.multicall must be set to True before calling multiCall()'
        if len(self._calls) == 0:
            return []

        try:
            return self.proxy.multiCall(self._calls)
        finally:
            self.multicall = False
            self._calls = []

    def __getattr__(self,name):
        #if name[:1] == '_':
        #    raise AttributeError, "no attribute %r" % name
        return VirtualMethod(self._callMethod,name)

    def uploadWrapper(self, localfile, path, name=None, callback=None):
        """upload a file in chunks using the uploadFile call"""
        # XXX - stick in a config or something
        start=time.time()
        blocksize=65536
        retries=3
        if name is None:
            name = os.path.basename(localfile)
        fo = file(localfile, "r")  #specify bufsize?
        totalsize = os.path.getsize(localfile)
        ofs = 0
        md5sum = md5.new()
        debug = self.opts.get('debug',False)
        if callback:
            callback(0, totalsize, 0, 0, 0)
        while True:
            lap = time.time()
            contents = fo.read(blocksize)
            md5sum.update(contents)
            size = len(contents)
            data = base64.encodestring(contents)
            if size == 0:
                # end of file, use offset = -1 to finalize upload
                offset = -1
                digest = md5sum.hexdigest()
                sz = ofs
            else:
                offset = ofs
                digest = md5.new(contents).hexdigest()
                sz = size
            del contents
            tries = 0
            while True:
                if debug:
                    self.logger.debug("uploadFile(%r,%r,%r,%r,%r,...)" %(path,name,sz,digest,offset))
                if self.callMethod('uploadFile', path, name, sz, digest, offset, data):
                    break
                if tries <= retries:
                    tries += 1
                    continue
                else:
                    raise GenericError, "Error uploading file %s, offset %d" %(path, offset)
            if size == 0:
                break
            ofs += size
            now = time.time()
            t1 = now - lap
            if t1 <= 0:
                t1 = 1
            t2 = now - start
            if t2 <= 0:
                t2 = 1
            if debug:
                self.logger.debug("Uploaded %d bytes in %f seconds (%f kbytes/sec)" % (size,t1,size/t1/1024))
            if debug:
                self.logger.debug("Total: %d bytes in %f seconds (%f kbytes/sec)" % (ofs,t2,ofs/t2/1024))
            if callback:
                callback(ofs, totalsize, size, t1, t2)
        fo.close()

    def downloadTaskOutput(self, taskID, fileName, offset=0, size=-1):
        """Download the file with the given name, generated by the task with the
        given ID.

        Note: This method does not work with multicall.
        """
        if self.multicall:
            raise GenericError, 'downloadTaskOutput() may not be called during a multicall'
        result = self.callMethod('downloadTaskOutput', taskID, fileName, offset, size)
        return base64.decodestring(result)

class DBHandler(logging.Handler):
    """
    A handler class which writes logging records, appropriately formatted,
    to a database.
    """
    def __init__(self, cnx, table, mapping=None):
        """
        Initialize the handler.

        A database connection and table name are required.
        """
        logging.Handler.__init__(self)
        self.cnx = cnx
        self.table = table
        if mapping is None:
            self.mapping = { 'message': '%(message)s' }
        else:
            self.mapping = mapping

    def emit(self, record):
        """
        Emit a record.

        If a formatter is specified, it is used to format the record.
        """
        try:
            cursor = self.cnx.cursor()
            columns = []
            values = []
            data = {}
            record.message = record.getMessage()
            for key, value in self.mapping.iteritems():
                value = str(value)
                if value.find("%(asctime)") >= 0:
                    if self.formatter:
                        fmt = self.formatter
                    else:
                        fmt = logging._defaultFormatter
                    record.asctime = fmt.formatTime(record, fmt.datefmt)
                columns.append(key)
                values.append("%%(%s)s" % key)
                data[key] = value % record.__dict__
                #values.append(_quote(value % record.__dict__))
            columns = ",".join(columns)
            values = ",".join(values)
            command = "INSERT INTO %s (%s) VALUES (%s)" % (self.table, columns, values)
            #note we're letting cursor.execute do the escaping
            cursor.execute(command,data)
            cursor.close()
            self.cnx.commit()
        except:
            self.handleError(record)

#used by parse_timestamp
TIMESTAMP_RE = re.compile("(\d+)-(\d+)-(\d+) (\d+):(\d+):(\d+)")

def parse_timestamp(ts):
    """Parse a timestamp returned from a query"""
    m = TIMESTAMP_RE.search(ts)
    t = tuple([int(x) for x in m.groups()]) + (0,0,0)
    return time.mktime(t)

def formatTime(value):
    """Format a timestamp so it looks nicer"""
    if not value:
        return ''
    elif isinstance(value, datetime.datetime):
        return value.strftime('%Y-%m-%d %H:%M:%S')
    else:
        # trim off the microseconds, if present
        dotidx = value.rfind('.')
        if dotidx != -1:
            return value[:dotidx]
        else:
            return value

def formatTimeLong(value):
    """Format a timestamp to a more human-reable format, i.e.:
    Sat, 07 Sep 2002 00:00:01 GMT
    """
    if not value:
        return ''
    else:
        # Assume the string value passed in is the local time
        localtime = time.mktime(time.strptime(formatTime(value), '%Y-%m-%d %H:%M:%S'))
        return time.strftime('%a, %d %b %Y %H:%M:%S %Z', time.localtime(localtime))

def buildLabel(buildInfo, showEpoch=False):
    """Format buildInfo (dict) into a descriptive label."""
    epoch = buildInfo['epoch']
    if showEpoch and epoch != None:
        epochStr = '%i:' % epoch
    else:
        epochStr = ''
    return '%s%s-%s-%s' % (epochStr, buildInfo['package_name'],
                           buildInfo['version'], buildInfo['release'])

def taskLabel(taskInfo):
    """Format taskInfo (dict) into a descriptive label."""
    method = taskInfo['method']
    arch = taskInfo['arch']
    extra = ''
    if method == 'build':
        if taskInfo.has_key('request'):
            source, target = taskInfo['request'][:2]
            if source.startswith('cvs://'):
                source = source[source.rfind('/') + 1:]
                source = source.replace('#', ':')
            else:
                source = os.path.basename(source)
            extra = '%s, %s' % (target, source)
    elif method == 'buildSRPMFromCVS':
        if taskInfo.has_key('request'):
            url = taskInfo['request'][0]
            url = url[url.rfind('/') + 1:]
            url = url.replace('#', ':')
            extra = url
    elif method == 'buildArch':
        if taskInfo.has_key('request'):
            srpm, tagID, arch = taskInfo['request'][:3]
            srpm = os.path.basename(srpm)
            extra = '%s, %s' % (srpm, arch)
    elif method == 'buildNotification':
        if taskInfo.has_key('request'):
            build = taskInfo['request'][1]
            extra = buildLabel(build)
    elif method == 'newRepo':
        pass
    elif method == 'prepRepo':
        if taskInfo.has_key('request'):
            tagInfo = taskInfo['request'][0]
            extra = tagInfo['name']
    elif method == 'createrepo':
        if taskInfo.has_key('request'):
            arch = taskInfo['request'][1]
            extra = arch
    elif method == 'dependantTask':
        if taskInfo.has_key('request'):
            extra = ', '.join([subtask[0] for subtask in taskInfo['request'][1]])
    elif method == 'chainbuild':
        if taskInfo.has_key('request'):
            extra = taskInfo['request'][1]
    elif method == 'waitrepo':
        if taskInfo.has_key('request'):
            extra = taskInfo['request'][0]
    
    if extra:
        return '%s (%s)' % (method, extra)
    else:
        return '%s (%s)' % (method, arch)

def _forceAscii(value):
    """Replace characters not in the 7-bit ASCII range
    with "?"."""
    return ''.join([(ord(c) <= 127) and c or '?' for c in value])

def fixEncoding(value, fallback='iso8859-15'):
    """
    Convert value to a 'str' object encoded as UTF-8.
    If value is not valid UTF-8 to begin with, assume it is
    encoded in the 'fallback' charset.
    """
    if not value:
        return value

    try:
        return value.decode('utf8').encode('utf8')
    except UnicodeDecodeError, err:
        return value.decode(fallback).encode('utf8')
                                                                                                
def add_file_logger(logger, fn):
    if not os.path.exists(fn):
        try:
            fh = open(fn, 'w')
            fh.close()
        except (ValueError, IOError):
            return
    if not os.path.isfile(fn):
        return
    if not os.access(fn,os.W_OK):
        return
    handler = logging.handlers.RotatingFileHandler(fn, maxBytes=1024*1024*10, backupCount=5)
    handler.setFormatter(logging.Formatter('%(asctime)s [%(levelname)s] %(name)s: %(message)s'))
    logging.getLogger(logger).addHandler(handler)

def add_stderr_logger(logger):
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter('%(asctime)s [%(levelname)s] {%(process)d} %(name)s:%(lineno)d %(message)s'))
    handler.setLevel(logging.DEBUG)
    logging.getLogger(logger).addHandler(handler)

def add_sys_logger(logger):
    # For remote logging;
    # address = ('host.example.com', logging.handlers.SysLogHandler.SYSLOG_UDP_PORT)
    address = "/dev/log"
    handler = logging.handlers.SysLogHandler(address=address,
                                             facility=logging.handlers.SysLogHandler.LOG_DAEMON)
    handler.setFormatter(logging.Formatter('%(name)s: %(message)s'))
    handler.setLevel(logging.INFO)
    logging.getLogger(logger).addHandler(handler)

def add_mail_logger(logger, addr):
    if not addr:
        return
    handler = logging.handlers.SMTPHandler("localhost",
                                           "%s@%s" % (pwd.getpwuid(os.getuid())[0], socket.getfqdn()),
                                           addr,
                                           "%s: error notice" % socket.getfqdn())
    handler.setFormatter(logging.Formatter('%(pathname)s:%(lineno)d [%(levelname)s] %(message)s'))
    handler.setLevel(logging.ERROR)
    logging.getLogger(logger).addHandler(handler)

def add_db_logger(logger, cnx):
    handler = DBHandler(cnx, "log_messages", {'message': '%(message)s',
                                              'message_time': '%(asctime)s',
                                              'logger_name': '%(name)s',
                                              'level': '%(levelname)s',
                                              'location': '%(pathname)s:%(lineno)d',
                                              'host': commands.getoutput("hostname"),
                                              })
    handler.setFormatter(logging.Formatter(datefmt='%Y-%m-%d %H:%M:%S'))
    logging.getLogger(logger).addHandler(handler)
    return handler

def remove_log_handler(logger, handler):
    logging.getLogger(logger).removeHandler(handler)
