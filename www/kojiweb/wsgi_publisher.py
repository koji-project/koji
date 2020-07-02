# a vaguely publisher-like dispatcher for wsgi
#
# Copyright (c) 2012-2014 Red Hat, Inc.
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

import cgi
import inspect
import logging
import os.path
import pprint
import sys
import traceback

import koji
import koji.util
from koji.server import ServerError, ServerRedirect
from koji.util import dslice, to_list


class URLNotFound(ServerError):
    """Used to generate a 404 response"""


class Dispatcher(object):

    def __init__(self):
        # we can't do much setup until we get a request
        self.firstcall = True
        self.options = {}
        self.startup_error = None
        self.handler_index = {}
        self.setup_logging1()

    def setup_logging1(self):
        """Set up basic logging, before options are loaded"""
        logger = logging.getLogger("koji")
        logger.setLevel(logging.WARNING)
        self.log_handler = logging.StreamHandler()
        # Log to stderr (StreamHandler default).
        # There seems to be no advantage to using wsgi.errors
        log_format = '%(msecs)d [%(levelname)s] SETUP p=%(process)s %(name)s: %(message)s'
        self.log_handler.setFormatter(logging.Formatter(log_format))
        self.log_handler.setLevel(logging.DEBUG)
        logger.addHandler(self.log_handler)
        self.formatter = None
        self.logger = logging.getLogger("koji.web")

    cfgmap = [
        # option, type, default
        ['SiteName', 'string', None],
        ['KojiHubURL', 'string', 'http://localhost/kojihub'],
        ['KojiFilesURL', 'string', 'http://localhost/kojifiles'],
        ['KojiTheme', 'string', None],
        ['KojiGreeting', 'string', 'Welcome to Koji Web'],
        ['LiteralFooter', 'boolean', True],

        ['WebPrincipal', 'string', None],
        ['WebKeytab', 'string', '/etc/httpd.keytab'],
        ['WebCCache', 'string', '/var/tmp/kojiweb.ccache'],
        ['KrbService', 'string', 'host'],
        ['KrbRDNS', 'boolean', True],
        ['KrbCanonHost', 'boolean', False],
        ['KrbServerRealm', 'string', None],

        ['WebCert', 'string', None],
        ['KojiHubCA', 'string', '/etc/kojiweb/kojihubca.crt'],

        ['PythonDebug', 'boolean', False],

        ['LoginTimeout', 'integer', 72],

        ['Secret', 'string', None],

        ['LoginDisabled', 'boolean', False],

        ['LibPath', 'string', '/usr/share/koji-web/lib'],

        ['LogLevel', 'string', 'WARNING'],
        ['LogFormat', 'string',
         '%(msecs)d [%(levelname)s] m=%(method)s u=%(user_name)s p=%(process)s r=%(remoteaddr)s '
         '%(name)s: %(message)s'],

        ['Tasks', 'list', []],
        ['ToplevelTasks', 'list', []],
        ['ParentTasks', 'list', []],

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
    ]

    def load_config(self, environ):
        """Load configuration options

        Options are read from a kojiweb config file. To override the
        configuration file location, use the SetEnv Apache directive. For
        example:

          SetEnv koji.web.ConfigFile /home/developer/koji/www/conf/web.conf

        Backwards compatibility:
            - if ConfigFile is not set, opts are loaded from http config
            - if ConfigFile is set, then the http config must not provide Koji options
            - In a future version we will load the default hub config regardless
            - all PythonOptions (except koji.web.ConfigFile) are now deprecated and
              support for them will disappear in a future version of Koji
        """
        cf = environ.get('koji.web.ConfigFile', '/etc/kojiweb/web.conf')
        cfdir = environ.get('koji.web.ConfigDir', '/etc/kojiweb/web.conf.d')
        config = koji.read_config_files([cfdir, (cf, True)])

        opts = {}
        for name, dtype, default in self.cfgmap:
            key = ('web', name)
            if config.has_option(*key):
                if dtype == 'integer':
                    opts[name] = config.getint(*key)
                elif dtype == 'boolean':
                    opts[name] = config.getboolean(*key)
                elif dtype == 'list':
                    opts[name] = [x.strip() for x in config.get(*key).split(',')]
                else:
                    opts[name] = config.get(*key)
            else:
                opts[name] = default
        opts['Secret'] = koji.util.HiddenValue(opts['Secret'])
        self.options = opts
        return opts

    def setup_logging2(self, environ):
        """Adjust logging based on configuration options"""
        opts = self.options
        # determine log level
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
                raise koji.GenericError("Invalid log level: %s" % level)
            # all our loggers start with koji
            if name == '':
                name = 'koji'
                default = level
            elif name.startswith('.'):
                name = 'koji' + name
            elif not name.startswith('koji'):
                name = 'koji.' + name
            level_code = logging.getLevelName(level)
            logging.getLogger(name).setLevel(level_code)
        logger = logging.getLogger("koji")
        # if KojiDebug is set, force main log level to DEBUG
        if opts.get('KojiDebug'):
            logger.setLevel(logging.DEBUG)
        elif default is None:
            # LogLevel did not configure a default level
            logger.setLevel(logging.WARNING)
        self.formatter = HubFormatter(opts['LogFormat'])
        self.formatter.environ = environ
        self.log_handler.setFormatter(self.formatter)

    def find_handlers(self):
        for name in vars(kojiweb_handlers):
            if name.startswith('_'):
                continue
            try:
                val = getattr(kojiweb_handlers, name, None)
                if not inspect.isfunction(val):
                    continue
                # err on the side of paranoia
                args = inspect.getargspec(val)
                if not args[0] or args[0][0] != 'environ':
                    continue
            except Exception:
                tb_str = ''.join(traceback.format_exception(*sys.exc_info()))
                self.logger.error(tb_str)
            self.handler_index[name] = val

    def prep_handler(self, environ):
        path_info = environ['PATH_INFO']
        if not path_info:
            # empty path info (no trailing slash) breaks our relative urls
            environ['koji.redirect'] = environ['REQUEST_URI'] + '/'
            raise ServerRedirect
        elif path_info == '/':
            method = 'index'
        else:
            method = path_info.lstrip('/').split('/')[0]
        environ['koji.method'] = method
        self.logger.info("Method: %s", method)
        func = self.handler_index.get(method)
        if not func:
            raise URLNotFound
        # parse form args
        data = {}
        fs = cgi.FieldStorage(fp=environ['wsgi.input'],
                              environ=environ.copy(),
                              keep_blank_values=True)
        for field in fs.list:
            if field.filename:
                val = field
            else:
                val = field.value
            data.setdefault(field.name, []).append(val)
        # replace singleton lists with single values
        # XXX - this is a bad practice, but for now we strive to emulate mod_python.publisher
        for arg in data:
            val = data[arg]
            if isinstance(val, list) and len(val) == 1:
                data[arg] = val[0]
        environ['koji.form'] = fs
        args, varargs, varkw, defaults = inspect.getargspec(func)
        if not varkw:
            # remove any unexpected args
            data = dslice(data, args, strict=False)
            # TODO (warning in header or something?)
        return func, data

    def _setup(self, environ):
        global kojiweb_handlers
        global kojiweb
        options = self.load_config(environ)
        if 'LibPath' in options and os.path.exists(options['LibPath']):
            sys.path.insert(0, options['LibPath'])
        # figure out our location and try to load index.py from same dir
        scriptsdir = os.path.dirname(environ['SCRIPT_FILENAME'])
        environ['koji.scriptsdir'] = scriptsdir
        sys.path.insert(0, scriptsdir)
        import index as kojiweb_handlers
        import kojiweb
        self.find_handlers()
        self.setup_logging2(environ)
        koji.util.setup_rlimits(options)
        # TODO - plugins?

    def setup(self, environ):
        try:
            self._setup(environ)
        except Exception:
            self.startup_error = "unknown startup_error"
            etype, e = sys.exc_info()[:2]
            tb_short = ''.join(traceback.format_exception_only(etype, e))
            self.startup_error = "startup_error: %s" % tb_short
            tb_str = ''.join(traceback.format_exception(*sys.exc_info()))
            self.logger.error(tb_str)

    def simple_error_page(self, message=None, err=None):
        result = ["""\
<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN"
"http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd">
<html><head><title>Error</title></head>
<body>
"""]
        if message:
            result.append("<p>%s</p>\n" % message)
        if err:
            result.append("<p>%s</p>\n" % err)
        result.append("</body></html>\n")
        result = [x.encode('utf-8') for x in result]
        length = sum([len(x) for x in result])
        headers = [
            ('Allow', 'GET, POST, HEAD'),
            ('Content-Length', str(length)),
            ('Content-Type', 'text/html'),
        ]
        return result, headers

    def error_page(self, environ, message=None, err=True):
        if err:
            etype, e = sys.exc_info()[:2]
            tb_short = ''.join(traceback.format_exception_only(etype, e))
            tb_long = ''.join(traceback.format_exception(*sys.exc_info()))
            if isinstance(e, koji.ServerOffline):
                desc = ('Outage', 'outage')
            else:
                desc = ('Error', 'error')
        else:
            etype = None
            e = None
            tb_short = ''
            tb_long = ''
            desc = ('Error', 'error')
        try:
            _initValues = kojiweb.util._initValues
            _genHTML = kojiweb.util._genHTML
        except (NameError, AttributeError):
            tb_str = ''.join(traceback.format_exception(*sys.exc_info()))
            self.logger.error(tb_str)
            # fallback to simple error page
            return self.simple_error_page(message, err=tb_short)
        values = _initValues(environ, *desc)
        values['etype'] = etype
        values['exception'] = e
        if err:
            values['explanation'], values['debug_level'] = kojiweb.util.explainError(e)
            if message:
                values['explanation'] = message
        else:
            values['explanation'] = message or "Unknown error"
            values['debug_level'] = 0
        values['tb_short'] = tb_short
        if int(self.options.get("PythonDebug", 0)):
            values['tb_long'] = tb_long
        else:
            values['tb_long'] = "Full tracebacks disabled"
        # default these koji values to false so the _genHTML doesn't try to look
        # them up (which will fail badly if the hub is offline)
        # FIXME - we need a better fix for this
        environ['koji.values'].setdefault('mavenEnabled', False)
        environ['koji.values'].setdefault('winEnabled', False)
        result = _genHTML(environ, 'error.chtml')
        headers = [
            ('Allow', 'GET, POST, HEAD'),
            ('Content-Length', str(len(result))),
            ('Content-Type', 'text/html'),
        ]
        return self._tobytes(result), headers

    def _tobytes(self, result):
        if isinstance(result, str):
            result = [bytes(result, encoding='utf-8')]
        return result

    def handle_request(self, environ, start_response):
        if self.startup_error:
            status = '200 OK'
            result, headers = self.error_page(environ, message=self.startup_error)
            start_response(status, headers)
            return result
        if environ['REQUEST_METHOD'] not in ['GET', 'POST', 'HEAD']:
            status = '405 Method Not Allowed'
            result, headers = self.error_page(environ, message="Method Not Allowed")
            start_response(status, headers)
            return result
        environ['koji.options'] = self.options
        try:
            environ['koji.headers'] = []
            func, data = self.prep_handler(environ)
            result = func(environ, **data)
            status = '200 OK'
        except ServerRedirect:
            status = '302 Found'
            location = environ['koji.redirect']
            result = '<p>Redirect: <a href="%s">here</a></p>\n' % location
            environ['koji.headers'].append(['Location', location])
        except URLNotFound:
            status = "404 Not Found"
            msg = "Not found: %s" % environ['REQUEST_URI']
            result, headers = self.error_page(environ, message=msg, err=False)
            start_response(status, headers)
            return result
        except Exception:
            tb_str = ''.join(traceback.format_exception(*sys.exc_info()))
            self.logger.error(tb_str)
            status = '500 Internal Server Error'
            result, headers = self.error_page(environ)
            start_response(status, headers)
            return result
        headers = {
            'allow': ('Allow', 'GET, POST, HEAD'),
        }
        extra = []
        for name, value in environ.get('koji.headers', []):
            key = name.lower()
            if key == 'set-cookie':
                extra.append((name, value))
            else:
                # last one wins
                headers[key] = (name, value)
        if isinstance(result, str):
            headers.setdefault('content-length', ('Content-Length', str(len(result))))
        headers.setdefault('content-type', ('Content-Type', 'text/html'))
        headers = to_list(headers.values()) + extra
        self.logger.debug("Headers:")
        self.logger.debug(koji.util.LazyString(pprint.pformat, [headers]))
        start_response(status, headers)
        return self._tobytes(result)

    def application(self, environ, start_response):
        """wsgi handler"""
        if self.formatter:
            self.formatter.environ = environ
        if self.firstcall:
            self.firstcall = False
            self.setup(environ)
        try:
            result = self.handle_request(environ, start_response)
        finally:
            if self.formatter:
                self.formatter.environ = {}
            session = environ.get('koji.session')
            if session:
                session.logout()
        return result


class HubFormatter(logging.Formatter):
    """Support some koji specific fields in the format string"""

    def format(self, record):
        # dispatcher should set environ for us
        environ = self.environ
        # XXX Can we avoid these data lookups if not needed?
        record.method = environ.get('koji.method')
        record.remoteaddr = "%s:%s" % (
            environ.get('REMOTE_ADDR', '?'),
            environ.get('REMOTE_PORT', '?'))
        record.user_name = environ.get('koji.currentLogin')
        user = environ.get('koji.currentUser')
        if user:
            record.user_id = user['id']
        else:
            record.user_id = None
        session = environ.get('koji.session')
        record.session_id = None
        if session:
            record.callnum = session.callnum
            if session.sinfo:
                record.session_id = session.sinfo.get('session.id')
        else:
            record.callnum = None
        return logging.Formatter.format(self, record)


# provide necessary global handlers for mod_wsgi
dispatcher = Dispatcher()
application = dispatcher.application
