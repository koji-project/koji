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
import datetime
import hashlib
import os
import random
import re
import ssl
import stat
import urllib
from collections.abc import Mapping
from functools import wraps
from socket import error as socket_error
from threading import local
from urllib.parse import parse_qs
from xml.parsers.expat import ExpatError

import jinja2
from markupsafe import Markup

import koji
import koji.tasks
from koji_cli.lib import greetings
from koji.xmlrpcplus import xmlrpc_client

from . import util as this_module


themeInfo = {}
themeCache = {}

# allowed values for SQL ordering (e.g. -id, package_name, etc.)
RE_ORDER = re.compile(r'^-?\w+$')


def _initValues(environ, title='Build System Info', pageID='summary'):
    global themeInfo
    global themeCache
    values = {}
    values['siteName'] = environ['koji.options'].get('SiteName', 'Koji')
    values['title'] = title
    values['pageID'] = pageID
    now = datetime.datetime.now()
    values['currentDate'] = str(now)
    values['date_str'] = koji.formatTimeLong(now)
    values['literalFooter'] = environ['koji.options'].get('LiteralFooter', True)
    values['terms'] = ''

    # ???
    values['themePath'] = themePath
    values['toggleOrder'] = toggleOrder
    values['toggleSelected'] = toggleSelected
    values['sortImage'] = sortImage
    values['passthrough'] = passthrough
    values['passthrough_except'] = passthrough_except
    values['authToken'] = authToken
    values['util'] = this_module

    themeCache.clear()
    themeInfo.clear()
    themeInfo['name'] = environ['koji.options'].get('KojiTheme', None)
    themeInfo['staticdir'] = environ['koji.options'].get('KojiStaticDir',
                                                         '/usr/share/koji-web/static')
    # maybe this part belongs elsewhere??
    values['localnav'] = ''
    values['localfooter'] = ''
    values['localbottom'] = ''
    localnavpath = themePath('extra-nav.html', local=True)
    if os.path.exists(localnavpath):
        values['localnav'] = SafeValue(
            "".join(open(localnavpath, 'rt', encoding='utf-8').readlines()))
    localfooterpath = themePath("extra-footer.html", local=True)
    if os.path.exists(localfooterpath):
        values['localfooter'] = SafeValue(
            "".join(open(localfooterpath, 'rt', encoding='utf-8').readlines()))
    localbottompath = themePath("extra-bottom.html", local=True)
    if os.path.exists(localbottompath):
        values['localbottom'] = SafeValue(
            "".join(open(localbottompath, 'rt', encoding='utf-8').readlines()))

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


# previously we had a custom SafeValue class here, but the Markup class does the same thing better
def SafeValue(value):
    """Mark a value as safe so that the template will not escape it"""
    # NOTE: this function should only be used in places where we trust the value

    def _MarkTrustedValue(value):
        # wrapper to keep Bandit B704 from complaining
        return value

    return Markup(_MarkTrustedValue(value))


def safe_return(func):
    @wraps(func)
    def _safe(*args, **kwargs):
        return SafeValue(func(*args, **kwargs))
    return _safe


# threadlocal cache
JINJA_CACHE = local()


def get_jinja_env(dirpath):
    if hasattr(JINJA_CACHE, 'env'):
        return JINJA_CACHE.env
    # otherwise
    env = jinja2.Environment(
        loader=jinja2.FileSystemLoader(dirpath),
        autoescape=True,
        line_statement_prefix='#',  # for ease of porting Cheetah templates
        line_comment_prefix='##'
    )
    JINJA_CACHE.env = env
    return env


def _genHTML(environ, fileName):
    if 'koji.currentUser' in environ:
        environ['koji.values']['currentUser'] = environ['koji.currentUser']
        environ['koji.values']['greeting'] = random.choice(greetings)
    else:
        environ['koji.values']['currentUser'] = None
    environ['koji.values']['authToken'] = _genToken(environ)
    if 'mavenEnabled' not in environ['koji.values']:
        if 'koji.session' in environ:
            environ['koji.values']['mavenEnabled'] = environ['koji.session'].mavenEnabled()
        else:
            environ['koji.values']['mavenEnabled'] = False
    if 'winEnabled' not in environ['koji.values']:
        if 'koji.session' in environ:
            environ['koji.values']['winEnabled'] = environ['koji.session'].winEnabled()
        else:
            environ['koji.values']['winEnabled'] = False
    if 'LoginDisabled' not in environ['koji.values']:
        if 'koji.options' in environ:
            environ['koji.values']['LoginDisabled'] = environ['koji.options']['LoginDisabled']
        else:
            environ['koji.values']['LoginDisabled'] = False

    reqdir = os.path.dirname(environ['SCRIPT_FILENAME']) + '/templates'
    env = get_jinja_env(reqdir)
    template = env.get_template(fileName)
    return template.render(**environ['koji.values'])


def _truncTime():
    now = datetime.datetime.now()
    # truncate to the nearest 15 minutes
    return now.replace(minute=(now.minute // 15 * 15), second=0, microsecond=0)


def _genToken(environ, tstamp=None):
    if 'koji.currentLogin' in environ and environ['koji.currentLogin']:
        user = environ['koji.currentLogin']
    else:
        return ''
    if tstamp is None:
        tstamp = _truncTime()
    value = user + str(tstamp) + environ['koji.options']['Secret'].value
    value = value.encode('utf-8')
    return hashlib.sha256(value).hexdigest()


def _getValidTokens(environ):
    tokens = []
    now = _truncTime()
    for delta in (0, 15, 30):
        token_time = now - datetime.timedelta(minutes=delta)
        token = _genToken(environ, token_time)
        if token:
            tokens.append(token)
    return tokens


class FieldStorageCompat(Mapping):
    """Emulate the parts of cgi.FieldStorage that we need"""

    def __init__(self, environ):
        qs = environ.get('QUERY_STRING', '')
        if not qs:
            # for python < 3.11, parse_qs will error on a blank string
            self.data = {}
            return

        data = parse_qs(qs, strict_parsing=True, keep_blank_values=True)
        # replace singleton lists with single values
        for arg in data:
            val = data[arg]
            if isinstance(val, list) and len(val) == 1:
                data[arg] = val[0]
        self.data = data

    # we need getitem, iter, and len for the Mapping inheritance to work

    def __getitem__(self, key):
        return FieldCompat(self.data[key])

    def __iter__(self):
        iter(self.data)

    def __len__(self):
        return len(self.data)

    def getfirst(self, name, default=None):
        """Get first value from list entries"""
        value = self.data.get(name, default)
        if isinstance(value, (list, tuple)):
            return value[0]
        else:
            return value

    def getlist(self, name):
        """Get value, wrap in list if not already"""
        if name not in self.data:
            return []
        value = self.data[name]
        if isinstance(value, (list, tuple)):
            return value
        else:
            return [value]


class FieldCompat:

    def __init__(self, value):
        self.value = value


# compat with jinja 2.x
try:
    pass_context = jinja2.pass_context
except AttributeError:
    pass_context = jinja2.contextfunction
    # (all our uses are functions, not filters)


@pass_context
def toggleOrder(context, sortKey, orderVar='order'):
    """Toggle order for jinja templates"""
    value = context.get(orderVar)
    return _toggleOrder(value, sortKey, orderVar)


def _toggleOrder(value, sortKey, orderVar):
    """
    If orderVar equals 'sortKey', return '-sortKey', else
    return 'sortKey'.
    """
    if value == sortKey:
        return '-' + sortKey
    elif value == '-' + sortKey:
        return sortKey
    elif sortKey == 'id':
        # sort ids reversed first
        return '-id'
    else:
        return sortKey


@safe_return  # avoid escaping quotes
def toggleSelected(var, option, checked=False):
    """
    If the passed in variable var equals the literal value in option,
    return 'selected="selected"', otherwise return ''. If checked is True,
    '"checked="checked"' string is returned
    Used for setting the selected option in select and radio boxes.
    """
    # "var" arg is a misnomer. We expect a value to compare
    value = var
    if value == option:
        if checked:
            return 'checked="checked"'
        else:
            return 'selected="selected"'
    else:
        return ''


@safe_return
@pass_context
def sortImage(context, sortKey, orderVar='order'):
    """jinja version"""
    orderVal = context.get(orderVar)
    return _sortImage(orderVal, sortKey, orderVar)


def _sortImage(orderVal, sortKey, orderVar):
    """
    Return an html img tag suitable for inclusion in the sortKey of a sortable table,
    if the sortValue is "sortKey" or "-sortKey".
    """
    if orderVal == sortKey:
        return '<img src="%s" class="sort" alt="ascending sort"/>' % \
               themePath("images/gray-triangle-up.gif")
    elif orderVal == '-' + sortKey:
        return '<img src="%s" class="sort" alt="descending sort"/>' % \
               themePath("images/gray-triangle-down.gif")
    else:
        return ''


@safe_return
@pass_context
def passthrough(context, *varnames, prefix='&', invert=False):
    if invert:
        _PASSTHROUGH = context.get('_PASSTHROUGH', None)
        if _PASSTHROUGH is None:
            raise Exception('template does not define _PASSTHROUGH')
        varnames = {n for n in _PASSTHROUGH if n not in varnames}
    data = {n: context.get(n, default=None) for n in varnames}
    return _passthrough(data, prefix)


def _passthrough(data, prefix='&'):
    """
    Construct a url parameter string from template vars

    Forms a url parameter string like '&key=value&key2=value' where
    the keys are the requested variable names and the values are pulled
    from the template vars.

    None/missing values are omitted

    If there are no non-None values, an empty string is returned

    The prefix value (default '&') is prepended if any values were found
    """
    result = []
    for var in sorted(data):
        value = data[var]
        if value is not None:
            if isinstance(value, str):
                if value.isdigit():
                    pass
                else:
                    value = urllib.parse.quote(value)
            result.append('%s=%s' % (var, value))
    if result:
        if prefix is None:
            prefix = ''
        return prefix + '&'.join(result)
    else:
        return ''


@pass_context
def passthrough_except(context, *exclude, prefix='&'):
    """
    Construct a string suitable for use as URL
    parameters.  The template calling this method must have
    previously used
    #attr _PASSTHROUGH = ...
    to define the list of variable names to be passed-through.
    Any variables names passed in will be excluded from the
    list of variables in the output string.
    """
    # note that we have to pass context ourselves here
    # the decorator only works when called directly from the template
    return passthrough(context, *exclude, prefix=prefix, invert=True)


def sortByKeyFuncNoneGreatest(key):
    """Return a function to sort a list of maps by the given key.
    None will sort higher than all other values (instead of lower).
    """
    def internal_key(obj):
        v = obj[key]
        # Nones has priority, others are second
        return (v is None, v)
    return internal_key


def paginateList(values, data, start, dataName, prefix=None, order=None, noneGreatest=False,
                 pageSize=50):
    """
    Slice the 'data' list into one page worth.  Start at offset
    'start' and limit the total number of pages to pageSize
    (defaults to 50).  'dataName' is the name under which the
    list will be added to the value map, and prefix is the name
    under which a number of list-related metadata variables will
    be added to the value map.
    """
    if order is not None:
        if not RE_ORDER.match(order):
            raise ValueError("Ordering is not alphanumeric: %r" % order)
        if order.startswith('-'):
            order = order[1:]
            reverse = True
        else:
            reverse = False
        data.sort(key=sortByKeyFuncNoneGreatest(order), reverse=reverse)

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
                   start=None, dataName=None, prefix=None, order=None, pageSize=50,
                   first_page_count=True):
    """Paginate the results of the method with the given name when called with the given args and
    kws. The method must support the queryOpts keyword parameter, and pagination is done in the
    database.

    :param bool first_page_count: If set to False, count is not returned for first page
                                  to speedup default page.
    """
    if args is None:
        args = []
    if kw is None:
        kw = {}
    if start:
        start = int(start)
    if not start or start < 0:
        start = 0
    if not dataName:
        raise Exception('dataName must be specified')
    if not RE_ORDER.match(order):
        raise ValueError("Ordering is not alphanumeric: %r" % order)

    if start == 0 and not first_page_count:
        totalRows = None
    else:
        kw['queryOpts'] = {'countOnly': True}
        totalRows = getattr(server, methodName)(*args, **kw)

    kw['queryOpts'] = {'order': order,
                       'offset': start,
                       'limit': pageSize}
    data = getattr(server, methodName)(*args, **kw)
    count = len(data)

    if start == 0 and count < pageSize:
        # we've got everything on the first page
        totalRows = count

    _populateValues(values, dataName, prefix, data, totalRows, start, count, pageSize, order)

    return data


def paginateResults(server, values, methodName, args=None, kw=None,
                    start=None, dataName=None, prefix=None, order=None, pageSize=50):
    """Paginate the results of the method with the given name when called with the given args and
    kws. This method should only be used when then method does not support the queryOpts command
    (because the logic used to generate the result list prevents filtering/ordering from being done
    in the database). The method must return a list of maps."""
    if args is None:
        args = []
    if kw is None:
        kw = {}
    if start:
        start = int(start)
    if not start or start < 0:
        start = 0
    if not dataName:
        raise Exception('dataName must be specified')
    if not RE_ORDER.match(order):
        raise ValueError("Ordering is not alphanumeric: %r" % order)

    kw['filterOpts'] = {'order': order,
                        'offset': start,
                        'limit': pageSize}

    totalRows, data = server.countAndFilterResults(methodName, *args, **kw)
    count = len(data)

    _populateValues(values, dataName, prefix, data, totalRows, start, count, pageSize, order)

    return data


def _populateValues(values, dataName, prefix, data, totalRows, start, count, pageSize, order):
    """Populate the values list with the data about the list provided."""
    values[dataName] = data
    # Don't use capitalize() to title() here, they mess up
    # mixed-case name
    # Possibly prepend a prefix to the numeric parameters, to avoid namespace collisions
    # when there is more than one list on the same page
    values[(prefix and prefix + 'Start' or 'start')] = start
    values[(prefix and prefix + 'Count' or 'count')] = count
    values[(prefix and prefix + 'Range' or 'range')] = pageSize
    values[(prefix and prefix + 'Order' or 'order')] = order
    currentPage = start // pageSize
    values[(prefix and prefix + 'CurrentPage' or 'currentPage')] = currentPage
    values['total' + dataName[0].upper() + dataName[1:]] = totalRows
    if totalRows is not None:
        totalPages = int(totalRows // pageSize)
        if totalRows % pageSize > 0:
            totalPages += 1
        pages = [page for page in range(0, totalPages)
                 if (abs(page - currentPage) < 100 or ((page + 1) % 100 == 0))]
        values[(prefix and prefix + 'Pages') or 'pages'] = pages
    else:
        values[(prefix and prefix + 'Pages') or 'pages'] = None


def stateName(stateID):
    """Convert a numeric build state into a readable name."""
    return koji.BUILD_STATES[stateID].lower()


@safe_return
def imageTag(name):
    """Return an img tag that loads an icon with the given name"""
    name = escapeHTML(name)
    return '<img class="stateimg" src="%s" title="%s" alt="%s"/>' \
           % (themePath("images/%s.png" % name), name, name)


def stateImage(stateID):
    """Return an IMG tag that loads an icon appropriate for
    the given state"""
    name = stateName(stateID)
    return imageTag(name)


def brStateName(stateID):
    """Convert a numeric buildroot state into a readable name."""
    if stateID is None:
        return '-'
    return koji.BR_STATES[stateID].lower()


def brStateImage(stateID):
    """Return an IMG tag that loads an icon appropriate for
    the given state"""
    name = brStateName(stateID)
    return imageTag(name)


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


def repoState(stateID):
    """Convert a numeric repo state into a readable name"""
    return koji.REPO_STATES[stateID].lower()


def taskState(stateID):
    """Convert a numeric task state into a readable name"""
    return koji.TASK_STATES[stateID].lower()


formatTime = koji.formatTime
formatTimeRSS = koji.formatTimeLong
formatTimeLong = koji.formatTimeLong


def formatTimestampDifference(start_ts, end_ts, in_days=False):
    diff = end_ts - start_ts
    seconds = diff % 60
    diff = diff // 60
    minutes = diff % 60
    diff = diff // 60
    hours = diff
    if in_days:
        return round(hours / 24, 1)
    return "%d:%02d:%02d" % (hours, minutes, seconds)


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
                s = "%s %s" % (s, version)
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

    if mode & stat.S_ISUID:
        result = result[:3] + 's' + result[4:]
    if mode & stat.S_ISGID:
        result = result[:6] + 's' + result[7:]

    return result


def formatThousands(value):
    return '{:,} B'.format(value)


def formatNatural(value):
    suffix = ['B', 'KB', 'MB', 'GB']
    suff_index = 0
    while value >= 1024 and suff_index < 3:
        suff_index += 1  # increment the index of the suffix
        value = value / 1024.0  # apply the division
    return '{:.2f} {}'.format(value, suffix[suff_index])


@safe_return
def formatLink(url):
    """Turn a string into an HTML link if it looks vaguely like a URL.
    If it doesn't, just return it properly escaped."""
    url = escapeHTML(url.strip())
    m = re.match(r'(https?|ssh|git|obs)://.*', url, flags=re.IGNORECASE)
    if m:
        return '<a href="{}">{}</a>'.format(url, url)

    return url


@safe_return
def formatRPM(rpminfo, link=True):
    """Format an rpm dict for display"""
    rpminfo = rpminfo.copy()
    if rpminfo.get('epoch'):
        rpminfo['epoch'] = str(rpminfo['epoch']) + ':'
    else:
        rpminfo['epoch'] = ''
    if rpminfo.get('draft'):
        rpminfo['suffix'] = f" (draft_{rpminfo.get('build_id', '???')})"
    else:
        rpminfo['suffix'] = ''
    label = escapeHTML("%(name)s-%(epoch)s%(version)s-%(release)s.%(arch)s%(suffix)s" % rpminfo)
    if link:
        rpm_id = urllib.parse.quote(str(rpminfo['id']))
        return f'<a href="rpminfo?rpmID={rpm_id}">{label}</a>'
    else:
        return label


def taskScratchClass(task_object):
    """ Return a css class indicating whether or not this task is a scratch
    build.
    """
    method = task_object['method']
    request = task_object['request']
    if method == 'build':
        try:
            opts = koji.tasks.parse_task_params(method, request)
            if opts.get('scratch'):
                return "scratch"
        except Exception:
            # not a build or broken task
            pass
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
    " : &quot;
    ' : &#x27;
    """
    if isinstance(value, Markup):
        return str(value)
    if not value:
        return str(value)

    value = koji.fixEncoding(str(value))
    return re.sub(r'&(?![a-zA-Z0-9#]+;)', '&amp;', value).\
        replace('<', '&lt;').\
        replace('>', '&gt;').\
        replace('"', '&quot;').\
        replace("'", '&#x27;')


@safe_return
@pass_context
def authToken(context, first=False, form=False):
    token = context.get('authToken', None)
    return _authToken(token, first, form)


def _authToken(token, first, form):
    """Return the current authToken if it exists.
    If form is True, return it enclosed in a hidden input field.
    Otherwise, return it in a format suitable for appending to a URL.
    If first is True, prefix it with ?, otherwise prefix it
    with &.  If no authToken exists, return an empty string."""
    if token is not None:
        token = escapeHTML(token)
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
    elif isinstance(error, (socket_error, ssl.SSLError)):
        str = """\
The web interface is having difficulty communicating with the main \
server. This most likely indicates a network issue."""
        level = 1
    elif isinstance(error, (xmlrpc_client.ProtocolError, ExpatError)):
        str = """\
The main server returned an invalid response. This could be caused by \
a network issue or load issues on the server."""
        level = 1
    else:
        str = "An error has occurred while processing your request."
    return str, level


class TaskResultFragment(object):
    """Represent an HTML fragment composed from texts and tags.

    This class permits us to compose HTML fragment by the default
    composer method or self-defined composer function.

    Public attributes:
        - text
        - size
        - need_escape
        - begin_tag
        - eng_tag
        - composer
        - empty_str_placeholder
    """

    def __init__(self, text='', size=None, need_escape=True, begin_tag='',
                 end_tag='', composer=None, empty_str_placeholder=None):
        self.text = text
        if size is None:
            self.size = len(text)
        else:
            self.size = size
        self.need_escape = need_escape
        self.begin_tag = begin_tag
        self.end_tag = end_tag
        if composer is None:
            self.composer = self.default_composer
        else:
            self.composer = lambda length=None: composer(self, length)
        if empty_str_placeholder is None:
            self.empty_str_placeholder = '...'
        else:
            self.empty_str_placeholder = empty_str_placeholder

    def default_composer(self, length=None):
        if length is None:
            text = self.text
        else:
            text = self.text[:length]
        if self.need_escape:
            text = escapeHTML(text)
        if self.size > 0 and text == '':
            text = self.empty_str_placeholder
        return '%s%s%s' % (self.begin_tag, text, self.end_tag)


class TaskResultLine(object):
    """Represent an HTML line fragment.

    This class permits us from several TaskResultFragment instances
    to compose an HTML fragment that ends with a line break. You
    can use the default composer method or give a self-defined version.

    Public attributes:
        - fragments
        - need_escape
        - begin_tag
        - end_tag
        - composer
    """

    def __init__(self, fragments=None, need_escape=True, begin_tag='',
                 end_tag='<br />', composer=None):
        if fragments is None:
            self.fragments = []
        else:
            self.fragments = fragments

        self.need_escape = need_escape
        self.begin_tag = begin_tag
        self.end_tag = end_tag
        if composer is None:
            self.composer = self.default_composer
        else:

            def composer_wrapper(length=None, postscript=None):
                return composer(self, length, postscript)

            self.composer = composer_wrapper
        self.size = self._size()

    def default_composer(self, length=None, postscript=None):
        line_text = ''
        size = 0
        if postscript is None:
            postscript = ''

        for fragment in self.fragments:
            if length is None:
                line_text += fragment.composer()
            else:
                if size >= length:
                    break
                remainder_size = length - size
                line_text += fragment.composer(remainder_size)
                size += fragment.size

        if self.need_escape:
            line_text = escapeHTML(line_text)

        return '%s%s%s%s' % (self.begin_tag, line_text, postscript, self.end_tag)

    def _size(self):
        return sum([fragment.size for fragment in self.fragments])


def _parse_value(key, value, sep=', '):
    _str = None
    begin_tag = ''
    end_tag = ''
    need_escape = True
    if key in ('brootid', 'buildroot_id'):
        # do the escaping ourselves since we include html
        need_escape = False
        brid = urllib.parse.quote(str(value))
        _str = escapeHTML(value)
        begin_tag = '<a href="buildrootinfo?buildrootID=%s">' % brid
        end_tag = '</a>'
    elif isinstance(value, list):
        _str = sep.join([str(val) for val in value])
    elif isinstance(value, dict):
        _str = sep.join(['%s=%s' % ((n == '' and "''" or n), v)
                         for n, v in value.items()])
    else:
        _str = str(value)
    if _str is None:
        _str = ''

    return TaskResultFragment(text=_str, need_escape=need_escape,
                              begin_tag=begin_tag, end_tag=end_tag)


def task_result_to_html(result=None, exc_class=None,
                        max_abbr_lines=None, max_abbr_len=None,
                        abbr_postscript=None):
    """convert the result to a mutiple lines HTML fragment

    Args:
        result: task result. Default is empty string.
        exc_class: Exception raised when access the task result.
        max_abbr_lines: maximum abbreviated result lines. Default is 11.
        max_abbr_len: maximum abbreviated result length. Default is 512.

    Returns:
        Tuple of full result and abbreviated result.
    """
    default_max_abbr_result_lines = 5
    default_max_abbr_result_len = 400

    if max_abbr_lines is None:
        max_abbr_lines = default_max_abbr_result_lines
    if max_abbr_len is None:
        max_abbr_len = default_max_abbr_result_len

    postscript_fragment = TaskResultFragment(
        need_escape=False,
        text='...', end_tag='</a>',
        begin_tag='<a href="#" collapse" %s %s>' % (
            'id="toggle-full-result"',
            'style="display: none;text-decoration:none;"'))

    if abbr_postscript is None:
        abbr_postscript = postscript_fragment.composer()
    elif isinstance(abbr_postscript, TaskResultFragment):
        abbr_postscript = abbr_postscript.composer()
    elif isinstance(abbr_postscript, str):
        abbr_postscript = abbr_postscript
    else:
        abbr_postscript = '...'

    if not abbr_postscript.startswith(' '):
        abbr_postscript = ' %s' % abbr_postscript

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
        fragment = TaskResultFragment(text=_str, need_escape=True)
        line = TaskResultLine(fragments=[fragment],
                              need_escape=False,  # fragment already escaped
                              begin_tag='<pre>', end_tag='</pre>')
        lines.append(line)
    elif isinstance(result, dict):

        def composer(line, length=None, postscript=None):
            if postscript is None:
                postscript = ''
            key_fragment = line.fragments[0]
            val_fragment = line.fragments[1]
            if length is None:
                return '%s%s = %s%s%s' % (line.begin_tag, key_fragment.composer(),
                                          val_fragment.composer(), postscript,
                                          line.end_tag)
            first_part_len = len('%s = ') + key_fragment.size
            remainder_len = length - first_part_len
            if remainder_len < 0:
                remainder_len = 0

            return '%s%s = %s%s%s' % (
                line.begin_tag, key_fragment.composer(),
                val_fragment.composer(remainder_len), postscript, line.end_tag)

        for k, v in result.items():
            if k == 'properties':
                _str = "properties = %s" % _parse_properties(v)
                fragment = TaskResultFragment(text=_str, need_escape=False)
                line = TaskResultLine(fragments=[fragment], need_escape=True)
            elif k != '__starstar':
                val_fragment = _parse_value(k, v)
                key_fragment = TaskResultFragment(text=k, need_escape=True)
                # fragment already escaped
                line = TaskResultLine(fragments=[key_fragment, val_fragment],
                                      need_escape=False, composer=composer)
            lines.append(line)
    else:
        if result is not None:
            fragment = _parse_value('', result)
            # fragment already escaped
            line = TaskResultLine(fragments=[fragment], need_escape=False)
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
            abbr_ret_str += line.composer(remainder_abbr_len, postscript=abbr_postscript)
        else:
            abbr_ret_str += line.composer()
        total_abbr_lines += 1
        total_abbr_len += line_len

    return SafeValue(full_ret_str), SafeValue(abbr_ret_str)
