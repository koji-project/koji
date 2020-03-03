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

# This modules provides a thread-safe way of passing
# request context around in a global way
#    - db connections
#    - request data
#    - auth data

from __future__ import absolute_import

import six
import six.moves._thread


class _data(object):
    pass


class ThreadLocal(object):
    def __init__(self):
        object.__setattr__(self, '_tdict', {})

    # should probably be getattribute, but easier to debug this way
    def __getattr__(self, key):
        id = six.moves._thread.get_ident()
        tdict = object.__getattribute__(self, '_tdict')
        if id not in tdict:
            raise AttributeError(key)
        data = tdict[id]
        return object.__getattribute__(data, key)

    def __setattr__(self, key, value):
        id = six.moves._thread.get_ident()
        tdict = object.__getattribute__(self, '_tdict')
        if id not in tdict:
            tdict[id] = _data()
        data = tdict[id]
        return object.__setattr__(data, key, value)

    def __delattr__(self, key):
        id = six.moves._thread.get_ident()
        tdict = object.__getattribute__(self, '_tdict')
        if id not in tdict:
            raise AttributeError(key)
        data = tdict[id]
        ret = object.__delattr__(data, key)
        if len(data.__dict__) == 0:
            del tdict[id]
        return ret

    def __str__(self):
        id = six.moves._thread.get_ident()
        tdict = object.__getattribute__(self, '_tdict')
        return "(current thread: %s) {" % id + \
            ", ".join(["%s : %s" % (k, v.__dict__) for (k, v) in six.iteritems(tdict)]) + \
            "}"

    def _threadclear(self):
        id = six.moves._thread.get_ident()
        tdict = object.__getattribute__(self, '_tdict')
        if id not in tdict:
            return
        del tdict[id]


context = ThreadLocal()
