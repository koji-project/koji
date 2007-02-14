#!/usr/bin/python
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

# This modules provides a thread-safe way of passing
# request context around in a global way
#    - db connections
#    - request data
#    - auth data

import thread

class _data(object):
    pass

class ThreadLocal(object):
    def __init__(self):
        object.__setattr__(self, '_tdict', {})

    # should probably be getattribute, but easier to debug this way
    def __getattr__(self, key):
        id = thread.get_ident()
        tdict = object.__getattribute__(self, '_tdict')
        if not tdict.has_key(id):
            raise AttributeError(key)
        data = tdict[id]
        return object.__getattribute__(data, key)

    def __setattr__(self, key, value):
        id = thread.get_ident()
        tdict = object.__getattribute__(self, '_tdict')
        if not tdict.has_key(id):
            tdict[id] = _data()
        data = tdict[id]
        return object.__setattr__(data,key,value)

    def __delattr__(self, key):
        id = thread.get_ident()
        tdict = object.__getattribute__(self, '_tdict')
        if not tdict.has_key(id):
            raise AttributeError(key)
        data = tdict[id]
        ret = object.__delattr__(data, key)
        if len(data.__dict__) == 0:
            del tdict[id]
        return ret

    def __str__(self):
        id = thread.get_ident()
        tdict = object.__getattribute__(self, '_tdict')
        return "(current thread: %s) {" % id  + \
            ", ".join([ "%s : %s" %(k,v.__dict__) for (k,v) in tdict.iteritems() ]) + \
            "}"

    def _threadclear(self):
        id = thread.get_ident()
        tdict = object.__getattribute__(self, '_tdict')
        if not tdict.has_key(id):
            return
        del tdict[id]


context = ThreadLocal()


if __name__ == '__main__':

    #testing

    #context.foo = 1
    #context.bar = 2
    print context
    #del context.bar
    print context

    import random
    import time
    def test():
        context.foo=random.random()
        time.sleep(1.5+random.random())
        context._threadclear()
        print context

    for x in xrange(1,10):
        thread.start_new_thread(test,())

    time.sleep(4)
    print
    print context

    context.foo = 1
    context.bar = 2
    print context.foo,context.bar
    print context
    context._threadclear()
    print context
