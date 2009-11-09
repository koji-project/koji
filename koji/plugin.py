# koji plugin module
# Copyright (c) 2008 Red Hat
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

import imp
import koji
import logging
import sys
import traceback

# set this up for use by the plugins
# we want log output to go to Apache's error_log
logger = logging.getLogger('koji.plugin')
logger.addHandler(logging.StreamHandler(sys.stderr))
logger.setLevel(logging.INFO)

# the available callback hooks and a list
# of functions to be called for each event
callbacks = {
    'prePackageListChange':   [],
    'postPackageListChange':  [],
    'preTaskStateChange':     [],
    'postTaskStateChange':    [],
    'preBuildStateChange':    [],
    'postBuildStateChange':   [],
    'preImport':              [],
    'postImport':             [],
    'preTag':                 [],
    'postTag':                [],
    'preUntag':               [],
    'postUntag':              [],
    'preRepoInit':            [],
    'postRepoInit':           [],
    'preRepoDone':            [],
    'postRepoDone':           []
    }

class PluginTracker(object):

    def __init__(self, path=None, prefix='_koji_plugin__'):
        self.searchpath = path
        #prefix should not have a '.' in it, this can cause problems.
        self.prefix = prefix
        self.plugins = {}

    def load(self, name, path=None, reload=False):
        if self.plugins.has_key(name) and not reload:
            return self.plugins[name]
        mod_name = name
        if self.prefix:
            #mod_name determines how the module is named in sys.modules
            #Using a prefix helps prevent overlap with other modules
            #(no '.' -- it causes problems)
            mod_name = self.prefix + name
        if sys.modules.has_key(mod_name) and not reload:
            raise koji.PluginError, 'module name conflict: %s' % mod_name
        if path is None:
            path = self.searchpath
        if path is None:
            raise koji.PluginError, "empty module search path"
        file, pathname, description = imp.find_module(name, self.pathlist(path))
        try:
            plugin = imp.load_module(mod_name, file, pathname, description)
        finally:
            file.close()
        self.plugins[name] = plugin
        return plugin

    def get(self, name):
        return self.plugins.get(name)

    def pathlist(self, path):
        if isinstance(path, basestring):
            return [path]
        else:
            return path


# some decorators used by plugins
def export(f):
    """a decorator that marks a function as exported

    intended to be used by plugins
    the HandlerRegistry will export the function under its own name
    """
    setattr(f, 'exported', True)
    return f

def export_as(alias):
    """returns a decorator that marks a function as exported and gives it an alias

    indended to be used by plugins
    """
    def dec(f):
        setattr(f, 'exported', True)
        setattr(f, 'export_alias', alias)
        return f
    return dec

def export_in(module, alias=None):
    """returns a decorator that marks a function as exported with a module prepended

    optionally, can also alias the function within the module
    indended to be used by plugins
    """
    def dec(f):
        if alias is None:
            alias = "%s.%s" % (module, f.__name__)
        else:
            alias = "%s.%s" % (module, alias)
        setattr(f, 'exported', True)
        setattr(f, 'export_module', module)
        setattr(f, 'export_alias', alias)
        return f
    return dec

def callback(*cbtypes):
    """A decorator that indicates a function is a callback.
    cbtypes is a list of callback types to register for.  Valid
    callback types are listed in the plugin module.

    Intended to be used by plugins.
    """
    def dec(f):
        setattr(f, 'callbacks', cbtypes)
        return f
    return dec

def ignore_error(f):
    """a decorator that marks a callback as ok to fail

    intended to be used by plugins
    """
    setattr(f, 'failure_is_an_option', True)
    return f

def register_callback(cbtype, func):
    if not cbtype in callbacks:
        raise koji.PluginError, '"%s" is not a valid callback type' % cbtype
    if not callable(func):
        raise koji.PluginError, '%s is not callable' % getattr(func, '__name__', 'function')
    callbacks[cbtype].append(func)

def run_callbacks(cbtype, *args, **kws):
    if not cbtype in callbacks:
        raise koji.PluginError, '"%s" is not a valid callback type' % cbtype
    for func in callbacks[cbtype]:
        try:
            func(cbtype, *args, **kws)
        except:
            tb = ''.join(traceback.format_exception(*sys.exc_info()))
            msg = 'Error running %s callback from %s: %s' % (cbtype, func.__module__, tb)
            if getattr(func, 'failure_is_an_option', False):
                logging.getLogger('koji.plugin').warn('%s: %s' % (msg, tb))
            else:
                raise koji.CallbackError, msg
