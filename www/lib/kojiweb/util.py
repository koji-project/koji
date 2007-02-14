import time
import koji

def toggleOrder(template, sortKey, orderVar='order'):
    """
    If orderVar equals 'sortKey', return '-sortKey', else
    return 'sortKey'.
    """
    if template.getVar(orderVar) == sortKey:
        return '-' + sortKey
    else:
        return sortKey

def sortImage(template, sortKey, orderVar='order'):
    """
    Return an html img tag suitable for inclusion in the sortKey of a sortable table,
    if the sortValue is "sortKey" or "-sortKey".
    """
    orderVal = template.getVar(orderVar)
    if orderVal == sortKey:
        return '<img src="/koji-static/images/gray-triangle-up.gif" width="10" height="9" class="sort"/>'
    elif orderVal == '-' + sortKey:
        return '<img src="/koji-static/images/gray-triangle-down.gif" width="10" height="9" class="sort"/>'
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
    return '<img class="stateimg" src="/koji-static/images/%s.png" title="%s" alt="%s"/>' \
           % (name, name, name)
    
def stateImage(stateID):
    """Return an IMG tag that loads an icon appropriate for
    the given state"""
    name = stateName(stateID)
    return imageTag(name)

def brStateName(stateID):
    """Convert a numeric buildroot state into a readable name."""
    return koji.BR_STATES[stateID].lower()

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

    return value.replace('&', '&amp;').\
           replace('<', '&lt;').\
           replace('>', '&gt;')
