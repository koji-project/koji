# kojixmlrpc - an XMLRPC interface for koji.
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

from ConfigParser import RawConfigParser
import inspect
import logging
import os
import sys
import time
import traceback
import types
import pprint
import resource
import xmlrpclib
from xmlrpclib import getparser,dumps,Fault
from koji.server import WSGIWrapper

import koji
import koji.auth
import koji.db
import koji.plugin
import koji.policy
import koji.util
from koji.context import context


# Workaround to allow xmlrpclib deal with iterators
class Marshaller(xmlrpclib.Marshaller):

    dispatch = xmlrpclib.Marshaller.dispatch.copy()

    def dump_generator(self, value, write):
        dump = self.__dump
        write("<value><array><data>\n")
        for v in value:
            dump(v, write)
        write("</data></array></value>\n")
    dispatch[types.GeneratorType] = dump_generator

xmlrpclib.Marshaller = Marshaller


class HandlerRegistry(object):
    """Track handlers for RPC calls"""

    def __init__(self):
        self.funcs = {}
        #introspection functions
        self.register_function(self.list_api, name="_listapi")
        self.register_function(self.system_listMethods, name="system.listMethods")
        self.register_function(self.system_methodSignature, name="system.methodSignature")
        self.register_function(self.system_methodHelp, name="system.methodHelp")
        self.argspec_cache = {}

    def register_function(self, function, name = None):
        if name is None:
            name = function.__name__
        self.funcs[name] = function

    def register_module(self, instance, prefix=None):
        """Register all the public functions in an instance with prefix prepended

        For example
            h.register_module(exports,"pub.sys")
        will register the methods of exports with names like
            pub.sys.method1
            pub.sys.method2
            ...etc
        """
        for name in dir(instance):
            if name.startswith('_'):
                continue
            function = getattr(instance, name)
            if not callable(function):
                continue
            if prefix is not None:
                name = "%s.%s" %(prefix,name)
            self.register_function(function, name=name)

    def register_instance(self,instance):
        self.register_module(instance)

    def register_plugin(self, plugin):
        """Scan a given plugin for handlers

        Handlers are functions marked with one of the decorators defined in koji.plugin
        """
        for v in vars(plugin).itervalues():
            if isinstance(v, (types.ClassType, types.TypeType)):
                #skip classes
                continue
            if callable(v):
                if getattr(v, 'exported', False):
                    if hasattr(v, 'export_alias'):
                        name = getattr(v, 'export_alias')
                    else:
                        name = v.__name__
                    self.register_function(v, name=name)
                if getattr(v, 'callbacks', None):
                    for cbtype in v.callbacks:
                        koji.plugin.register_callback(cbtype, v)

    def getargspec(self, func):
        ret = self.argspec_cache.get(func)
        if ret:
            return ret
        ret = tuple(inspect.getargspec(func))
        if inspect.ismethod(func) and func.im_self:
            # bound method, remove first arg
            args, varargs, varkw, defaults = ret
            if args:
                aname = args[0] #generally "self"
                del args[0]
                if defaults and aname in defaults:
                    # shouldn't happen, but...
                    del defaults[aname]
        return ret

    def list_api(self):
        funcs = []
        for name,func in self.funcs.items():
            #the keys in self.funcs determine the name of the method as seen over xmlrpc
            #func.__name__ might differ (e.g. for dotted method names)
            args = self._getFuncArgs(func)
            argspec = self.getargspec(func)
            funcs.append({'name': name,
                          'doc': func.__doc__,
                          'argspec': argspec,
                          'argdesc': inspect.formatargspec(*argspec),
                          'args': args})
        return funcs

    def _getFuncArgs(self, func):
        args = []
        for x in range(0, func.func_code.co_argcount):
            if x == 0 and func.func_code.co_varnames[x] == "self":
                continue
            if func.func_defaults and func.func_code.co_argcount - x <= len(func.func_defaults):
                args.append((func.func_code.co_varnames[x], func.func_defaults[x - func.func_code.co_argcount + len(func.func_defaults)]))
            else:
                args.append(func.func_code.co_varnames[x])
        return args

    def system_listMethods(self):
        return self.funcs.keys()

    def system_methodSignature(self, method):
        #it is not possible to autogenerate this data
        return 'signatures not supported'

    def system_methodHelp(self, method):
        func = self.funcs.get(method)
        if func is None:
            return ""
        args = inspect.formatargspec(*self.getargspec(func))
        ret = '%s%s' % (method, args)
        if func.__doc__:
            ret += "\ndescription: %s" % func.__doc__
        return ret

    def get(self, name):
        func = self.funcs.get(name, None)
        if func is None:
            raise koji.GenericError, "Invalid method: %s" % name
        return func


class HandlerAccess(object):
    """This class is used to grant access to the rpc handlers"""

    def __init__(self, registry):
        self.__reg = registry

    def call(self, __name, *args, **kwargs):
        return self.__reg.get(__name)(*args, **kwargs)

    def get(self, name):
        return self.__reg.get(name)


class ModXMLRPCRequestHandler(object):
    """Simple XML-RPC handler for mod_python environment"""

    def __init__(self, handlers):
        self.traceback = False
        self.handlers = handlers  #expecting HandlerRegistry instance
        self.logger = logging.getLogger('koji.xmlrpc')

    def _get_handler(self, name):
        # just a wrapper so we can handle multicall ourselves
        # we don't register multicall since the registry will outlive our instance
        if name in ('multiCall', 'system.multicall'):
            return self.multiCall
        else:
            return self.handlers.get(name)

    def _read_request(self, stream):
        parser, unmarshaller = getparser()
        rlen = 0
        maxlen = opts.get('MaxRequestLength', None)
        while True:
            chunk = stream.read(8192)
            if not chunk:
                break
            rlen += len(chunk)
            if maxlen and rlen > maxlen:
                raise koji.GenericError, 'Request too long'
            parser.feed(chunk)
        parser.close()
        return unmarshaller.close(), unmarshaller.getmethodname()

    def _wrap_handler(self, handler, environ):
        """Catch exceptions and encode response of handler"""

        # generate response
        try:
            response = handler(environ)
            # wrap response in a singleton tuple
            response = (response,)
            response = dumps(response, methodresponse=1, allow_none=1)
        except Fault, fault:
            self.traceback = True
            response = dumps(fault)
        except:
            self.traceback = True
            # report exception back to server
            e_class, e = sys.exc_info()[:2]
            faultCode = getattr(e_class,'faultCode',1)
            tb_type = context.opts.get('KojiTraceback',None)
            tb_str = ''.join(traceback.format_exception(*sys.exc_info()))
            if issubclass(e_class, koji.GenericError):
                if context.opts.get('KojiDebug'):
                    if tb_type == "extended":
                        faultString = koji.format_exc_plus()
                    else:
                        faultString = tb_str
                else:
                    faultString = str(e)
            else:
                if tb_type == "normal":
                    faultString = tb_str
                elif tb_type == "extended":
                    faultString = koji.format_exc_plus()
                else:
                    faultString = "%s: %s" % (e_class,e)
            self.logger.warning(tb_str)
            response = dumps(Fault(faultCode, faultString))

        return response

    def handle_upload(self, environ):
        #uploads can't be in a multicall
        context.method = None
        self.check_session()
        self.enforce_lockout()
        return kojihub.handle_upload(environ)

    def handle_rpc(self, environ):
        params, method = self._read_request(environ['wsgi.input'])
        return self._dispatch(method, params)

    def check_session(self):
        if not hasattr(context,"session"):
            #we may be called again by one of our meta-calls (like multiCall)
            #so we should only create a session if one does not already exist
            context.session = koji.auth.Session()
            try:
                context.session.validate()
            except koji.AuthLockError:
                #might be ok, depending on method
                if context.method not in ('exclusiveSession','login', 'krbLogin', 'logout'):
                    raise

    def enforce_lockout(self):
        if context.opts.get('LockOut') and \
            context.method not in ('login', 'krbLogin', 'sslLogin', 'logout') and \
            not context.session.hasPerm('admin'):
            raise koji.ServerOffline, "Server disabled for maintenance"

    def _dispatch(self, method, params):
        func = self._get_handler(method)
        context.method = method
        context.params = params
        self.check_session()
        self.enforce_lockout()
        # handle named parameters
        params, opts = koji.decode_args(*params)

        if self.logger.isEnabledFor(logging.INFO):
            self.logger.info("Handling method %s for session %s (#%s)",
                            method, context.session.id, context.session.callnum)
            if method != 'uploadFile' and self.logger.isEnabledFor(logging.DEBUG):
                self.logger.debug("Params: %s", pprint.pformat(params))
                self.logger.debug("Opts: %s", pprint.pformat(opts))
            start = time.time()

        ret = koji.util.call_with_argcheck(func, params, opts)

        if self.logger.isEnabledFor(logging.INFO):
            rusage = resource.getrusage(resource.RUSAGE_SELF)
            self.logger.info("Completed method %s for session %s (#%s): %f seconds, rss %s, stime %f",
                            method, context.session.id, context.session.callnum,
                            time.time()-start,
                            rusage.ru_maxrss, rusage.ru_stime)

        return ret

    def multiCall(self, calls):
        """Execute a multicall.  Execute each method call in the calls list, collecting
        results and errors, and return those as a list."""
        results = []
        for call in calls:
            try:
                result = self._dispatch(call['methodName'], call['params'])
            except Fault, fault:
                results.append({'faultCode': fault.faultCode, 'faultString': fault.faultString})
            except:
                # transform unknown exceptions into XML-RPC Faults
                # don't create a reference to full traceback since this creates
                # a circular reference.
                exc_type, exc_value = sys.exc_info()[:2]
                faultCode = getattr(exc_type, 'faultCode', 1)
                faultString = ', '.join(exc_value.args)
                trace = traceback.format_exception(*sys.exc_info())
                # traceback is not part of the multicall spec, but we include it for debugging purposes
                results.append({'faultCode': faultCode, 'faultString': faultString, 'traceback': trace})
            else:
                results.append([result])

        return results

    def handle_request(self,req):
        """Handle a single XML-RPC request"""

        pass
        #XXX no longer used


def offline_reply(start_response, msg=None):
    """Send a ServerOffline reply"""
    faultCode = koji.ServerOffline.faultCode
    if msg is None:
        faultString = "server is offline"
    else:
        faultString = msg
    response = dumps(Fault(faultCode, faultString))
    headers = [
        ('Content-Length', str(len(response))),
        ('Content-Type', "text/xml"),
    ]
    start_response('200 OK', headers)
    return [response]

def load_config(environ):
    """Load configuration options

    Options are read from a config file. The config file location is
    controlled by the PythonOption ConfigFile in the httpd config.

    Backwards compatibility:
        - if ConfigFile is not set, opts are loaded from http config
        - if ConfigFile is set, then the http config must not provide Koji options
        - In a future version we will load the default hub config regardless
        - all PythonOptions (except ConfigFile) are now deprecated and support for them
          will disappear in a future version of Koji
    """
    logger = logging.getLogger("koji")
    #get our config file(s)
    if 'modpy.opts' in environ:
        modpy_opts = environ.get('modpy.opts')
        cf = modpy_opts.get('ConfigFile', None)
        # to aid in the transition from PythonOptions to hub.conf, we only load
        # the configfile if it is explicitly configured
        if cf == '/etc/koji-hub/hub.conf':
            cfdir =  modpy_opts.get('ConfigDir', '/etc/koji-hub/hub.conf.d')
        else:
            cfdir =  modpy_opts.get('ConfigDir', None)
        if not cf and not cfdir:
            logger.warn('Warning: configuring Koji via PythonOptions is deprecated. Use hub.conf')
    else:
        cf = environ.get('koji.hub.ConfigFile', '/etc/koji-hub/hub.conf')
        cfdir = environ.get('koji.hub.ConfigDir', '/etc/koji-hub/hub.conf.d')
        modpy_opts = {}
    if cfdir:
        configs = koji.config_directory_contents(cfdir)
    else:
        configs = []
    if cf and os.path.isfile(cf):
        configs.append(cf)
    if configs:
        config = RawConfigParser()
        config.read(configs)
    else:
        config = None
    cfgmap = [
        #option, type, default
        ['DBName', 'string', None],
        ['DBUser', 'string', None],
        ['DBHost', 'string', None],
        ['DBhost', 'string', None],   # alias for backwards compatibility
        ['DBPass', 'string', None],
        ['KojiDir', 'string', None],

        ['AuthPrincipal', 'string', None],
        ['AuthKeytab', 'string', None],
        ['ProxyPrincipals', 'string', ''],
        ['HostPrincipalFormat', 'string', None],

        ['DNUsernameComponent', 'string', 'CN'],
        ['ProxyDNs', 'string', ''],

        ['LoginCreatesUser', 'boolean', True],
        ['KojiWebURL', 'string', 'http://localhost.localdomain/koji'],
        ['EmailDomain', 'string', None],
        ['NotifyOnSuccess', 'boolean', True],
        ['DisableNotifications', 'boolean', False],

        ['Plugins', 'string', ''],
        ['PluginPath', 'string', '/usr/lib/koji-hub-plugins'],

        ['KojiDebug', 'boolean', False],
        ['KojiTraceback', 'string', None],
        ['VerbosePolicy', 'boolean', False],
        ['EnableFunctionDebug', 'boolean', False],

        ['LogLevel', 'string', 'WARNING'],
        ['LogFormat', 'string', '%(asctime)s [%(levelname)s] m=%(method)s u=%(user_name)s p=%(process)s r=%(remoteaddr)s %(name)s: %(message)s'],

        ['MissingPolicyOk', 'boolean', True],
        ['EnableMaven', 'boolean', False],
        ['EnableWin', 'boolean', False],
        ['EnableImageMigration', 'boolean', False],

        ['RLIMIT_AS', 'string', None],
        ['RLIMIT_CORE', 'string', None],
        ['RLIMIT_CPU', 'string', None],
        ['RLIMIT_DATA', 'string', None],
        ['RLIMIT_FSIZE', 'string', None],
        ['RLIMIT_MEMLOCK', 'string', None],
        ['RLIMIT_NOFILE', 'string', None],
        ['RLIMIT_NPROC', 'string', None],
        ['RLIMIT_OFILE', 'string', None],
        ['RLIMIT_RSS', 'string', None],
        ['RLIMIT_STACK', 'string', None],

        ['MemoryWarnThreshold', 'integer', 5000],
        ['MaxRequestLength', 'integer', 4194304],

        ['LockOut', 'boolean', False],
        ['ServerOffline', 'boolean', False],
        ['OfflineMessage', 'string', None],
    ]
    opts = {}
    for name, dtype, default in cfgmap:
        if config:
            key = ('hub', name)
            if config.has_option(*key):
                if dtype == 'integer':
                    opts[name] = config.getint(*key)
                elif dtype == 'boolean':
                    opts[name] = config.getboolean(*key)
                else:
                    opts[name] = config.get(*key)
            else:
                opts[name] = default
        else:
            if modpy_opts.get(name, None) is not None:
                if dtype == 'integer':
                    opts[name] = int(modpy_opts.get(name))
                elif dtype == 'boolean':
                    opts[name] = modpy_opts.get(name).lower() in ('yes', 'on', 'true', '1')
                else:
                    opts[name] = modpy_opts.get(name)
            else:
                opts[name] = default
    if opts['DBHost'] is None:
        opts['DBHost'] = opts['DBhost']
    # load policies
    # (only from config file)
    if config and config.has_section('policy'):
        #for the moment, we simply transfer the policy conf to opts
        opts['policy'] = dict(config.items('policy'))
    else:
        opts['policy'] = {}
    for pname, text in _default_policies.iteritems():
        opts['policy'].setdefault(pname, text)
    # use configured KojiDir
    if opts.get('KojiDir') is not None:
        koji.BASEDIR = opts['KojiDir']
        koji.pathinfo.topdir = opts['KojiDir']
    return opts


def load_plugins(opts):
    """Load plugins specified by our configuration"""
    if not opts['Plugins']:
        return
    logger = logging.getLogger('koji.plugins')
    tracker = koji.plugin.PluginTracker(path=opts['PluginPath'].split(':'))
    for name in opts['Plugins'].split():
        logger.info('Loading plugin: %s', name)
        try:
            tracker.load(name)
        except Exception:
            logger.error(''.join(traceback.format_exception(*sys.exc_info())))
            #make this non-fatal, but set ServerOffline
            opts['ServerOffline'] = True
            opts['OfflineMessage'] = 'configuration error'
    return tracker

_default_policies = {
    'build_from_srpm' : '''
            has_perm admin :: allow
            all :: deny
            ''',
    'build_from_repo_id' : '''
            has_perm admin :: allow
            all :: deny
            ''',
    'package_list' : '''
            has_perm admin :: allow
            all :: deny
            ''',
    'channel' : '''
            has req_channel :: req
            is_child_task :: parent
            all :: use default
            ''',
    'vm' : '''
            has_perm admin win-admin :: allow
            all :: deny
           '''
}

def get_policy(opts, plugins):
    if not opts.get('policy'):
        return
    #first find available policy tests
    alltests = [koji.policy.findSimpleTests([vars(kojihub), vars(koji.policy)])]
    # we delay merging these to allow a test to be overridden for a specific policy
    for plugin_name in opts.get('Plugins', '').split():
        alltests.append(koji.policy.findSimpleTests(vars(plugins.get(plugin_name))))
    policy = {}
    for pname, text in opts['policy'].iteritems():
        #filter/merge tests
        merged = {}
        for tests in alltests:
            # tests can be limited to certain policies by setting a class variable
            for name, test in tests.iteritems():
                if hasattr(test, 'policy'):
                    if isinstance(test.policy, basestring):
                        if pname != test.policy:
                            continue
                    elif pname not in test.policy:
                        continue
                # in case of name overlap, last one wins
                # hence plugins can override builtin tests
                merged[name] = test
        policy[pname] = koji.policy.SimpleRuleSet(text.splitlines(), merged)
    return policy


class HubFormatter(logging.Formatter):
    """Support some koji specific fields in the format string"""

    def format(self, record):
        record.method = getattr(context, 'method', None)
        if hasattr(context, 'environ'):
            record.remoteaddr = "%s:%s" % (
                context.environ.get('REMOTE_ADDR', '?'),
                context.environ.get('REMOTE_PORT', '?'))
        else:
            record.remoteaddr = "?:?"
        if hasattr(context, 'session'):
            record.user_id = context.session.user_id
            record.session_id = context.session.id
            record.callnum = context.session.callnum
            record.user_name = context.session.user_data.get('name')
        else:
            record.user_id = None
            record.session_id = None
            record.callnum = None
            record.user_name = None
        return logging.Formatter.format(self, record)

def setup_logging1():
    """Set up basic logging, before options are loaded"""
    global log_handler
    logger = logging.getLogger("koji")
    logger.setLevel(logging.WARNING)
    #stderr logging (stderr goes to httpd logs)
    log_handler = logging.StreamHandler()
    log_format = '%(asctime)s [%(levelname)s] SETUP p=%(process)s %(name)s: %(message)s'
    log_handler.setFormatter(HubFormatter(log_format))
    log_handler.setLevel(logging.DEBUG)
    logger.addHandler(log_handler)

def setup_logging2(opts):
    global log_handler
    """Adjust logging based on configuration options"""
    #determine log level
    level = opts['LogLevel']
    valid_levels = ('DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL')
    # the config value can be a single level name or a series of
    # logger:level names pairs. processed in order found
    default = None
    for part in level.split():
        pair = part.split(':', 1)
        if len(pair) == 2:
            name, level = pair
        else:
            name = 'koji'
            level = part
            default = level
        if level not in valid_levels:
            raise koji.GenericError, "Invalid log level: %s" % level
        #all our loggers start with koji
        if name == '':
            name = 'koji'
            default = level
        elif name.startswith('.'):
            name = 'koji' + name
        elif not name.startswith('koji'):
            name = 'koji.' + name
        level_code = logging._levelNames[level]
        logging.getLogger(name).setLevel(level_code)
    logger = logging.getLogger("koji")
    # if KojiDebug is set, force main log level to DEBUG
    if opts.get('KojiDebug'):
        logger.setLevel(logging.DEBUG)
    elif default is None:
        #LogLevel did not configure a default level
        logger.setLevel(logging.WARNING)
    #log_handler defined in setup_logging1
    log_handler.setFormatter(HubFormatter(opts['LogFormat']))


def load_scripts(environ):
    """Update path and import our scripts files"""
    global kojihub
    scriptsdir = os.path.dirname(environ['SCRIPT_FILENAME'])
    sys.path.insert(0, scriptsdir)
    import kojihub


#
# mod_python handler
#

def handler(req):
    wrapper = WSGIWrapper(req)
    return wrapper.run(application)


def get_memory_usage():
    pagesize = resource.getpagesize()
    statm = [pagesize*int(y)/1024 for y in "".join(open("/proc/self/statm").readlines()).strip().split()]
    size, res, shr, text, lib, data, dirty = statm
    return res - shr

def server_setup(environ):
    global opts, plugins, registry, policy
    logger = logging.getLogger('koji')
    try:
        setup_logging1()
        opts = load_config(environ)
        setup_logging2(opts)
        load_scripts(environ)
        koji.util.setup_rlimits(opts)
        plugins = load_plugins(opts)
        registry = get_registry(opts, plugins)
        policy = get_policy(opts, plugins)
        koji.db.provideDBopts(database = opts["DBName"],
                              user = opts["DBUser"],
                              password = opts.get("DBPass",None),
                              host = opts.get("DBHost", None))
    except Exception:
        tb_str = ''.join(traceback.format_exception(*sys.exc_info()))
        logger.error(tb_str)
        opts = {
            'ServerOffline': True,
            'OfflineMessage': 'server startup error',
            }


#
# wsgi handler
#

firstcall = True

def application(environ, start_response):
    global firstcall
    if firstcall:
        server_setup(environ)
        firstcall = False
    # XMLRPC uses POST only. Reject anything else
    if environ['REQUEST_METHOD'] != 'POST':
        headers = [
            ('Allow', 'POST'),
        ]
        start_response('405 Method Not Allowed', headers)
        response = "Method Not Allowed\nThis is an XML-RPC server. Only POST requests are accepted."
        headers = [
            ('Content-Length', str(len(response))),
            ('Content-Type', "text/plain"),
        ]
        return [response]
    if opts.get('ServerOffline'):
        return offline_reply(start_response, msg=opts.get("OfflineMessage", None))
    # XXX check request length
    # XXX most of this should be moved elsewhere
    if 1:
        try:
            start = time.time()
            memory_usage_at_start = get_memory_usage()

            context._threadclear()
            context.commit_pending = False
            context.opts = opts
            context.handlers = HandlerAccess(registry)
            context.environ = environ
            context.policy = policy
            try:
                context.cnx = koji.db.connect()
            except Exception:
                return offline_reply(start_response, msg="database outage")
            h = ModXMLRPCRequestHandler(registry)
            if environ['CONTENT_TYPE'] == 'application/octet-stream':
                response = h._wrap_handler(h.handle_upload, environ)
            else:
                response = h._wrap_handler(h.handle_rpc, environ)
            headers = [
                ('Content-Length', str(len(response))),
                ('Content-Type', "text/xml"),
            ]
            start_response('200 OK', headers)
            if h.traceback:
                #rollback
                context.cnx.rollback()
            elif context.commit_pending:
                context.cnx.commit()
            memory_usage_at_end = get_memory_usage()
            if memory_usage_at_end - memory_usage_at_start > opts['MemoryWarnThreshold']:
                paramstr = repr(getattr(context, 'params', 'UNKNOWN'))
                if len(paramstr) > 120:
                    paramstr = paramstr[:117] + "..."
                h.logger.warning("Memory usage of process %d grew from %d KiB to %d KiB (+%d KiB) processing request %s with args %s" % (os.getpid(), memory_usage_at_start, memory_usage_at_end, memory_usage_at_end - memory_usage_at_start, context.method, paramstr))
            h.logger.debug("Returning %d bytes after %f seconds", len(response),
                        time.time() - start)
        finally:
            #make sure context gets cleaned up
            if hasattr(context,'cnx'):
                try:
                    context.cnx.close()
                except Exception:
                    pass
            context._threadclear()
        return [response] #XXX


def get_registry(opts, plugins):
    # Create and populate handler registry
    registry = HandlerRegistry()
    functions = kojihub.RootExports()
    hostFunctions = kojihub.HostExports()
    registry.register_instance(functions)
    registry.register_module(hostFunctions,"host")
    registry.register_function(koji.auth.login)
    registry.register_function(koji.auth.krbLogin)
    registry.register_function(koji.auth.sslLogin)
    registry.register_function(koji.auth.logout)
    registry.register_function(koji.auth.subsession)
    registry.register_function(koji.auth.logoutChild)
    registry.register_function(koji.auth.exclusiveSession)
    registry.register_function(koji.auth.sharedSession)
    for name in opts.get('Plugins', '').split():
        registry.register_plugin(plugins.get(name))
    return registry
