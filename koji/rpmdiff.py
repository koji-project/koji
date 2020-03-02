# Copyright (C) 2006 Mandriva; 2009-2014 Red Hat, Inc.
# Authors: Frederic Lepied, Florian Festi
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA  02110-1301 USA
#
# This library and program is heavily based on rpmdiff from the rpmlint package
# It was modified to be used as standalone library for the Koji project.

from __future__ import absolute_import

import hashlib
import itertools
import json
import os

import rpm
import six
from six.moves import zip


class BytesJSONEncoder(json.JSONEncoder):
    def default(self, o):
        if six.PY3 and isinstance(o, bytes):
            return o.decode('utf-8')
        return json.JSONEncoder.default(self, o)


class Rpmdiff:

    # constants

    TAGS = (rpm.RPMTAG_NAME, rpm.RPMTAG_SUMMARY,
            rpm.RPMTAG_DESCRIPTION, rpm.RPMTAG_GROUP,
            rpm.RPMTAG_LICENSE, rpm.RPMTAG_URL,
            rpm.RPMTAG_PREIN, rpm.RPMTAG_POSTIN,
            rpm.RPMTAG_PREUN, rpm.RPMTAG_POSTUN)

    PRCO = ('REQUIRES', 'PROVIDES', 'CONFLICTS', 'OBSOLETES')

    # {fname : (size, mode, mtime, flags, dev, inode,
    #          nlink, state, vflags, user, group, digest)}
    __FILEIDX = [['S', 0],
                 ['M', 1],
                 ['5', 11],
                 ['D', 4],
                 ['N', 6],
                 ['L', 7],
                 ['V', 8],
                 ['U', 9],
                 ['G', 10],
                 ['F', 3],
                 ['T', 2]]

    try:
        if rpm.RPMSENSE_SCRIPT_PRE:
            PREREQ_FLAG = rpm.RPMSENSE_PREREQ | rpm.RPMSENSE_SCRIPT_PRE |\
                rpm.RPMSENSE_SCRIPT_POST | rpm.RPMSENSE_SCRIPT_PREUN |\
                rpm.RPMSENSE_SCRIPT_POSTUN
    except AttributeError:
        try:
            PREREQ_FLAG = rpm.RPMSENSE_PREREQ
        except Exception:
            # (proyvind): This seems ugly, but then again so does
            #            this whole check as well.
            PREREQ_FLAG = False

    DEPFORMAT = '%-12s%s %s %s %s'
    FORMAT = '%-12s%s'

    ADDED = 'added'
    REMOVED = 'removed'

    # code starts here

    def __init__(self, old, new, ignore=None):
        self.result = []
        self.old_data = {'tags': {}, 'ignore': ignore}
        self.new_data = {'tags': {}, 'ignore': ignore}
        if ignore is None:
            ignore = set()
        else:
            ignore = set(ignore)

        old = self.__load_pkg(old)
        new = self.__load_pkg(new)

        # Compare single tags
        for tag in self.TAGS:
            old_tag = old[tag]
            new_tag = new[tag]
            self.old_data['tags'][tag] = old[tag]
            self.new_data['tags'][tag] = new[tag]
            if old_tag != new_tag:
                tagname = rpm.tagnames[tag]
                if old_tag is None:
                    self.__add(self.FORMAT, (self.ADDED, tagname))
                elif new_tag is None:
                    self.__add(self.FORMAT, (self.REMOVED, tagname))
                else:
                    self.__add(self.FORMAT, ('S.5........', tagname))

        # compare Provides, Requires, ...
        for tag in self.PRCO:
            self.__comparePRCOs(old, new, tag)

        # compare the files

        old_files_dict = self.__fileIteratorToDict(old.fiFromHeader())
        new_files_dict = self.__fileIteratorToDict(new.fiFromHeader())
        files = sorted(set(itertools.chain(six.iterkeys(old_files_dict),
                                           six.iterkeys(new_files_dict))))
        self.old_data['files'] = old_files_dict
        self.new_data['files'] = new_files_dict

        for f in files:
            diff = 0

            old_file = old_files_dict.get(f)
            new_file = new_files_dict.get(f)

            if not old_file:
                self.__add(self.FORMAT, (self.ADDED, f))
            elif not new_file:
                self.__add(self.FORMAT, (self.REMOVED, f))
            else:
                format = ''
                for entry in self.__FILEIDX:
                    # entry = [character, value]
                    if entry[0] in ignore:
                        # erase fields which are ignored
                        old_file[entry[1]] = None
                        new_file[entry[1]] = None
                        format = format + '.'
                    elif old_file[entry[1]] != new_file[entry[1]]:
                        format = format + entry[0]
                        diff = 1
                    else:
                        format = format + '.'
                if diff:
                    self.__add(self.FORMAT, (format, f))

    # return a report of the differences
    def textdiff(self):
        return '\n'.join((format % data for format, data in self.result))

    # do the two rpms differ
    def differs(self):
        return bool(self.result)

    # add one differing item
    def __add(self, format, data):
        self.result.append((format, data))

    # load a package from a file or from the installed ones
    def __load_pkg(self, filename):
        ts = rpm.ts()
        f = os.open(filename, os.O_RDONLY)
        hdr = ts.hdrFromFdno(f)
        os.close(f)
        return hdr

    # output the right string according to RPMSENSE_* const
    def sense2str(self, sense):
        s = ""
        for tag, char in ((rpm.RPMSENSE_LESS, "<"),
                          (rpm.RPMSENSE_GREATER, ">"),
                          (rpm.RPMSENSE_EQUAL, "=")):
            if sense & tag:
                s += char
        return s

    # compare Provides, Requires, Conflicts, Obsoletes
    def __comparePRCOs(self, old, new, name):
        oldflags = old[name[:-1] + 'FLAGS']
        newflags = new[name[:-1] + 'FLAGS']
        # fix buggy rpm binding not returning list for single entries
        if not isinstance(oldflags, list):
            oldflags = [oldflags]
        if not isinstance(newflags, list):
            newflags = [newflags]

        o = list(zip(old[name], oldflags, old[name[:-1] + 'VERSION']))
        n = list(zip(new[name], newflags, new[name[:-1] + 'VERSION']))

        if name == 'PROVIDES':  # filter our self provide
            oldNV = (old['name'], rpm.RPMSENSE_EQUAL,
                     "%s-%s" % (old['version'], old['release']))
            newNV = (new['name'], rpm.RPMSENSE_EQUAL,
                     "%s-%s" % (new['version'], new['release']))
            o = [entry for entry in o if entry != oldNV]
            n = [entry for entry in n if entry != newNV]

        self.old_data[name] = sorted(o)
        self.new_data[name] = sorted(n)

        for oldentry in o:
            if oldentry not in n:
                if name == 'REQUIRES' and oldentry[1] & self.PREREQ_FLAG:
                    tagname = 'PREREQ'
                else:
                    tagname = name
                self.__add(self.DEPFORMAT,
                           (self.REMOVED, tagname, oldentry[0],
                            self.sense2str(oldentry[1]), oldentry[2]))
        for newentry in n:
            if newentry not in o:
                if name == 'REQUIRES' and newentry[1] & self.PREREQ_FLAG:
                    tagname = 'PREREQ'
                else:
                    tagname = name
                self.__add(self.DEPFORMAT,
                           (self.ADDED, tagname, newentry[0],
                            self.sense2str(newentry[1]), newentry[2]))

    def __fileIteratorToDict(self, fi):
        result = {}
        for filedata in fi:
            result[filedata[0]] = list(filedata[1:])
        return result

    def kojihash(self, new=False):
        """return hashed data for use in koji"""
        if new:
            data = self.new_data
        else:
            data = self.old_data
        if not data:
            raise ValueError("rpm header data are empty")
        s = json.dumps(data, sort_keys=True, cls=BytesJSONEncoder)
        if six.PY3:
            s = s.encode('utf-8')
        return hashlib.sha256(s).hexdigest()
