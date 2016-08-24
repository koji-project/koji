# utility functions for koji web interface
#
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
#       Mike Bonnet <mikeb@redhat.com>
#       Mike McLean <mikem@redhat.com>

import Cheetah.Template
import datetime
import koji
from koji.util import md5_constructor
import os
import stat
#a bunch of exception classes that explainError needs
from socket import error as socket_error
from socket import sslerror as socket_sslerror
from xmlrpclib import ProtocolError
from xml.parsers.expat import ExpatError
import cgi

try:
    # pyOpenSSL might not be around
    from OpenSSL.SSL import Error as SSL_Error
except:
    SSL_Error = NoSuchException


themeInfo = {}
themeCache = {}

def _initValues(environ, title='Build System Info', pageID='summary'):
    global themeInfo
    global themeCache
    values = {}
    values['siteName'] = environ['koji.options'].get('SiteName', 'Koji')
    values['title'] = title
    values['pageID'] = pageID
    values['currentDate'] = str(datetime.datetime.now())
    values['literalFooter'] = environ['koji.options'].get('LiteralFooter', True)
    themeCache.clear()
    themeInfo.clear()
    themeInfo['name'] = environ['koji.options'].get('KojiTheme', None)
    themeInfo['staticdir'] = environ['koji.options'].get('KojiStaticDir', '/usr/share/koji-web/static')

    environ['koji.values'] = values

    return values

def themePath(path, local=False):
    global themeInfo
    global themeCache
    local = bool(local)
    if (path, local) in themeCache:
        return themeCache[path, local]
    if not themeInfo['name']:
        if local:
            ret = os.path.join(themeInfo['staticdir'], path)
        else:
            ret = "/koji-static/%s" % path
    else:
        themepath = os.path.join(themeInfo['staticdir'], 'themes', themeInfo['name'], path)
        if os.path.exists(themepath):
            if local:
                ret = themepath
            else:
                ret = "/koji-static/themes/%s/%s" % (themeInfo['name'], path)
        else:
            if local:
                ret = os.path.join(themeInfo['staticdir'], path)
            else:
                ret = "/koji-static/%s" % path
    themeCache[path, local] = ret
    return ret

class DecodeUTF8(Cheetah.Filters.Filter):
    def filter(self, *args, **kw):
        """Convert all strs to unicode objects"""
        result = super(DecodeUTF8, self).filter(*args, **kw)
        if isinstance(result, unicode):
            pass
        else:
            result = result.decode('utf-8', 'replace')
        return result

# Escape ampersands so the output can be valid XHTML
class XHTMLFilter(DecodeUTF8):
    def filter(self, *args, **kw):
        result = super(XHTMLFilter, self).filter(*args, **kw)
        result = result.replace('&', '&amp;')
        result = result.replace('&amp;amp;', '&amp;')
        result = result.replace('&amp;nbsp;', '&nbsp;')
        result = result.replace('&amp;lt;', '&lt;')
        result = result.replace('&amp;gt;', '&gt;')
        return result

TEMPLATES = {}

def _genHTML(environ, fileName):
    reqdir = os.path.dirname(environ['SCRIPT_FILENAME'])
    if os.getcwd() != reqdir:
        os.chdir(reqdir)

    if 'koji.currentUser' in environ:
        environ['koji.values']['currentUser'] = environ['koji.currentUser']
    else:
        environ['koji.values']['currentUser'] = None
    environ['koji.values']['authToken'] = _genToken(environ)
    if not environ['koji.values'].has_key('mavenEnabled'):
        if 'koji.session' in environ:
            environ['koji.values']['mavenEnabled'] = environ['koji.session'].mavenEnabled()
        else:
            environ['koji.values']['mavenEnabled'] = False
    if not environ['koji.values'].has_key('winEnabled'):
        if 'koji.session' in environ:
            environ['koji.values']['winEnabled'] = environ['koji.session'].winEnabled()
        else:
            environ['koji.values']['winEnabled'] = False
    if not environ['koji.values'].has_key('LoginDisabled'):
        if 'koji.options' in environ:
            environ['koji.values']['LoginDisabled'] = environ['koji.options']['LoginDisabled']
        else:
            environ['koji.values']['LoginDisabled'] = False

    tmpl_class = TEMPLATES.get(fileName)
    if not tmpl_class:
        tmpl_class = Cheetah.Template.Template.compile(file=fileName)
        TEMPLATES[fileName] = tmpl_class
    tmpl_inst = tmpl_class(namespaces=[environ['koji.values']], filter=XHTMLFilter)
    return tmpl_inst.respond().encode('utf-8', 'replace')

def _truncTime():
    now = datetime.datetime.now()
    # truncate to the nearest 15 minutes
    return now.replace(minute=(now.minute / 15 * 15), second=0, microsecond=0)

def _genToken(environ, tstamp=None):
    if 'koji.currentLogin' in environ and environ['koji.currentLogin']:
        user = environ['koji.currentLogin']
    else:
        return ''
    if tstamp == None:
        tstamp = _truncTime()
    return md5_constructor(user + str(tstamp) + environ['koji.options']['Secret'].value).hexdigest()[-8:]

def _getValidTokens(environ):
    tokens = []
    now = _truncTime()
    for delta in (0, 15, 30):
        token_time = now - datetime.timedelta(minutes=delta)
        token = _genToken(environ, token_time)
        if token:
            tokens.append(token)
    return tokens

def toggleOrder(template, sortKey, orderVar='order'):
    """
    If orderVar equals 'sortKey', return '-sortKey', else
    return 'sortKey'.
    """
    if template.getVar(orderVar) == sortKey:
        return '-' + sortKey
    else:
        return sortKey

def toggleSelected(template, var, option):
    """
    If the passed in variable var equals the literal value in option,
    return 'selected="selected"', otherwise return ''.
    Used for setting the selected option in select boxes.
    """
    if var == option:
        return 'selected="selected"'
    else:
        return ''

def sortImage(template, sortKey, orderVar='order'):
    """
    Return an html img tag suitable for inclusion in the sortKey of a sortable table,
    if the sortValue is "sortKey" or "-sortKey".
    """
    orderVal = template.getVar(orderVar)
    if orderVal == sortKey:
        return '<img src="%s" class="sort" alt="ascending sort"/>' % themePath("images/gray-triangle-up.gif")
    elif orderVal == '-' + sortKey:
        return '<img src="%s" class="sort" alt="descending sort"/>' % themePath("images/gray-triangle-down.gif")
    else:
        return ''

def passthrough(template, *vars):
    """
    Construct a string suitable for use as URL
    parameters.  For each variable name in *vars,
    if the template has a corresponding non-None value,
    append that name-value pair to the string.  The name-value
    pairs will be separated by ampersands (&), and prefixed by
    an ampersand if there are any name-value pairs.  If there
    are no name-value pairs, an empty string will be returned.
    """
    result = []
    for var in vars:
        value = template.getVar(var, default=None)
        if value != None:
            result.append('%s=%s' % (var, value))
    if result:
        return '&' + '&'.join(result)
    else:
        return ''

def passthrough_except(template, *exclude):
    """
    Construct a string suitable for use as URL
    parameters.  The template calling this method must have
    previously used
    #attr _PASSTHROUGH = ...
    to define the list of variable names to be passed-through.
    Any variables names passed in will be excluded from the
    list of variables in the output string.
    """
    passvars = []
    for var in template._PASSTHROUGH:
        if not var in exclude:
            passvars.append(var)
    return passthrough(template, *passvars)

def sortByKeyFunc(key, noneGreatest=False):
    """Return a function to sort a list of maps by the given key.
    If the key starts with '-', sort in reverse order.  If noneGreatest
    is True, None will sort higher than all other values (instead of lower).
    """
    if noneGreatest:
        # Normally None evaluates to be less than every other value
        # Invert the comparison so it always evaluates to greater
        cmpFunc = lambda a, b: (a is None or b is None) and -(cmp(a, b)) or cmp(a, b)
    else:
        cmpFunc = cmp

    if key.startswith('-'):
        key = key[1:]
        sortFunc = lambda a, b: cmpFunc(b[key], a[key])
    else:
        sortFunc = lambda a, b: cmpFunc(a[key], b[key])

    return sortFunc

def paginateList(values, data, start, dataName, prefix=None, order=None, noneGreatest=False, pageSize=50):
    """
    Slice the 'data' list into one page worth.  Start at offset
    'start' and limit the total number of pages to pageSize
    (defaults to 50).  'dataName' is the name under which the
    list will be added to the value map, and prefix is the name
    under which a number of list-related metadata variables will
    be added to the value map.
    """
    if order != None:
        data.sort(sortByKeyFunc(order, noneGreatest))

    totalRows = len(data)

    if start:
        start = int(start)
    if not start or start < 0:
        start = 0

    data = data[start:(start + pageSize)]
    count = len(data)

    _populateValues(values, dataName, prefix, data, totalRows, start, count, pageSize, order)

    return data

def paginateMethod(server, values, methodName, args=None, kw=None,
                   start=None, dataName=None, prefix=None, order=None, pageSize=50):
    """Paginate the results of the method with the given name when called with the given args and kws.
    The method must support the queryOpts keyword parameter, and pagination is done in the database."""
    if args is None:
        args = []
    if kw is None:
        kw = {}
    if start:
        start = int(start)
    if not start or start < 0:
        start = 0
    if not dataName:
        raise StandardError, 'dataName must be specified'

    kw['queryOpts'] = {'countOnly': True}
    totalRows = getattr(server, methodName)(*args, **kw)

    kw['queryOpts'] = {'order': order,
                       'offset': start,
                       'limit': pageSize}
    data = getattr(server, methodName)(*args, **kw)
    count = len(data)

    _populateValues(values, dataName, prefix, data, totalRows, start, count, pageSize, order)

    return data

def paginateResults(server, values, methodName, args=None, kw=None,
                    start=None, dataName=None, prefix=None, order=None, pageSize=50):
    """Paginate the results of the method with the given name when called with the given args and kws.
    This method should only be used when then method does not support the queryOpts command (because
    the logic used to generate the result list prevents filtering/ordering from being done in the database).
    The method must return a list of maps."""
    if args is None:
        args = []
    if kw is None:
        kw = {}
    if start:
        start = int(start)
    if not start or start < 0:
        start = 0
    if not dataName:
        raise StandardError, 'dataName must be specified'

    totalRows = server.count(methodName, *args, **kw)

    kw['filterOpts'] = {'order': order,
                        'offset': start,
                        'limit': pageSize}
    data = server.filterResults(methodName, *args, **kw)
    count = len(data)

    _populateValues(values, dataName, prefix, data, totalRows, start, count, pageSize, order)

    return data

def _populateValues(values, dataName, prefix, data, totalRows, start, count, pageSize, order):
    """Populate the values list with the data about the list provided."""
    values[dataName] = data
    # Don't use capitalize() to title() here, they mess up
    # mixed-case name
    values['total' + dataName[0].upper() + dataName[1:]] = totalRows
    # Possibly prepend a prefix to the numeric parameters, to avoid namespace collisions
    # when there is more than one list on the same page
    values[(prefix and prefix + 'Start' or 'start')] = start
    values[(prefix and prefix + 'Count' or 'count')] = count
    values[(prefix and prefix + 'Range' or 'range')] = pageSize
    values[(prefix and prefix + 'Order' or 'order')] = order
    currentPage = start / pageSize
    values[(prefix and prefix + 'CurrentPage' or 'currentPage')] = currentPage
    totalPages = totalRows / pageSize
    if totalRows % pageSize > 0:
        totalPages += 1
    pages = [page for page in range(0, totalPages) if (abs(page - currentPage) < 100 or ((page + 1) % 100 == 0))]
    values[(prefix and prefix + 'Pages') or 'pages'] = pages

def stateName(stateID):
    """Convert a numeric build state into a readable name."""
    return koji.BUILD_STATES[stateID].lower()

def imageTag(name):
    """Return an img tag that loads an icon with the given name"""
    return '<img class="stateimg" src="%s" title="%s" alt="%s"/>' \
           % (themePath("images/%s.png" % name), name, name)

def stateImage(stateID):
    """Return an IMG tag that loads an icon appropriate for
    the given state"""
    name = stateName(stateID)
    return imageTag(name)

def brStateName(stateID):
    """Convert a numeric buildroot state into a readable name."""
    return koji.BR_STATES[stateID].lower()


def brLabel(brinfo):
    if brinfo['br_type'] == koji.BR_TYPES['STANDARD']:
        return '%(tag_name)s-%(id)i-%(repo_id)i' % brinfo
    else:
        return '%(cg_name)s:%(id)i' % brinfo


def repoStateName(stateID):
    """Convert a numeric repository state into a readable name."""
    if stateID == koji.REPO_INIT:
        return 'initializing'
    elif stateID == koji.REPO_READY:
        return 'ready'
    elif stateID == koji.REPO_EXPIRED:
        return 'expired'
    elif stateID == koji.REPO_DELETED:
        return 'deleted'
    else:
        return 'unknown'

def taskState(stateID):
    """Convert a numeric task state into a readable name"""
    return koji.TASK_STATES[stateID].lower()

formatTime = koji.formatTime
formatTimeRSS = koji.formatTimeLong
formatTimeLong = koji.formatTimeLong

def formatDep(name, version, flags):
    """Format dependency information into
    a human-readable format.  Copied from
    rpmUtils/miscutils.py:formatRequires()"""
    s = name

    if flags:
        if flags & (koji.RPMSENSE_LESS | koji.RPMSENSE_GREATER |
                    koji.RPMSENSE_EQUAL):
            s = s + " "
            if flags & koji.RPMSENSE_LESS:
                s = s + "<"
            if flags & koji.RPMSENSE_GREATER:
                s = s + ">"
            if flags & koji.RPMSENSE_EQUAL:
                s = s + "="
            if version:
                s = "%s %s" %(s, version)
    return s

def formatMode(mode):
    """Format a numeric mode into a ls-like string describing the access mode."""
    if stat.S_ISREG(mode):
        result = '-'
    elif stat.S_ISDIR(mode):
        result = 'd'
    elif stat.S_ISCHR(mode):
        result = 'c'
    elif stat.S_ISBLK(mode):
        result = 'b'
    elif stat.S_ISFIFO(mode):
        result = 'p'
    elif stat.S_ISLNK(mode):
        result = 'l'
    elif stat.S_ISSOCK(mode):
        result = 's'
    else:
        # What is it?  Show it like a regular file.
        result = '-'

    for x in ('USR', 'GRP', 'OTH'):
        for y in ('R', 'W', 'X'):
            if mode & getattr(stat, 'S_I' + y + x):
                result += y.lower()
            else:
                result += '-'

    return result

def rowToggle(template):
    """If the value of template._rowNum is even, return 'row-even';
    if it is odd, return 'row-odd'.  Increment the value before checking it.
    If the template does not have that value, set it to 0."""
    if not hasattr(template, '_rowNum'):
        template._rowNum = 0
    template._rowNum += 1
    if template._rowNum % 2:
        return 'row-odd'
    else:
        return 'row-even'


def taskScratchClass(task_object):
    """ Return a css class indicating whether or not this task is a scratch
    build.
    """
    method = task_object['method']
    request = task_object['request']
    if method == 'build' and len(request) >= 3:
        # Each task method has its own signature for what gets put in the
        # request list.  Builds should have an `opts` dict at index 2.
        # See www/kojiweb/taskinfo.chtml for the grimoire.
        opts = request[2]
        if opts.get('scratch'):
            return "scratch"
    return ""


_fileFlags = {1: 'configuration',
              2: 'documentation',
              4: 'icon',
              8: 'missing ok',
              16: "don't replace",
              64: 'ghost',
              128: 'license',
              256: 'readme',
              512: 'exclude',
              1024: 'unpatched',
              2048: 'public key'}

def formatFileFlags(flags):
    """Format rpm fileflags for display.  Returns
    a list of human-readable strings specifying the
    flags set in "flags"."""
    results = []
    for flag, desc in _fileFlags.items():
        if flags & flag:
            results.append(desc)
    return results

def escapeHTML(value):
    """Replace special characters to the text can be displayed in
    an HTML page correctly.
    < : &lt;
    > : &gt;
    & : &amp;
    """
    if not value:
        return value

    value = koji.fixEncoding(value)
    return value.replace('&', '&amp;').\
           replace('<', '&lt;').\
           replace('>', '&gt;')

def authToken(template, first=False, form=False):
    """Return the current authToken if it exists.
    If form is True, return it enclosed in a hidden input field.
    Otherwise, return it in a format suitable for appending to a URL.
    If first is True, prefix it with ?, otherwise prefix it
    with &.  If no authToken exists, return an empty string."""
    token = template.getVar('authToken', default=None)
    if token != None:
        if form:
            return '<input type="hidden" name="a" value="%s"/>' % token
        if first:
            return '?a=' + token
        else:
            return '&a=' + token
    else:
        return ''

def explainError(error):
    """Explain an exception in user-consumable terms

    Some of the explanations are web-centric, which is why this call is not part
    of the main koji library, at least for now...

    Returns a tuple: (str, level)
    str = explanation in plain text
    level = an integer indicating how much traceback data should
            be shown:
                0 - no traceback data
                1 - just the exception
                2 - full traceback
    """
    str = "An exception has occurred"
    level = 2
    if isinstance(error, koji.ServerOffline):
        str = "The server is offline. Please try again later."
        level = 0
    elif isinstance(error, koji.ActionNotAllowed):
        str = """\
The web interface has tried to do something that your account is not \
allowed to do. This is most likely a bug in the web interface."""
    elif isinstance(error, koji.FunctionDeprecated):
        str = """\
The web interface has tried to access a deprecated function. This is \
most likely a bug in the web interface."""
    elif isinstance(error, koji.RetryError):
        str = """\
The web interface is having difficulty communicating with the main \
server and was unable to retry an operation. Most likely this indicates \
a network issue, but it could also be a configuration issue."""
        level = 1
    elif isinstance(error, koji.GenericError):
        if getattr(error, 'fromFault', False):
            str = """\
An error has occurred on the main server. This could be a software \
bug, a server configuration issue, or possibly something else."""
        else:
            str = """\
An error has occurred in the web interface code. This could be due to \
a bug or a configuration issue."""
    elif isinstance(error, (socket_error, socket_sslerror)):
        str = """\
The web interface is having difficulty communicating with the main \
server. This most likely indicates a network issue."""
        level = 1
    elif isinstance(error, (ProtocolError, ExpatError)):
        str = """\
The main server returned an invalid response. This could be caused by \
a network issue or load issues on the server."""
        level = 1
    else:
        str = "An error has occurred while processing your request."
    return str, level


class TaskResultFragment(object):
    """This class permits us to compose HTML fragment by the default
    composer method or self-defined composer function.

    The composer function should have the following prototype:

    composer(TaskResultFragment(), length=None)

    return a string that is an available HTML fragment.
    """
    def __init__(self, text='', size=None, need_escape=None, escaped=None,
                     begin_tag='', end_tag='', composer=None):
        self.text = text
        if size is None:
            self.size = len(text)
        else:
            self.size = size
        self.need_escape = need_escape
        self.escaped = escaped
        self.begin_tag = begin_tag
        self.end_tag = end_tag
        if composer is None:
            self.composer = self.default_composer
        else:
            self.composer = lambda length=None: composer(self, length)

    def default_composer(self, length=None):
        import cgi
        if length is None:
            text = self.text
        else:
            text = self.text[:length]
        if self.need_escape and not self.escaped:
            text = cgi.escape(text)
        if self.size > 0 and text == '':
            text = '...'
        return '%s%s%s' % (self.begin_tag, text, self.end_tag)


class TaskResultLine(object):
    """This class permits us from several TaskResultFragment instances
    to compose an HTML fragment that ends with a line break. You
    can use the default composer method or give a self-defined version.

    The composer function prototype should be

    composer(TaskResultLine(), length=None)

    return a string that is an available HTML fragment.
    """
    def __init__(self, fragments=None, need_escape=None, escaped=True,
                     begin_tag='', end_tag='<br />', composer=None):
        if fragments is None:
            self.fragments = []
        else:
            self.fragments = fragments

        self.need_escape = need_escape
        self.escaped = escaped
        self.begin_tag = begin_tag
        self.end_tag = end_tag
        if composer is None:
            self.composer = self.default_composer
        else:
            self.composer = lambda length=None: composer(self, length)
        self.size=self._size()

    def default_composer(self, length=None):
        import cgi
        line_text = ''
        size = 0
        postfix = self.postfix(length)

        for fragment in self.fragments:
            if length is None:
                line_text += fragment.composer()
            else:
                if size >= length: break
                remainder_size = length - size
                line_text += fragment.composer(remainder_size)
                size += fragment.size

        if self.need_escape and not self.escaped:
            line_text = cgi.escape(line_text)

        return '%s%s%s%s' % (self.begin_tag, line_text, postfix, self.end_tag)

    def _size(self):
        return sum([fragment.size for fragment in self.fragments])

    def postfix(self, length=None):
        if length is None or length >= self.size:
            postfix = ''
        else:
            postfix = ' ... ...'
        return postfix


def _parse_value(key, value, sep=', '):
    _str = None
    begin_tag = ''
    end_tag = ''

    if key in ('brootid', 'buildroot_id'):
        _str = str(value)
        begin_tag = '<a href="buildrootinfo?buildrootID=%s">' % _str
        end_tag = '</a>'
    elif isinstance(value, list):
        _str = sep.join([str(val) for val in value])
    elif isinstance(value, dict):
        _str = sep.join(['%s=%s' % ((n == '' and "''" or n), v) for n, v in value.items()])
    else:
        _str = str(value)
    if _str is None:
        _str = ''

    return TaskResultFragment(text=_str, begin_tag=begin_tag, end_tag=end_tag)

def task_result_to_html_or_string(result=None, exc_class=None,
                                      max_abbr_lines=None, max_abbr_len=None):
    """convert the result to a HTML fragment or a string.

    Returns a tuple: (full_html_or_string, abbreviated_html_or_string)
    """
    default_max_abbr_result_lines = 11
    default_max_abbr_result_len = 512
    if max_abbr_lines is None:
        max_abbr_lines = default_max_abbr_result_lines
    if isinstance(result, dict):
        max_abbr_lines = len(result) + 1
    if max_abbr_len is None:
        max_abbr_len = default_max_abbr_result_len
    full_ret_str = ''
    abbr_ret_str = ''
    lines = []

    def _parse_properties(props):
        return ', '.join([v is not None and '%s=%s' % (n, v) or str(n)
                              for n, v in props.items()])

    if exc_class:
        if hasattr(result, 'faultString'):
            _str = result.faultString.strip()
        else:
            _str = "%s: %s" % (exc_class.__name__, str(result))
        fragment = TaskResultFragment(text=_str)
        line = TaskResultLine(
            fragments=[fragment], need_escape=True,
            escaped=False, begin_tag='<pre>', end_tag='</pre>')
        lines.append(line)
    elif isinstance(result, dict):
        def composer(line, length=None):
            key_fragment = line.fragments[0]
            val_fragment = line.fragments[1]
            if length is None:
                return '%s%s = %s%s' % (line.begin_tag, key_fragment.composer(),
                                            val_fragment.composer(), line.end_tag)
            postfix = line.postfix(length)
            first_part_len = len('%s = ' % key_fragment.composer())
            remainder_len = length - first_part_len
            if remainder_len < 0: remainder_len = 0
            return '%s%s = %s%s%s' % (
                line.begin_tag, key_fragment.composer(),
                val_fragment.composer(remainder_len), postfix, line.end_tag)

        for k, v in result.items():
            if k == 'properties':
                _str = "properties = %s" % _parse_properties(v)
                fragment = TaskResultFragment(text=_str)
                line = TaskResultLine(fragments=[fragment], need_escape=False)
            elif k != '__starstar':
                val_fragment = _parse_value(k, v)
                key_fragment = TaskResultFragment(text=k)
                line = TaskResultLine(fragments=[key_fragment, val_fragment],
                                          need_escape=False, composer=composer)
            lines.append(line)
    else:
        if result is not None:
            fragment = _parse_value('', result)
            line = TaskResultLine(fragments=[fragment])
            lines.append(line)

    if not lines:
        return full_ret_str, abbr_ret_str

    total_lines = len(lines)
    full_result_len = sum([line.size for line in lines])
    total_abbr_lines = 0
    total_abbr_len = 0

    for line in lines:
        line_len = line.size
        full_ret_str += line.composer()

        if total_lines < max_abbr_lines and full_result_len < max_abbr_len:
            continue
        if total_abbr_lines >= max_abbr_lines or total_abbr_len >= max_abbr_len:
            continue

        if total_abbr_len + line_len >= max_abbr_len:
            remainder_abbr_len = max_abbr_len - total_abbr_len
        else:
            remainder_abbr_len = None
        total_abbr_lines += 1
        total_abbr_len += line_len
        abbr_ret_str += line.composer(remainder_abbr_len)

    return full_ret_str, abbr_ret_str
