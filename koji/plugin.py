# koji plugin module
# Copyright (c) 2008-2014 Red Hat, Inc.
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

from __future__ import absolute_import

import logging
import sys
import traceback

import six

import koji
from koji.util import encode_datetime_recurse

try:
    import importlib
    import importlib.machinery
except ImportError:  # pragma: no cover
    # importlib not available for PY2, so we fall back to using imp
    import imp as imp
    importlib = None

# the available callback hooks and a list
# of functions to be called for each event
callbacks = {
    # hub
    'prePackageListChange': [],
    'postPackageListChange': [],
    'preTaskStateChange': [],
    'postTaskStateChange': [],
    'preBuildStateChange': [],
    'postBuildStateChange': [],
    'preImport': [],
    'postImport': [],
    'preRPMSign': [],
    'postRPMSign': [],
    'preTag': [],
    'postTag': [],
    'preUntag': [],
    'postUntag': [],
    'preRepoInit': [],
    'postRepoInit': [],
    'preRepoDone': [],
    'postRepoDone': [],
    'preCommit': [],
    'postCommit': [],
    # builder
    'preSCMCheckout': [],
    'postSCMCheckout': [],
    'postCreateDistRepo': [],
    'postCreateRepo': [],
}


class PluginTracker(object):

    def __init__(self, path=None, prefix='_koji_plugin__'):
        self.searchpath = path
        # prefix should not have a '.' in it, this can cause problems.
        self.prefix = prefix
        self.plugins = {}

    def load(self, name, path=None, reload=False):
        if name in self.plugins and not reload:
            return self.plugins[name]
        mod_name = name
        if self.prefix:
            # mod_name determines how the module is named in sys.modules
            # Using a prefix helps prevent overlap with other modules
            # (no '.' -- it causes problems)
            mod_name = self.prefix + name
        if mod_name in sys.modules and not reload:
            raise koji.PluginError('module name conflict: %s' % mod_name)
        if path is None:
            path = self.searchpath
        if path is None:
            raise koji.PluginError("empty module search path")
        file = None
        try:
            if importlib:
                orig_spec = importlib.machinery.PathFinder().find_spec(name, self.pathlist(path))
                plugin_spec = importlib.util.spec_from_file_location(mod_name, orig_spec.origin)
                plugin = importlib.util.module_from_spec(plugin_spec)
                sys.modules[mod_name] = plugin
                plugin_spec.loader.exec_module(plugin)
            else:
                file, pathname, description = imp.find_module(name, self.pathlist(path))
                plugin = imp.load_module(mod_name, file, pathname, description)
        except Exception:
            msg = 'Loading plugin %s failed' % name
            logging.getLogger('koji.plugin').error(msg)
            raise
        finally:
            if file:
                file.close()
        self.plugins[name] = plugin
        return plugin

    def get(self, name):
        return self.plugins.get(name)

    def pathlist(self, path):
        if isinstance(path, six.string_types):
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


def export_cli(f):
    """a decorator that marks a function as exported for CLI

    intended to be used by plugins
    the HandlerRegistry will export the function under its own name
    """
    setattr(f, 'exported_cli', True)
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
            local_alias = "%s.%s" % (module, f.__name__)
        else:
            local_alias = "%s.%s" % (module, alias)
        setattr(f, 'exported', True)
        setattr(f, 'export_module', module)
        setattr(f, 'export_alias', local_alias)
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


def convert_datetime(f):
    """Indicate that callback needs to receive datetime objects as strings"""
    setattr(f, 'convert_datetime', True)
    return f


def register_callback(cbtype, func):
    if cbtype not in callbacks:
        raise koji.PluginError('"%s" is not a valid callback type' % cbtype)
    if not callable(func):
        raise koji.PluginError('%s is not callable' % getattr(func, '__name__', 'function'))
    callbacks[cbtype].append(func)


def run_callbacks(cbtype, *args, **kws):
    if cbtype not in callbacks:
        raise koji.PluginError('"%s" is not a valid callback type' % cbtype)
    cache = {}
    for func in callbacks[cbtype]:
        cb_args, cb_kwargs = _fix_cb_args(func, args, kws, cache)
        try:
            func(cbtype, *cb_args, **cb_kwargs)
        except Exception:
            msg = 'Error running %s callback from %s' % (cbtype, func.__module__)
            if getattr(func, 'failure_is_an_option', False):
                logging.getLogger('koji.plugin').warning(msg, exc_info=True)
            else:
                tb = ''.join(traceback.format_exception(*sys.exc_info()))
                raise koji.CallbackError('%s:\n%s' % (msg, tb))


def _fix_cb_args(func, args, kwargs, cache):
    if getattr(func, 'convert_datetime', False):
        if id(args) in cache:
            args = cache[id(args)]
        else:
            val = encode_datetime_recurse(args)
            cache[id(args)] = val
            args = val
        if id(kwargs) in cache:
            kwargs = cache[id(kwargs)]
        else:
            val = encode_datetime_recurse(kwargs)
            cache[id(kwargs)] = val
            kwargs = val
    return args, kwargs
