# mod_python script

# kojixmlrpc - an XMLRPC interface for koji.
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
import time
import traceback
import pprint
from xmlrpclib import loads,dumps,Fault
from mod_python import apache

import koji
import koji.auth
import koji.db
from kojihub import RootExports
from kojihub import HostExports
from koji.context import context

def _opt_bool(opts, name):
    """Convert a string option into a boolean
    True or False value.  The following values
    will be considered True (case-insensitive):
    yes, on, true, 1
    Anything else will be considered False."""
    val = opts.get(name, 'no')
    if val is None:
        val = ''
    if val.lower() in ('yes', 'on', 'true', '1'):
        return True
    else:
        return False

class ModXMLRPCRequestHandler(object):
    """Simple XML-RPC handler for mod_python environment"""

    def __init__(self):
        self.funcs = {}
        self.traceback = False
        #introspection functions
        self.register_function(self.list_api, name="_listapi")
        self.register_function(self.system_listMethods, name="system.listMethods")
        self.register_function(self.system_methodSignature, name="system.methodSignature")
        self.register_function(self.system_methodHelp, name="system.methodHelp")
        self.register_function(self.multiCall)
        # Also register it as system.multicall for standards compliance
        self.register_function(self.multiCall, name="system.multicall")

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

    def _marshaled_dispatch(self, data):
        """Dispatches an XML-RPC method from marshalled (XML) data."""

        params, method = loads(data)

        start = time.time()
        # generate response
        try:
            response = self._dispatch(method, params)
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
                if _opt_bool(context.opts, 'KojiDebug'):
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
            sys.stderr.write(tb_str)
            sys.stderr.write('\n')
            response = dumps(Fault(faultCode, faultString))

        if _opt_bool(context.opts, 'KojiDebug'):
            sys.stderr.write("Returning %d bytes after %f seconds\n" %
                             (len(response),time.time() - start))
            sys.stderr.flush()
        
        return response

    def _dispatch(self,method,params):
        func = self.funcs.get(method,None)
        if func is None:
            raise koji.GenericError, "Invalid method: %s" % method
        context.method = method
        if not hasattr(context,"session"):
            #we may be called again by one of our meta-calls (like multiCall)
            #so we should only create a session if one does not already exist
            context.session = koji.auth.Session()
            try:
                context.session.validate()
            except koji.AuthLockError:
                #might be ok, depending on method
                if method not in ('exclusiveSession','login', 'krbLogin', 'logout'):
                    raise
            if _opt_bool(context.opts, 'LockOut') and \
                   method not in ('login', 'krbLogin', 'sslLogin', 'logout'):
                if not context.session.hasPerm('admin'):
                    raise koji.GenericError, "Server disabled for maintenance"
        # handle named parameters
        params,opts = koji.decode_args(*params)

        if _opt_bool(context.opts, 'KojiDebug'):
            sys.stderr.write("Handling method %s for session %s (#%s)\n" \
                             % (method, context.session.id, context.session.callnum))
            if method != 'uploadFile':
                sys.stderr.write("Params: %s\n" % pprint.pformat(params))
                sys.stderr.write("Opts: %s\n" % pprint.pformat(opts))
            start = time.time()
            
        ret = func(*params,**opts)

        if _opt_bool(context.opts, 'KojiDebug'):
            sys.stderr.write("Completed method %s for session %s (#%s): %f seconds\n"
                             % (method, context.session.id, context.session.callnum,
                                time.time()-start))
            sys.stderr.flush()
        
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

    def list_api(self):
        funcs = []
        for name,func in self.funcs.items():
            #the keys in self.funcs determine the name of the method as seen over xmlrpc
            #func.__name__ might differ (e.g. for dotted method names)
            args = self._getFuncArgs(func)
            funcs.append({'name': name,
                          'doc': func.__doc__,
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
        arglist = []
        for arg in self._getFuncArgs(func):
            if isinstance(arg,str):
                arglist.append(arg)
            else:
                arglist.append('%s=%s' % (arg[0], arg[1]))
        ret = '%s(%s)' % (method, ", ".join(arglist))
        if func.__doc__:
            ret += "\ndescription: %s" % func.__doc__
        return ret

    def handle_request(self,req):
        """Handle a single XML-RPC request"""

        # XMLRPC uses POST only. Reject anything else
        if req.method != 'POST':
            req.allow_methods(['POST'],1)
            raise apache.SERVER_RETURN, apache.HTTP_METHOD_NOT_ALLOWED

        response = self._marshaled_dispatch(req.read())

        req.content_type = "text/xml"
        req.set_content_length(len(response))
        req.write(response)


def offline_reply(req, msg=None):
    """Send a ServerOffline reply"""
    faultCode = koji.ServerOffline.faultCode
    if msg is None:
        faultString = "server is offline"
    else:
        faultString = msg
    response = dumps(Fault(faultCode, faultString))
    req.content_type = "text/xml"
    req.set_content_length(len(response))
    req.write(response)

#
# mod_python handler
#

def handler(req, profiling=False):
    if profiling:
        import profile, pstats, StringIO, tempfile
        global _profiling_req
        _profiling_req = req
        temp = tempfile.NamedTemporaryFile()
        profile.run("import kojixmlrpc; kojixmlrpc.handler(kojixmlrpc._profiling_req, False)", temp.name)
        stats = pstats.Stats(temp.name)
        strstream = StringIO.StringIO()
        sys.stdout = strstream
        stats.sort_stats("time")
        stats.print_stats()
        req.write("<pre>" + strstream.getvalue() + "</pre>")
        _profiling_req = None
    else:
        opts = req.get_options()
        try:
            if _opt_bool(opts, 'ServerOffline'):
                offline_reply(req, msg=opts.get("OfflineMessage", None))
                return apache.OK
            context._threadclear()
            context.commit_pending = False
            context.opts = opts
            context.req = req
            koji.db.provideDBopts(database = opts["DBName"],
                                  user = opts["DBUser"],
                                  host = opts.get("DBhost",None))
            try:
                context.cnx = koji.db.connect(_opt_bool(opts, 'KojiDebug'))
            except Exception:
                offline_reply(req, msg="database outage")
                return apache.OK
            functions = RootExports()
            hostFunctions = HostExports()
            h = ModXMLRPCRequestHandler()
            h.register_instance(functions)
            h.register_module(hostFunctions,"host")
            h.register_function(koji.auth.login)
            h.register_function(koji.auth.krbLogin)
            h.register_function(koji.auth.sslLogin)
            h.register_function(koji.auth.logout)
            h.register_function(koji.auth.subsession)
            h.register_function(koji.auth.logoutChild)
            h.register_function(koji.auth.exclusiveSession)
            h.register_function(koji.auth.sharedSession)
            h.handle_request(req)
            if h.traceback:
                #rollback
                context.cnx.rollback()
            elif context.commit_pending:
                context.cnx.commit()
        finally:
            #make sure context gets cleaned up
            if hasattr(context,'cnx'):
                context.cnx.close()
            context._threadclear()
    return apache.OK
