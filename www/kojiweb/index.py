import os
import os.path
import re
import sys
import mimetypes
import mod_python
import mod_python.Cookie
import Cheetah.Filters
import Cheetah.Template
import datetime
import time
import koji
import kojiweb.util
from kojiweb.util import _initValues
from kojiweb.util import _genHTML
from kojiweb.util import _getValidTokens

# Convenience definition of a commonly-used sort function
_sortbyname = kojiweb.util.sortByKeyFunc('name')

def _setUserCookie(req, user):
    options = req.get_options()
    # include the current time in the cookie so we can verify that
    # someone is not using an expired cookie
    cookie = mod_python.Cookie.SignedCookie('user', user + ':' + str(time.time()),
                                            secret=options['Secret'],
                                            secure=True,
                                            path=os.path.dirname(req.uri),
                                            expires=(time.time() + (int(options['LoginTimeout']) * 60 * 60)))
    mod_python.Cookie.add_cookie(req, cookie)

def _clearUserCookie(req):
    cookie = mod_python.Cookie.Cookie('user', '',
                                      path=os.path.dirname(req.uri),
                                      expires=0)
    mod_python.Cookie.add_cookie(req, cookie)

def _getUserCookie(req):
    options = req.get_options()
    cookies = mod_python.Cookie.get_cookies(req,
                                            mod_python.Cookie.SignedCookie,
                                            secret=options['Secret'])
    if cookies.has_key('user') and \
           (type(cookies['user']) is mod_python.Cookie.SignedCookie):
        value =  cookies['user'].value
        if ':' in value:
            user, timestamp = value.split(':')
            timestamp = float(timestamp)
            if (time.time() - timestamp) < (int(options['LoginTimeout']) * 60 * 60):
                # cookie is valid and was created more recently than the login
                # timeout
                return user

    return None

def _krbLogin(req, session, principal):
    options = req.get_options()
    wprinc = options['WebPrincipal']
    keytab = options['WebKeytab']
    ccache = options['WebCCache']
    return session.krb_login(principal=wprinc, keytab=keytab,
                             ccache=ccache, proxyuser=principal)

def _sslLogin(req, session, username):
    options = req.get_options()
    client_cert = options['WebCert']
    client_ca = options['ClientCA']
    server_ca = options['KojiHubCA']

    return session.ssl_login(client_cert, client_ca, server_ca,
                             proxyuser=username)

def _assertLogin(req):
    session = req._session
    options = req.get_options()
    if not (hasattr(req, 'currentLogin') and
            hasattr(req, 'currentUser')):
        raise StandardError, '_getServer() must be called before _assertLogin()'
    elif req.currentLogin and req.currentUser:
        if options.get('WebCert'):
            if not _sslLogin(req, session, req.currentLogin):
                raise koji.AuthError, 'could not login %s via SSL' % req.currentLogin
        elif options.get('WebPrincipal'):
            if not _krbLogin(req, req._session, req.currentLogin):
                raise koji.AuthError, 'could not login using principal: %s' % req.currentLogin
        else:
            raise koji.AuthError, 'KojiWeb is incorrectly configured for authentication, contact the system administrator'

        # verify a valid authToken was passed in to avoid CSRF
        authToken = req.form.get('a', '')
        validTokens = _getValidTokens(req)
        if authToken and authToken in validTokens:
            # we have a token and it's valid
            pass
        else:
            # their authToken is likely expired
            # send them back to the page that brought them here so they
            # can re-click the link with a valid authToken
            _redirectBack(req, page=None, forceSSL=(_getBaseURL(req).startswith('https://')))
            assert False
    else:
        mod_python.util.redirect(req, 'login')
        assert False

def _getServer(req):
    serverURL = req.get_options().get('KojiHubURL', 'http://localhost/kojihub')
    session = koji.ClientSession(serverURL)
    
    req.currentLogin = _getUserCookie(req)
    if req.currentLogin:
        req.currentUser = session.getUser(req.currentLogin)
        if not req.currentUser:
            raise koji.AuthError, 'could not get user for principal: %s' % req.currentLogin
        _setUserCookie(req, req.currentLogin)
    else:
        req.currentUser = None
    
    req._session = session
    return session

def _construct_url(req, page):
    port = req.connection.local_addr[1]
    url_scheme = 'http'
    env = req.subprocess_env
    if env.get('HTTPS') == 'on':
        url_scheme = 'https'
    if (url_scheme == 'https' and port == 443) or \
        (url_scheme == 'http' and port == 80):
        return "%s://%s%s" % (url_scheme, req.hostname, page)
    return "%s://%s:%d%s" % (url_scheme, req.hostname, port, page)

def _getBaseURL(req):
    pieces = req.uri.split('/')
    base = '/'.join(pieces[:-1])
    return _construct_url(req, base)

def _redirectBack(req, page, forceSSL):
    if page:
        # We'll work with the page we were given
        pass
    elif req.headers_in.get('Referer'):
        page = req.headers_in.get('Referer')
    else:
        page = 'index'

    # Modify the scheme if necessary
    if page.startswith('http'):
        pass
    elif page.startswith('/'):
        page = _construct_url(req, page)
    else:
        page = _getBaseURL(req) + '/' + page
    if forceSSL:
        page = page.replace('http:', 'https:')
    else:
        page = page.replace('https:', 'http:')

    # and redirect to the page
    mod_python.util.redirect(req, page)

def login(req, page=None):
    session = _getServer(req)
    options = req.get_options()

    # try SSL first, fall back to Kerberos
    if options.get('WebCert'):
        req.add_common_vars()
        env = req.subprocess_env
        if not env.get('HTTPS') == 'on':
            dest = 'login'
            if page:
                dest = dest + '?page=' + page
            _redirectBack(req, dest, forceSSL=True)
            return

        if env.get('SSL_CLIENT_VERIFY') != 'SUCCESS':
            raise koji.AuthError, 'could not verify client: %s' % env.get('SSL_CLIENT_VERIFY')

        # use the subject's common name as their username
        username = env.get('SSL_CLIENT_S_DN_CN')
        if not username:
            raise koji.AuthError, 'unable to get user information from client certificate'
        
        if not _sslLogin(req, session, username):
            raise koji.AuthError, 'could not login %s using SSL certificates' % username
        
    elif options.get('WebPrincipal'):
        principal = req.user
        if not principal:
            raise koji.AuthError, 'configuration error: mod_auth_kerb should have performed authentication before presenting this page'

        if not _krbLogin(req, session, principal):
            raise koji.AuthError, 'could not login using principal: %s' % principal
        
        username = principal
    else:
        raise koji.AuthError, 'KojiWeb is incorrectly configured for authentication, contact the system administrator'

    _setUserCookie(req, username)
    # To protect the session cookie, we must forceSSL
    _redirectBack(req, page, forceSSL=True)

def logout(req, page=None):
    _clearUserCookie(req)

    _redirectBack(req, page, forceSSL=False)

def index(req, packageOrder='package_name', packageStart=None):
    values = _initValues(req)
    server = _getServer(req)

    user = req.currentUser

    values['builds'] = server.listBuilds(userID=(user and user['id'] or None), queryOpts={'order': '-build_id', 'limit': 10})

    taskOpts = {'parent': None, 'decode': True}
    if user:
        taskOpts['owner'] = user['id']
    values['tasks'] = server.listTasks(opts=taskOpts, queryOpts={'order': '-id', 'limit': 10})

    values['order'] = '-id'

    if user:
        packages = kojiweb.util.paginateResults(server, values, 'listPackages', kw={'userID': user['id'], 'with_dups': True},
                                                start=packageStart, dataName='packages', prefix='package', order=packageOrder, pageSize=10)
        
        notifs = server.getBuildNotifications(user['id'])
        notifs.sort(kojiweb.util.sortByKeyFunc('id'))
        # XXX Make this a multicall
        for notif in notifs:
            notif['package'] = None
            if notif['package_id']:
                notif['package'] = server.getPackage(notif['package_id'])
    
            notif['tag'] = None
            if notif['tag_id']:
                notif['tag'] = server.getTag(notif['tag_id'])
        values['notifs'] = notifs
        
    values['user'] = user
    values['welcomeMessage'] = req.get_options().get('KojiGreeting', 'Welcome to Koji Web')
    
    return _genHTML(req, 'index.chtml')

def notificationedit(req, notificationID):
    server = _getServer(req)
    _assertLogin(req)
    
    notificationID = int(notificationID)
    notification = server.getBuildNotification(notificationID)
    if notification == None:
        raise koji.GenericError, 'no notification with ID: %i' % notificationID

    form = req.form

    if form.has_key('save'):
        package_id = form['package']
        if package_id == 'all':
            package_id = None
        else:
            package_id = int(package_id)

        tag_id = form['tag']
        if tag_id == 'all':
            tag_id = None
        else:
            tag_id = int(tag_id)

        if form.has_key('success_only'):
            success_only = True
        else:
            success_only = False
        
        server.updateNotification(notification['id'], package_id, tag_id, success_only)
        
        mod_python.util.redirect(req, 'index')
    elif form.has_key('cancel'):
        mod_python.util.redirect(req, 'index')
    else:
        values = _initValues(req, 'Edit Notification')

        values['notif'] = notification
        packages = server.listPackages()
        packages.sort(kojiweb.util.sortByKeyFunc('package_name'))
        values['packages'] = packages
        tags = server.listTags(queryOpts={'order': 'name'})
        values['tags'] = tags

        return _genHTML(req, 'notificationedit.chtml')

def notificationcreate(req):
    server = _getServer(req)
    _assertLogin(req)
    
    form = req.form

    if form.has_key('add'):
        user = req.currentUser
        if not user:
            raise koji.GenericError, 'not logged-in'
        
        package_id = form['package']
        if package_id == 'all':
            package_id = None
        else:
            package_id = int(package_id)

        tag_id = form['tag']
        if tag_id == 'all':
            tag_id = None
        else:
            tag_id = int(tag_id)

        if form.has_key('success_only'):
            success_only = True
        else:
            success_only = False
        
        server.createNotification(user['id'], package_id, tag_id, success_only)
        
        mod_python.util.redirect(req, 'index')
    elif form.has_key('cancel'):
        mod_python.util.redirect(req, 'index')
    else:
        values = _initValues(req, 'Edit Notification')

        values['notif'] = None
        packages = server.listPackages()
        packages.sort(kojiweb.util.sortByKeyFunc('package_name'))
        values['packages'] = packages
        tags = server.listTags(queryOpts={'order': 'name'})
        values['tags'] = tags

        return _genHTML(req, 'notificationedit.chtml')

def notificationdelete(req, notificationID):
    server = _getServer(req)
    _assertLogin(req)
    
    notificationID = int(notificationID)
    notification = server.getBuildNotification(notificationID)
    if not notification:
        raise koji.GenericError, 'no notification with ID: %i' % notificationID

    server.deleteNotification(notification['id'])

    mod_python.util.redirect(req, 'index')

def hello(req):
    return _getServer(req).hello()

def showSession(req):
    return _getServer(req).showSession()

# All Tasks
_TASKS = ['build',
          'buildSRPMFromSCM',
          'buildArch',
          'chainbuild',
          'maven',
          'buildMaven',
          'wrapperRPM',
          'winbuild',
          'vmExec',
          'waitrepo',
          'tagBuild',
          'newRepo',
          'createrepo',
          'buildNotification',
          'tagNotification',
          'dependantTask',
          'createLiveCD',
          'createAppliance']
# Tasks that can exist without a parent
_TOPLEVEL_TASKS = ['build', 'buildNotification', 'chainbuild', 'maven', 'wrapperRPM', 'winbuild', 'newRepo', 'tagBuild', 'tagNotification', 'waitrepo', 'createLiveCD', 'createAppliance']
# Tasks that can have children
_PARENT_TASKS = ['build', 'chainbuild', 'maven', 'winbuild', 'newRepo']

def tasks(req, owner=None, state='active', view='tree', method='all', hostID=None, channelID=None, start=None, order='-id'):
    values = _initValues(req, 'Tasks', 'tasks')
    server = _getServer(req)

    opts = {'decode': True}
    if owner:
        if owner.isdigit():
            owner = int(owner)
        ownerObj = server.getUser(owner, strict=True)
        opts['owner'] = ownerObj['id']
        values['owner'] = ownerObj['name']
        values['ownerObj'] = ownerObj
    else:
        values['owner'] = None
        values['ownerObj'] = None

    values['users'] = server.listUsers(queryOpts={'order': 'name'})

    if method in _TASKS:
        opts['method'] = method
    else:
        method = 'all'
    values['method'] = method
    values['alltasks'] = _TASKS

    treeEnabled = True
    if hostID or (method not in ['all'] + _PARENT_TASKS):
        # force flat view if we're filtering by a hostID or a task that never has children
        if view == 'tree':
            view = 'flat'
        # don't let them choose tree view either
        treeEnabled = False
    values['treeEnabled'] = treeEnabled

    toplevelEnabled = True
    if method not in ['all'] + _TOPLEVEL_TASKS:
        # force flat view if we're viewing a task that is never a top-level task
        if view == 'toplevel':
            view = 'flat'
        toplevelEnabled = False
    values['toplevelEnabled'] = toplevelEnabled

    values['view'] = view

    if view == 'tree':
        treeDisplay = True
    else:
        treeDisplay = False
    values['treeDisplay'] = treeDisplay

    if view in ('tree', 'toplevel'):
        opts['parent'] = None
    
    if state == 'active':
        opts['state'] = [koji.TASK_STATES['FREE'], koji.TASK_STATES['OPEN'], koji.TASK_STATES['ASSIGNED']]
    elif state == 'all':
        pass
    else:
        # Assume they've passed in a state name
        opts['state'] = [koji.TASK_STATES[state.upper()]]
    values['state'] = state

    if hostID:
        hostID = int(hostID)
        host = server.getHost(hostID, strict=True)
        opts['host_id'] = host['id']
        values['host'] = host
        values['hostID'] = host['id']
    else:
        values['host'] = None
        values['hostID'] = None

    if channelID:
        try:
            channelID = int(channelID)
        except ValueError:
            pass
        channel = server.getChannel(channelID, strict=True)
        opts['channel_id'] = channel['id']
        values['channel'] = channel
        values['channelID'] = channel['id']
    else:
        values['channel'] = None
        values['channelID'] = None

    loggedInUser = req.currentUser
    values['loggedInUser'] = loggedInUser

    values['order'] = order

    tasks = kojiweb.util.paginateMethod(server, values, 'listTasks', kw={'opts': opts},
                                        start=start, dataName='tasks', prefix='task', order=order)
    
    if view == 'tree':
        server.multicall = True
        for task in tasks:
            server.getTaskDescendents(task['id'], request=True)
        descendentList = server.multiCall()
        for task, [descendents] in zip(tasks, descendentList):
            task['descendents'] = descendents

    return _genHTML(req, 'tasks.chtml')

def taskinfo(req, taskID):
    server = _getServer(req)
    values = _initValues(req, 'Task Info', 'tasks')

    taskID = int(taskID)
    task = server.getTaskInfo(taskID, request=True)
    if not task:
        raise koji.GenericError, 'invalid task ID: %s' % taskID

    values['title'] = koji.taskLabel(task) + ' | Task Info'

    values['task'] = task
    params = task['request']
    values['params'] = params

    if task['channel_id']:
        channel = server.getChannel(task['channel_id'])
        values['channelName'] = channel['name']
    else:
        values['channelName'] = None
    if task['host_id']:
        host = server.getHost(task['host_id'])
        values['hostName'] = host['name']
    else:
        values['hostName'] = None
    if task['owner']:
        owner = server.getUser(task['owner'])
        values['owner'] = owner
    else:
        values['owner'] = None
    if task['parent']:
        parent = server.getTaskInfo(task['parent'], request=True)
        values['parent'] = parent
    else:
        values['parent'] = None
    
    descendents = server.getTaskDescendents(task['id'], request=True)
    values['descendents'] = descendents

    builds = server.listBuilds(taskID=task['id'])
    if builds:
        taskBuild = builds[0]
    else:
        taskBuild = None
    values['taskBuild'] = taskBuild

    values['estCompletion'] = None
    if taskBuild and taskBuild['state'] == koji.BUILD_STATES['BUILDING']:
        avgDuration = server.getAverageBuildDuration(taskBuild['package_id'])
        if avgDuration != None:
            avgDelta = datetime.timedelta(seconds=avgDuration)
            startTime = datetime.datetime.fromtimestamp(taskBuild['creation_ts'])
            values['estCompletion'] = startTime + avgDelta

    buildroots = server.listBuildroots(taskID=task['id'])
    values['buildroots'] = buildroots

    if task['method'] == 'buildArch':
        buildTag = server.getTag(params[1])
        values['buildTag'] = buildTag
    elif task['method'] == 'buildMaven':
        buildTag = params[1]
        values['buildTag'] = buildTag
    elif task['method'] == 'createLiveCD' or task['method'] == 'createAppliance':
        values['image'] = server.getImageInfo(taskID=taskID)
    elif task['method'] == 'buildSRPMFromSCM':
        if len(params) > 1:
            buildTag = server.getTag(params[1])
            values['buildTag'] = buildTag
    elif task['method'] == 'tagBuild':
        destTag = server.getTag(params[0])
        build = server.getBuild(params[1])
        values['destTag'] = destTag
        values['build'] = build
    elif task['method'] == 'newRepo':
        tag = server.getTag(params[0])
        values['tag'] = tag
    elif task['method'] == 'tagNotification':
        destTag = None
        if params[2]:
            destTag = server.getTag(params[2])
        srcTag = None
        if params[3]:
            srcTag = server.getTag(params[3])
        build = server.getBuild(params[4])
        user = server.getUser(params[5])
        values['destTag'] = destTag
        values['srcTag'] = srcTag
        values['build'] = build
        values['user'] = user
    elif task['method'] == 'dependantTask':
        deps = [server.getTaskInfo(depID, request=True) for depID in params[0]]
        values['deps'] = deps
    elif task['method'] == 'wrapperRPM':
        buildTag = params[1]
        values['buildTag'] = buildTag
        if params[3]:
            wrapTask = server.getTaskInfo(params[3]['id'], request=True)
            values['wrapTask'] = wrapTask
    elif task['method'] == 'restartVerify':
        values['rtask'] = server.getTaskInfo(params[0], request=True)
    
    if task['state'] in (koji.TASK_STATES['CLOSED'], koji.TASK_STATES['FAILED']):
        try:
            result = server.getTaskResult(task['id'])
            values['result'] = result
            values['excClass'] = None
        except:
            excClass, exc = sys.exc_info()[:2]
            values['result'] = exc
            values['excClass'] = excClass
            # clear the exception, since we're just using
            # it for display purposes
            sys.exc_clear()
    else:
        values['result'] = None
        values['excClass'] = None

    output = server.listTaskOutput(task['id'])
    output.sort(_sortByExtAndName)
    values['output'] = output
    if req.currentUser:
        values['perms'] = server.getUserPerms(req.currentUser['id'])
    else:
        values['perms'] = []
    
    return _genHTML(req, 'taskinfo.chtml')

def imageinfo(req, imageID):
    """Do some prep work and generate the imageinfo page for kojiweb."""
    server = _getServer(req)
    values = _initValues(req, 'Image Information')
    imageURL = req.get_options().get('KojiImagesURL', 'http://localhost/images')
    imageID = int(imageID)
    image = server.getImageInfo(imageID=imageID, strict=True)
    values['image'] = image
    values['title'] = image['filename'] + ' | Image Information'
    values['buildroot'] = server.getBuildroot(image['br_id'], strict=True)
    values['task'] = server.getTaskInfo(image['task_id'], request=True)
    if image['mediatype'] == 'LiveCD ISO':
        values['imageBase'] = imageURL + '/' + koji.pathinfo.livecdRelPath(image['id'])
    else:
        values['imageBase'] = imageURL + '/' + koji.pathinfo.applianceRelPath(image['id'])

    return _genHTML(req, 'imageinfo.chtml')

def taskstatus(req, taskID):
    server = _getServer(req)

    taskID = int(taskID)
    task = server.getTaskInfo(taskID)
    if not task:
        return ''
    files = server.listTaskOutput(taskID, stat=True)
    output = '%i:%s\n' % (task['id'], koji.TASK_STATES[task['state']])
    for filename, file_stats in files.items():
        output += '%s:%s\n' % (filename, file_stats['st_size'])

    return output

def resubmittask(req, taskID):
    server = _getServer(req)
    _assertLogin(req)
    
    taskID = int(taskID)
    newTaskID = server.resubmitTask(taskID)
    mod_python.util.redirect(req, 'taskinfo?taskID=%i' % newTaskID)

def canceltask(req, taskID):
    server = _getServer(req)
    _assertLogin(req)

    taskID = int(taskID)
    server.cancelTask(taskID)
    mod_python.util.redirect(req, 'taskinfo?taskID=%i' % taskID)

def _sortByExtAndName(a, b):
    """Sort two filenames, first by extension, and then by name."""
    aRoot, aExt = os.path.splitext(a)
    bRoot, bExt = os.path.splitext(b)
    return cmp(aExt, bExt) or cmp(aRoot, bRoot)

def getfile(req, taskID, name, offset=None, size=None):
    server = _getServer(req)
    taskID = int(taskID)

    output = server.listTaskOutput(taskID, stat=True)
    file_info = output.get(name)
    if not file_info:
        raise koji.GenericError, 'no file "%s" output by task %i' % (name, taskID)

    mime_guess = mimetypes.guess_type(name, strict=False)[0]
    if mime_guess:
        req.content_type = mime_guess
    else:
        if name.endswith('.log') or name.endswith('.ks'):
            req.content_type = 'text/plain'
        else:
            req.content_type = 'application/octet-stream'
    if req.content_type != 'text/plain':
        req.headers_out['Content-Disposition'] = 'attachment; filename=%s' % name

    file_size = int(file_info['st_size'])
    if offset is None:
        offset = 0
    else:
        offset = int(offset)
    if size is None:
        size = file_size
    else:
        size = int(size)
    if size < 0:
        size = file_size
    if offset < 0:
        # seeking relative to the end of the file
        if offset < -file_size:
            offset = -file_size
        if size > -offset:
            size = -offset
    else:
        if size > (file_size - offset):
            size = file_size - offset

    req.set_content_length(size)

    remaining = size
    while True:
        if remaining <= 0:
            break
        chunk_size = 1048576
        if remaining < chunk_size:
            chunk_size = remaining
        if offset > 2147483647:
            offset = str(offset)
        content = server.downloadTaskOutput(taskID, name, offset=offset, size=chunk_size)
        if isinstance(offset, str):
            offset = int(offset)
        if not content:
            break
        req.write(content)
        content_length = len(content)
        offset += content_length
        remaining -= content_length

def tags(req, start=None, order=None, childID=None):
    values = _initValues(req, 'Tags', 'tags')
    server = _getServer(req)

    if order == None:
        order = 'name'
    values['order'] = order

    tags = kojiweb.util.paginateMethod(server, values, 'listTags', kw=None,
                                       start=start, dataName='tags', prefix='tag', order=order)

    if req.currentUser:
        values['perms'] = server.getUserPerms(req.currentUser['id'])
    else:
        values['perms'] = []

    values['childID'] = childID
    
    return _genHTML(req, 'tags.chtml')

_PREFIX_CHARS = [chr(char) for char in range(48, 58) + range(97, 123)]

def packages(req, tagID=None, userID=None, order='package_name', start=None, prefix=None, inherited='1'):
    values = _initValues(req, 'Packages', 'packages')
    server = _getServer(req)
    tag = None
    if tagID != None:
        if tagID.isdigit():
            tagID = int(tagID)
        tag = server.getTag(tagID, strict=True)
    values['tagID'] = tagID
    values['tag'] = tag
    user = None
    if userID != None:
        if userID.isdigit():
            userID = int(userID)
        user = server.getUser(userID, strict=True)
    values['userID'] = userID
    values['user'] = user
    values['order'] = order
    if prefix:
        prefix = prefix.lower()[0]
    if prefix not in _PREFIX_CHARS:
        prefix = None
    values['prefix'] = prefix
    inherited = int(inherited)
    values['inherited'] = inherited
    
    packages = kojiweb.util.paginateResults(server, values, 'listPackages',
                                            kw={'tagID': tagID, 'userID': userID, 'prefix': prefix, 'inherited': bool(inherited)},
                                            start=start, dataName='packages', prefix='package', order=order)
    
    values['chars'] = _PREFIX_CHARS
    
    return _genHTML(req, 'packages.chtml')

def packageinfo(req, packageID, tagOrder='name', tagStart=None, buildOrder='-completion_time', buildStart=None):
    values = _initValues(req, 'Package Info', 'packages')
    server = _getServer(req)

    if packageID.isdigit():
        packageID = int(packageID)
    package = server.getPackage(packageID)
    if package == None:
        raise koji.GenericError, 'invalid package ID: %s' % packageID

    values['title'] = package['name'] + ' | Package Info'

    values['package'] = package
    values['packageID'] = package['id']
    
    tags = kojiweb.util.paginateMethod(server, values, 'listTags', kw={'package': package['id']},
                                       start=tagStart, dataName='tags', prefix='tag', order=tagOrder)
    builds = kojiweb.util.paginateMethod(server, values, 'listBuilds', kw={'packageID': package['id']},
                                         start=buildStart, dataName='builds', prefix='build', order=buildOrder)

    return _genHTML(req, 'packageinfo.chtml')

def taginfo(req, tagID, all='0', packageOrder='package_name', packageStart=None, buildOrder='-completion_time', buildStart=None, childID=None):
    values = _initValues(req, 'Tag Info', 'tags')
    server = _getServer(req)

    if tagID.isdigit():
        tagID = int(tagID)
    tag = server.getTag(tagID, strict=True)

    values['title'] = tag['name'] + ' | Tag Info'

    all = int(all)

    numPackages = server.count('listPackages', tagID=tag['id'], inherited=True)
    numBuilds = server.count('listTagged', tag=tag['id'], inherit=True)
    values['numPackages'] = numPackages
    values['numBuilds'] = numBuilds

    inheritance = server.getFullInheritance(tag['id'])
    tagsByChild = {}
    for parent in inheritance:
        child_id = parent['child_id']
        if not tagsByChild.has_key(child_id):
            tagsByChild[child_id] = []
        tagsByChild[child_id].append(child_id)

    srcTargets = server.getBuildTargets(buildTagID=tag['id'])
    srcTargets.sort(_sortbyname)
    destTargets = server.getBuildTargets(destTagID=tag['id'])
    destTargets.sort(_sortbyname)

    values['tag'] = tag
    values['tagID'] = tag['id']
    values['inheritance'] = inheritance
    values['tagsByChild'] = tagsByChild
    values['srcTargets'] = srcTargets
    values['destTargets'] = destTargets
    values['all'] = all
    values['repo'] = server.getRepo(tag['id'], state=koji.REPO_READY)
    values['external_repos'] = server.getExternalRepoList(tag['id'])

    child = None
    if childID != None:
        child = server.getTag(int(childID), strict=True)
    values['child'] = child

    if req.currentUser:
        values['perms'] = server.getUserPerms(req.currentUser['id'])
    else:
        values['perms'] = []
    permList = server.getAllPerms()
    allPerms = dict([(perm['id'], perm['name']) for perm in permList])
    values['allPerms'] = allPerms

    return _genHTML(req, 'taginfo.chtml')

def tagcreate(req):
    server = _getServer(req)
    _assertLogin(req)

    mavenEnabled = server.mavenEnabled()

    form = req.form

    if form.has_key('add'):
        params = {}
        name = form['name'].value
        params['arches'] = form['arches'].value
        params['locked'] = bool(form.has_key('locked'))
        permission = form['permission'].value
        if permission != 'none':
            params['perm'] = int(permission)
        if mavenEnabled:
            params['maven_support'] = bool(form.has_key('maven_support'))
            params['maven_include_all'] = bool(form.has_key('maven_include_all'))

        tagID = server.createTag(name, **params)

        mod_python.util.redirect(req, 'taginfo?tagID=%i' % tagID)
    elif form.has_key('cancel'):
        mod_python.util.redirect(req, 'tags')
    else:
        values = _initValues(req, 'Add Tag', 'tags')

        values['mavenEnabled'] = mavenEnabled

        values['tag'] = None
        values['permissions'] = server.getAllPerms()

        return _genHTML(req, 'tagedit.chtml')

def tagedit(req, tagID):
    server = _getServer(req)
    _assertLogin(req)

    mavenEnabled = server.mavenEnabled()

    tagID = int(tagID)
    tag = server.getTag(tagID)
    if tag == None:
        raise koji.GenericError, 'no tag with ID: %i' % tagID

    form = req.form

    if form.has_key('save'):
        params = {}
        params['name'] = form['name'].value
        params['arches'] = form['arches'].value
        params['locked'] = bool(form.has_key('locked'))
        permission = form['permission'].value
        if permission != 'none':
            params['perm'] = int(permission)
        if mavenEnabled:
            params['maven_support'] = bool(form.has_key('maven_support'))
            params['maven_include_all'] = bool(form.has_key('maven_include_all'))

        server.editTag2(tag['id'], **params)
        
        mod_python.util.redirect(req, 'taginfo?tagID=%i' % tag['id'])
    elif form.has_key('cancel'):
        mod_python.util.redirect(req, 'taginfo?tagID=%i' % tag['id'])
    else:
        values = _initValues(req, 'Edit Tag', 'tags')

        values['mavenEnabled'] = mavenEnabled

        values['tag'] = tag
        values['permissions'] = server.getAllPerms()

        return _genHTML(req, 'tagedit.chtml')

def tagdelete(req, tagID):
    server = _getServer(req)
    _assertLogin(req)

    tagID = int(tagID)
    tag = server.getTag(tagID)
    if tag == None:
        raise koji.GenericError, 'no tag with ID: %i' % tagID

    server.deleteTag(tag['id'])

    mod_python.util.redirect(req, 'tags')

def tagparent(req, tagID, parentID, action):
    server = _getServer(req)
    _assertLogin(req)

    tag = server.getTag(int(tagID), strict=True)
    parent = server.getTag(int(parentID), strict=True)

    if action in ('add', 'edit'):
        form = req.form

        if form.has_key('add') or form.has_key('save'):
            newDatum = {}
            newDatum['parent_id'] = parent['id']
            newDatum['priority'] = int(form['priority'])
            maxdepth = form['maxdepth']
            maxdepth = len(maxdepth) > 0 and int(maxdepth) or None
            newDatum['maxdepth'] = maxdepth
            newDatum['intransitive'] = bool(form.has_key('intransitive'))
            newDatum['noconfig'] = bool(form.has_key('noconfig'))
            newDatum['pkg_filter'] = form['pkg_filter'].value

            data = server.getInheritanceData(tag['id'])
            data.append(newDatum)
                
            server.setInheritanceData(tag['id'], data)
        elif form.has_key('cancel'):
            pass
        else:
            values = _initValues(req, action.capitalize() + ' Parent Tag', 'tags')
            values['tag'] = tag
            values['parent'] = parent

            inheritanceData = server.getInheritanceData(tag['id'])
            maxPriority = 0
            for datum in inheritanceData:
                if datum['priority'] > maxPriority:
                    maxPriority = datum['priority']
            values['maxPriority'] = maxPriority
            inheritanceData = [datum for datum in  inheritanceData \
                               if datum['parent_id'] == parent['id']]
            if len(inheritanceData) == 0:
                values['inheritanceData'] = None
            elif len(inheritanceData) == 1:
                values['inheritanceData'] = inheritanceData[0]
            else:
                raise koji.GenericError, 'tag %i has tag %i listed as a parent more than once' % (tag['id'], parent['id'])
            
            return _genHTML(req, 'tagparent.chtml')
    elif action == 'remove':
        data = server.getInheritanceData(tag['id'])
        for datum in data:
            if datum['parent_id'] == parent['id']:
                datum['delete link'] = True
                break
        else:
            raise koji.GenericError, 'tag %i is not a parent of tag %i' % (parent['id'], tag['id'])

        server.setInheritanceData(tag['id'], data)
    else:
        raise koji.GenericError, 'unknown action: %s' % action

    mod_python.util.redirect(req, 'taginfo?tagID=%i' % tag['id'])

def externalrepoinfo(req, extrepoID):
    values = _initValues(req, 'External Repo Info', 'tags')
    server = _getServer(req)

    if extrepoID.isdigit():
        extrepoID = int(extrepoID)
    extRepo = server.getExternalRepo(extrepoID, strict=True)
    repoTags = server.getTagExternalRepos(repo_info=extRepo['id'])

    values['title'] = extRepo['name'] + ' | External Repo Info'
    values['extRepo'] = extRepo
    values['repoTags'] = repoTags

    return _genHTML(req, 'externalrepoinfo.chtml')

def buildinfo(req, buildID):
    values = _initValues(req, 'Build Info', 'builds')
    server = _getServer(req)

    buildID = int(buildID)
    
    build = server.getBuild(buildID)

    values['title'] = koji.buildLabel(build) + ' | Build Info'

    tags = server.listTags(build['id'])
    tags.sort(_sortbyname)
    rpms = server.listBuildRPMs(build['id'])
    rpms.sort(_sortbyname)
    mavenbuild = server.getMavenBuild(buildID)
    winbuild = server.getWinBuild(buildID)
    if mavenbuild:
        archivetype = 'maven'
    elif winbuild:
        archivetype = 'win'
    else:
        archivetype = None
    archives = server.listArchives(build['id'], type=archivetype, queryOpts={'order': 'filename'})
    archivesByExt = {}
    for archive in archives:
        archivesByExt.setdefault(os.path.splitext(archive['filename'])[1][1:], []).append(archive)

    rpmsByArch = {}
    debuginfoByArch = {}
    for rpm in rpms:
        if koji.is_debuginfo(rpm['name']):
            debuginfoByArch.setdefault(rpm['arch'], []).append(rpm)
        else:
            rpmsByArch.setdefault(rpm['arch'], []).append(rpm)

    if rpmsByArch.has_key('src'):
        srpm = rpmsByArch['src'][0]
        headers = server.getRPMHeaders(srpm['id'], headers=['summary', 'description'])
        values['summary'] = koji.fixEncoding(headers.get('summary'))
        values['description'] = koji.fixEncoding(headers.get('description'))
        values['changelog'] = server.getChangelogEntries(build['id'])

    noarch_log_dest = 'noarch'
    if build['task_id']:
        task = server.getTaskInfo(build['task_id'], request=True)
        if rpmsByArch.has_key('noarch') and \
                [a for a in rpmsByArch.keys() if a not in ('noarch', 'src')]:
            # This build has noarch and other-arch packages, indicating either
            # noarch in extra-arches (kernel) or noarch subpackages.
            # Point the log link to the arch of the buildArch task that the first
            # noarch package came from.  This will be correct in both the
            # extra-arches case (noarch) and the subpackage case (one of the other
            # arches).  If noarch extra-arches and noarch subpackages are mixed in
            # same build, this will become incorrect.
            noarch_rpm = rpmsByArch['noarch'][0]
            if noarch_rpm['buildroot_id']:
                noarch_buildroot = server.getBuildroot(noarch_rpm['buildroot_id'])
                if noarch_buildroot:
                    noarch_task = server.getTaskInfo(noarch_buildroot['task_id'], request=True)
                    if noarch_task:
                        noarch_log_dest = noarch_task['request'][2]

        # get the summary, description, and changelogs from the built srpm
        # if the build is not yet complete
        if build['state'] != koji.BUILD_STATES['COMPLETE']:
            srpm_tasks = server.listTasks(opts={'parent': task['id'], 'method': 'buildSRPMFromSCM'})
            if srpm_tasks:
                srpm_task = srpm_tasks[0]
                if srpm_task['state'] == koji.TASK_STATES['CLOSED']:
                    srpm_path = None
                    for output in server.listTaskOutput(srpm_task['id']):
                        if output.endswith('.src.rpm'):
                            srpm_path = output
                            break
                    if srpm_path:
                        srpm_headers = server.getRPMHeaders(taskID=srpm_task['id'], filepath=srpm_path,
                                                            headers=['summary', 'description'])
                        if srpm_headers:
                            values['summary'] = koji.fixEncoding(srpm_headers['summary'])
                            values['description'] = koji.fixEncoding(srpm_headers['description'])
                        changelog = server.getChangelogEntries(taskID=srpm_task['id'], filepath=srpm_path)
                        if changelog:
                            values['changelog'] = changelog
    else:
        task = None

    values['build'] = build
    values['tags'] = tags
    values['rpmsByArch'] = rpmsByArch
    values['debuginfoByArch'] = debuginfoByArch
    values['task'] = task
    values['mavenbuild'] = mavenbuild
    values['winbuild'] = winbuild
    values['archives'] = archives
    values['archivesByExt'] = archivesByExt
    
    values['noarch_log_dest'] = noarch_log_dest
    if req.currentUser:
        values['perms'] = server.getUserPerms(req.currentUser['id'])
    else:
        values['perms'] = []
    for field in ['summary', 'description', 'changelog']:
        if not values.has_key(field):
            values[field] = None

    if build['state'] == koji.BUILD_STATES['BUILDING']:
        avgDuration = server.getAverageBuildDuration(build['package_id'])
        if avgDuration != None:
            avgDelta = datetime.timedelta(seconds=avgDuration)
            startTime = datetime.datetime.fromtimestamp(build['creation_ts'])
            values['estCompletion'] = startTime + avgDelta
        else:
            values['estCompletion'] = None

    values['downloadBase'] = req.get_options().get('KojiPackagesURL', 'http://localhost/packages')
    values['mavenBase'] = req.get_options().get('KojiMavenURL', 'http://localhost/maven2')

    return _genHTML(req, 'buildinfo.chtml')

def builds(req, userID=None, tagID=None, packageID=None, state=None, order='-build_id', start=None, prefix=None, inherited='1', latest='1', type=None):
    values = _initValues(req, 'Builds', 'builds')
    server = _getServer(req)

    user = None
    if userID:
        if userID.isdigit():
            userID = int(userID)
        user = server.getUser(userID, strict=True)
    values['userID'] = userID
    values['user'] = user

    loggedInUser = req.currentUser
    values['loggedInUser'] = loggedInUser

    values['users'] = server.listUsers(queryOpts={'order': 'name'})

    tag = None
    if tagID:
        if tagID.isdigit():
            tagID = int(tagID)
        tag = server.getTag(tagID, strict=True)
    values['tagID'] = tagID
    values['tag'] = tag

    package = None
    if packageID:
        if packageID.isdigit():
            packageID = int(packageID)
        package = server.getPackage(packageID, strict=True)
    values['packageID'] = packageID
    values['package'] = package

    if state == 'all':
        state = None
    elif state != None:
        state = int(state)
    values['state'] = state

    if prefix:
        prefix = prefix.lower()[0]
    if prefix not in _PREFIX_CHARS:
        prefix = None
    values['prefix'] = prefix
    
    values['order'] = order
    if type in ('maven', 'win'):
        pass
    elif type == 'all':
        type = None
    else:
        type = None
    values['type'] = type

    if tag:
        inherited = int(inherited)
        values['inherited'] = inherited
        latest = int(latest)
        values['latest'] = latest
    else:
        values['inherited'] = None
        values['latest'] = None

    if tag:
        # don't need to consider 'state' here, since only completed builds would be tagged
        builds = kojiweb.util.paginateResults(server, values, 'listTagged', kw={'tag': tag['id'], 'package': (package and package['name'] or None),
                                                                                'owner': (user and user['name'] or None),
                                                                                'type': type,
                                                                                'inherit': bool(inherited), 'latest': bool(latest), 'prefix': prefix},
                                              start=start, dataName='builds', prefix='build', order=order)
    else:
        builds = kojiweb.util.paginateMethod(server, values, 'listBuilds', kw={'userID': (user and user['id'] or None), 'packageID': (package and package['id'] or None),
                                                                               'type': type,
                                                                               'state': state, 'prefix': prefix},
                                             start=start, dataName='builds', prefix='build', order=order)
    
    values['chars'] = _PREFIX_CHARS

    return _genHTML(req, 'builds.chtml')

def users(req, order='name', start=None, prefix=None):
    values = _initValues(req, 'Users', 'users')
    server = _getServer(req)

    if prefix:
        prefix = prefix.lower()[0]
    if prefix not in _PREFIX_CHARS:
        prefix = None
    values['prefix'] = prefix

    values['order'] = order

    users = kojiweb.util.paginateMethod(server, values, 'listUsers', kw={'prefix': prefix},
                                        start=start, dataName='users', prefix='user', order=order)

    values['chars'] = _PREFIX_CHARS
    
    return _genHTML(req, 'users.chtml')

def userinfo(req, userID, packageOrder='package_name', packageStart=None, buildOrder='-completion_time', buildStart=None):
    values = _initValues(req, 'User Info', 'users')
    server = _getServer(req)

    if userID.isdigit():
        userID = int(userID)
    user = server.getUser(userID, strict=True)

    values['title'] = user['name'] + ' | User Info'

    values['user'] = user
    values['userID'] = userID
    values['taskCount'] = server.listTasks(opts={'owner': user['id'], 'parent': None}, queryOpts={'countOnly': True})

    packages = kojiweb.util.paginateResults(server, values, 'listPackages', kw={'userID': user['id'], 'with_dups': True},
                                            start=packageStart, dataName='packages', prefix='package', order=packageOrder, pageSize=10)
    
    builds = kojiweb.util.paginateMethod(server, values, 'listBuilds', kw={'userID': user['id']},
                                         start=buildStart, dataName='builds', prefix='build', order=buildOrder, pageSize=10)
    
    return _genHTML(req, 'userinfo.chtml')

def rpminfo(req, rpmID, fileOrder='name', fileStart=None, buildrootOrder='-id', buildrootStart=None):
    values = _initValues(req, 'RPM Info', 'builds')
    server = _getServer(req)

    rpmID = int(rpmID)
    rpm = server.getRPM(rpmID)

    values['title'] = '%(name)s-%%s%(version)s-%(release)s.%(arch)s.rpm' % rpm + ' | RPM Info'
    epochStr = ''
    if rpm['epoch'] != None:
        epochStr = '%s:' % rpm['epoch']
    values['title'] = values['title'] % epochStr

    build = None
    if rpm['build_id'] != None:
        build = server.getBuild(rpm['build_id'])
    builtInRoot = None
    if rpm['buildroot_id'] != None:
        builtInRoot = server.getBuildroot(rpm['buildroot_id'])
    if rpm['external_repo_id'] == 0:
        values['requires'] = server.getRPMDeps(rpm['id'], koji.DEP_REQUIRE)
        values['requires'].sort(_sortbyname)
        values['provides'] = server.getRPMDeps(rpm['id'], koji.DEP_PROVIDE)
        values['provides'].sort(_sortbyname)
        values['obsoletes'] = server.getRPMDeps(rpm['id'], koji.DEP_OBSOLETE)
        values['obsoletes'].sort(_sortbyname)
        values['conflicts'] = server.getRPMDeps(rpm['id'], koji.DEP_CONFLICT)
        values['conflicts'].sort(_sortbyname)
        headers = server.getRPMHeaders(rpm['id'], headers=['summary', 'description'])
        values['summary'] = koji.fixEncoding(headers.get('summary'))
        values['description'] = koji.fixEncoding(headers.get('description'))
    buildroots = kojiweb.util.paginateMethod(server, values, 'listBuildroots', kw={'rpmID': rpm['id']},
                                             start=buildrootStart, dataName='buildroots', prefix='buildroot',
                                             order=buildrootOrder)

    values['rpmID'] = rpmID
    values['rpm'] = rpm
    values['build'] = build
    values['builtInRoot'] = builtInRoot
    values['buildroots'] = buildroots
    
    files = kojiweb.util.paginateMethod(server, values, 'listRPMFiles', args=[rpm['id']],
                                        start=fileStart, dataName='files', prefix='file', order=fileOrder)

    return _genHTML(req, 'rpminfo.chtml')

def archiveinfo(req, archiveID, fileOrder='name', fileStart=None, buildrootOrder='-id', buildrootStart=None):
    values = _initValues(req, 'Archive Info', 'builds')
    server = _getServer(req)

    archiveID = int(archiveID)
    archive = server.getArchive(archiveID)
    archive_type = server.getArchiveType(type_id=archive['type_id'])
    build = server.getBuild(archive['build_id'])
    maveninfo = False
    if 'group_id' in archive:
        maveninfo = True
    wininfo = False
    if 'relpath' in archive:
        wininfo = True
    builtInRoot = None
    if archive['buildroot_id'] != None:
        builtInRoot = server.getBuildroot(archive['buildroot_id'])
    files = kojiweb.util.paginateMethod(server, values, 'listArchiveFiles', args=[archive['id']],
                                        start=fileStart, dataName='files', prefix='file', order=fileOrder)
    buildroots = kojiweb.util.paginateMethod(server, values, 'listBuildroots', kw={'archiveID': archive['id']},
                                             start=buildrootStart, dataName='buildroots', prefix='buildroot',
                                             order=buildrootOrder)

    values['title'] = archive['filename'] + ' | Archive Info'

    values['archiveID'] = archive['id']
    values['archive'] = archive
    values['archive_type'] = archive_type
    values['build'] = build
    values['maveninfo'] = maveninfo
    values['wininfo'] = wininfo
    values['builtInRoot'] = builtInRoot
    values['buildroots'] = buildroots

    return _genHTML(req, 'archiveinfo.chtml')

def fileinfo(req, filename, rpmID=None, archiveID=None):
    values = _initValues(req, 'File Info', 'builds')
    server = _getServer(req)

    values['rpm'] = None
    values['archive'] = None
    
    if rpmID:
        rpmID = int(rpmID)
        rpm = server.getRPM(rpmID)
        if not rpm:
            raise koji.GenericError, 'invalid RPM ID: %i' % rpmID
        file = server.getRPMFile(rpm['id'], filename)
        if not file:
            raise koji.GenericError, 'no file %s in RPM %i' % (filename, rpmID)
        values['rpm'] = rpm
    elif archiveID:
        archiveID = int(archiveID)
        archive = server.getArchive(archiveID)
        if not archive:
            raise koji.GenericError, 'invalid archive ID: %i' % archiveID
        file = server.getArchiveFile(archive['id'], filename)
        if not file:
            raise koji.GenericError, 'no file %s in archive %i' % (filename, archiveID)
        values['archive'] = archive
    else:
        raise koji.GenericError, 'either rpmID or archiveID must be specified'

    values['title'] = file['name'] + ' | File Info'

    values['file'] = file

    return _genHTML(req, 'fileinfo.chtml')

def cancelbuild(req, buildID):
    server = _getServer(req)
    _assertLogin(req)
    
    buildID = int(buildID)
    build = server.getBuild(buildID)
    if build == None:
        raise koji.GenericError, 'unknown build ID: %i' % buildID

    result = server.cancelBuild(build['id'])
    if not result:
        raise koji.GenericError, 'unable to cancel build'

    mod_python.util.redirect(req, 'buildinfo?buildID=%i' % build['id'])

def hosts(req, state='enabled', start=None, order='name'):
    values = _initValues(req, 'Hosts', 'hosts')
    server = _getServer(req)

    values['order'] = order

    args = {}

    if state == 'enabled':
        args['enabled'] = True
    elif state == 'disabled':
        args['enabled'] = False
    else:
        state = 'all'
    values['state'] = state

    hosts = server.listHosts(**args)
    
    server.multicall = True
    for host in hosts:
        server.getLastHostUpdate(host['id'])
    updates = server.multiCall()
    for host, [lastUpdate] in zip(hosts, updates):
        host['last_update'] = lastUpdate

    # Paginate after retrieving last update info so we can sort on it
    kojiweb.util.paginateList(values, hosts, start, 'hosts', 'host', order)

    return _genHTML(req, 'hosts.chtml')

def hostinfo(req, hostID=None, userID=None):
    values = _initValues(req, 'Host Info', 'hosts')
    server = _getServer(req)

    if hostID:
        if hostID.isdigit():
            hostID = int(hostID)
        host = server.getHost(hostID)
        if host == None:
            raise koji.GenericError, 'invalid host ID: %s' % hostID
    elif userID:
        userID = int(userID)
        hosts = server.listHosts(userID=userID)
        host = None
        if hosts:
            host = hosts[0]
        if host == None:
            raise koji.GenericError, 'invalid host ID: %s' % userID
    else:
        raise koji.GenericError, 'hostID or userID must be provided'

    values['title'] = host['name'] + ' | Host Info'

    channels = server.listChannels(host['id'])
    channels.sort(_sortbyname)
    buildroots = server.listBuildroots(hostID=host['id'],
                                       state=[state[1] for state in koji.BR_STATES.items() if state[0] != 'EXPIRED'])
    buildroots.sort(kojiweb.util.sortByKeyFunc('-create_event_time'))

    values['host'] = host
    values['channels'] = channels
    values['buildroots'] = buildroots
    values['lastUpdate'] = server.getLastHostUpdate(host['id'])
    if req.currentUser:
        values['perms'] = server.getUserPerms(req.currentUser['id'])
    else:
        values['perms'] = []
    
    return _genHTML(req, 'hostinfo.chtml')

def hostedit(req, hostID):
    server = _getServer(req)
    _assertLogin(req)

    hostID = int(hostID)
    host = server.getHost(hostID)
    if host == None:
        raise koji.GenericError, 'no host with ID: %i' % hostID

    form = req.form

    if form.has_key('save'):
        arches = form['arches'].value
        capacity = float(form['capacity'].value)
        description = form['description'].value
        comment = form['comment'].value
        enabled = bool(form.has_key('enabled'))
        channels = [f.value for f in form.getlist('channels')]

        server.editHost(host['id'], arches=arches, capacity=capacity,
                        description=description, comment=comment)
        if enabled != host['enabled']:
            if enabled:
                server.enableHost(host['name'])
            else:
                server.disableHost(host['name'])

        hostChannels = [c['name'] for c in server.listChannels(hostID=host['id'])]
        for channel in hostChannels:
            if channel not in channels:
                server.removeHostFromChannel(host['name'], channel)
        for channel in channels:
            if channel not in hostChannels:
                server.addHostToChannel(host['name'], channel)

        mod_python.util.redirect(req, 'hostinfo?hostID=%i' % host['id'])
    elif form.has_key('cancel'):
        mod_python.util.redirect(req, 'hostinfo?hostID=%i' % host['id'])
    else:
        values = _initValues(req, 'Edit Host', 'hosts')

        values['host'] = host
        allChannels = server.listChannels()
        allChannels.sort(_sortbyname)
        values['allChannels'] = allChannels
        values['hostChannels'] = server.listChannels(hostID=host['id'])

        return _genHTML(req, 'hostedit.chtml')

def disablehost(req, hostID):
    server = _getServer(req)
    _assertLogin(req)

    hostID = int(hostID)
    host = server.getHost(hostID, strict=True)
    server.disableHost(host['name'])

    mod_python.util.redirect(req, 'hostinfo?hostID=%i' % host['id'])

def enablehost(req, hostID):
    server = _getServer(req)
    _assertLogin(req)

    hostID = int(hostID)
    host = server.getHost(hostID, strict=True)
    server.enableHost(host['name'])

    mod_python.util.redirect(req, 'hostinfo?hostID=%i' % host['id'])

def channelinfo(req, channelID):
    values = _initValues(req, 'Channel Info', 'hosts')
    server = _getServer(req)

    channelID = int(channelID)
    channel = server.getChannel(channelID)
    if channel == None:
        raise koji.GenericError, 'invalid channel ID: %i' % channelID

    values['title'] = channel['name'] + ' | Channel Info'

    states = [koji.TASK_STATES[s] for s in ('FREE', 'OPEN', 'ASSIGNED')]
    values['taskCount'] = \
            server.listTasks(opts={'channel_id': channelID, 'state': states},
                             queryOpts={'countOnly': True})

    hosts = server.listHosts(channelID=channelID)
    hosts.sort(_sortbyname)

    values['channel'] = channel
    values['hosts'] = hosts

    return _genHTML(req, 'channelinfo.chtml')

def buildrootinfo(req, buildrootID, builtStart=None, builtOrder=None, componentStart=None, componentOrder=None):
    values = _initValues(req, 'Buildroot Info', 'hosts')
    server = _getServer(req)

    buildrootID = int(buildrootID)
    buildroot = server.getBuildroot(buildrootID)

    values['title'] = '%(tag_name)s-%(id)i-%(repo_id)i' % buildroot + ' | Buildroot Info'

    if buildroot == None:
        raise koji.GenericError, 'unknown buildroot ID: %i' % buildrootID

    task = server.getTaskInfo(buildroot['task_id'], request=True)

    values['buildroot'] = buildroot
    values['task'] = task
    
    return _genHTML(req, 'buildrootinfo.chtml')

def rpmlist(req, type, buildrootID=None, imageID=None, start=None, order='nvr'):
    """
    rpmlist requires a buildrootID OR an imageID to be passed in. From one
    of these values it will paginate a list of rpms included in the
    corresponding object. (buildroot or image)
    """

    values = _initValues(req, 'RPM List', 'hosts')
    server = _getServer(req)

    if buildrootID != None:
        buildrootID = int(buildrootID)
        buildroot = server.getBuildroot(buildrootID)
        values['buildroot'] = buildroot
        if buildroot == None:
            raise koji.GenericError, 'unknown buildroot ID: %i' % buildrootID

        rpms = None
        if type == 'component':
            rpms = kojiweb.util.paginateMethod(server, values, 'listRPMs',
                   kw={'componentBuildrootID': buildroot['id']},
                   start=start, dataName='rpms', prefix='rpm', order=order)
        elif type == 'built':
            rpms = kojiweb.util.paginateMethod(server, values, 'listRPMs',
                   kw={'buildrootID': buildroot['id']},
                   start=start, dataName='rpms', prefix='rpm', order=order)
        else:
            raise koji.GenericError, 'unrecognized type of rpmlist'

    elif imageID != None:
        imageID = int(imageID)
        values['image'] = server.getImageInfo(imageID=imageID)
        # If/When future image types are supported, add elifs here if needed.
        if type == 'image':
            rpms =  kojiweb.util.paginateMethod(server, values, 'listRPMs',
                    kw={'imageID': imageID}, \
                    start=start, dataName='rpms', prefix='rpm', order=order)
        else:
            raise koji.GenericError, 'unrecognized type of image rpmlist'

    else:
        # It is an error if neither buildrootID and imageID are defined.
        raise koji.GenericError, 'Both buildrootID and imageID are None'

    values['type'] = type
    values['order'] = order

    return _genHTML(req, 'rpmlist.chtml')

def archivelist(req, buildrootID, type, start=None, order='filename'):
    values = _initValues(req, 'Archive List', 'hosts')
    server = _getServer(req)

    buildrootID = int(buildrootID)
    buildroot = server.getBuildroot(buildrootID)
    if buildroot == None:
        raise koji.GenericError, 'unknown buildroot ID: %i' % buildrootID

    archives = None
    if type == 'component':
        rpms = kojiweb.util.paginateMethod(server, values, 'listArchives', kw={'componentBuildrootID': buildroot['id']},
                                           start=start, dataName='archives', prefix='archive', order=order)
    elif type == 'built':
        rpms = kojiweb.util.paginateMethod(server, values, 'listArchives', kw={'buildrootID': buildroot['id']},
                                           start=start, dataName='archives', prefix='archive', order=order)
    else:
        raise koji.GenericError, 'invalid type: %s' % type

    values['buildroot'] = buildroot
    values['type'] = type

    values['order'] = order

    return _genHTML(req, 'archivelist.chtml')

def buildtargets(req, start=None, order='name'):
    values = _initValues(req, 'Build Targets', 'buildtargets')
    server = _getServer(req)

    targets = kojiweb.util.paginateMethod(server, values, 'getBuildTargets',
                                          start=start, dataName='targets', prefix='target', order=order)
    
    values['order'] = order
    if req.currentUser:
        values['perms'] = server.getUserPerms(req.currentUser['id'])
    else:
        values['perms'] = []
    
    return _genHTML(req, 'buildtargets.chtml')

def buildtargetinfo(req, targetID=None, name=None):
    values = _initValues(req, 'Build Target Info', 'buildtargets')
    server = _getServer(req)

    target = None
    if targetID != None:
        targetID = int(targetID)
        target = server.getBuildTarget(targetID)
    elif name != None:
        target = server.getBuildTarget(name)
    
    if target == None:
        raise koji.GenericError, 'invalid build target: %s' % (targetID or name)

    values['title'] = target['name'] + ' | Build Target Info'

    buildTag = server.getTag(target['build_tag'])
    destTag = server.getTag(target['dest_tag'])

    values['target'] = target
    values['buildTag'] = buildTag
    values['destTag'] = destTag
    if req.currentUser:
        values['perms'] = server.getUserPerms(req.currentUser['id'])
    else:
        values['perms'] = []

    return _genHTML(req, 'buildtargetinfo.chtml')

def buildtargetedit(req, targetID):
    server = _getServer(req)
    _assertLogin(req)

    targetID = int(targetID)

    target = server.getBuildTarget(targetID)
    if target == None:
        raise koji.GenericError, 'invalid build target: %s' % targetID

    form = req.form

    if form.has_key('save'):
        name = form['name'].value
        buildTagID = int(form['buildTag'])
        buildTag = server.getTag(buildTagID)
        if buildTag == None:
            raise koji.GenericError, 'invalid tag ID: %i' % buildTagID

        destTagID = int(form['destTag'])
        destTag = server.getTag(destTagID)
        if destTag == None:
            raise koji.GenericError, 'invalid tag ID: %i' % destTagID

        server.editBuildTarget(target['id'], name, buildTag['id'], destTag['id'])

        mod_python.util.redirect(req, 'buildtargetinfo?targetID=%i' % target['id'])
    elif form.has_key('cancel'):
        mod_python.util.redirect(req, 'buildtargetinfo?targetID=%i' % target['id'])
    else:
        values = _initValues(req, 'Edit Build Target', 'buildtargets')
        tags = server.listTags()
        tags.sort(_sortbyname)
        
        values['target'] = target
        values['tags'] = tags

        return _genHTML(req, 'buildtargetedit.chtml')

def buildtargetcreate(req):
    server = _getServer(req)
    _assertLogin(req)

    form = req.form

    if form.has_key('add'):
        # Use the str .value field of the StringField object,
        # since xmlrpclib doesn't know how to marshal the StringFields
        # returned by mod_python
        name = form['name'].value
        buildTagID = int(form['buildTag'])
        destTagID = int(form['destTag'])

        server.createBuildTarget(name, buildTagID, destTagID)
        target = server.getBuildTarget(name)

        if target == None:
            raise koji.GenericError, 'error creating build target "%s"' % name
        
        mod_python.util.redirect(req, 'buildtargetinfo?targetID=%i' % target['id'])
    elif form.has_key('cancel'):
        mod_python.util.redirect(req, 'buildtargets')
    else:
        values = _initValues(req, 'Add Build Target', 'builtargets')

        tags = server.listTags()
        tags.sort(_sortbyname)

        values['target'] = None
        values['tags'] = tags

        return _genHTML(req, 'buildtargetedit.chtml')

def buildtargetdelete(req, targetID):
    server = _getServer(req)
    _assertLogin(req)

    targetID = int(targetID)

    target = server.getBuildTarget(targetID)
    if target == None:
        raise koji.GenericError, 'invalid build target: %i' % targetID

    server.deleteBuildTarget(target['id'])

    mod_python.util.redirect(req, 'buildtargets')

def reports(req):
    server = _getServer(req)
    values = _initValues(req, 'Reports', 'reports')
    return _genHTML(req, 'reports.chtml')

def buildsbyuser(req, start=None, order='-builds'):
    values = _initValues(req, 'Builds by User', 'reports')
    server = _getServer(req)

    maxBuilds = 1
    users = server.listUsers()

    server.multicall = True
    for user in users:
        server.listBuilds(userID=user['id'], queryOpts={'countOnly': True})
    buildCounts = server.multiCall()

    for user, [numBuilds] in zip(users, buildCounts):
        user['builds'] = numBuilds
        if numBuilds > maxBuilds:
            maxBuilds = numBuilds
    
    values['order'] = order

    graphWidth = 400.0
    values['graphWidth'] = graphWidth
    values['maxBuilds'] = maxBuilds
    values['increment'] = graphWidth / maxBuilds
    kojiweb.util.paginateList(values, users, start, 'userBuilds', 'userBuild', order)

    return _genHTML(req, 'buildsbyuser.chtml')

def rpmsbyhost(req, start=None, order=None, hostArch=None, rpmArch=None):
    values = _initValues(req, 'RPMs by Host', 'reports')
    server = _getServer(req)

    maxRPMs = 1
    hostArchFilter = hostArch
    if hostArchFilter == 'ix86':
        hostArchFilter = ['i386', 'i486', 'i586', 'i686']
    hosts = server.listHosts(arches=hostArchFilter)
    rpmArchFilter = rpmArch
    if rpmArchFilter == 'ix86':
        rpmArchFilter = ['i386', 'i486', 'i586', 'i686']

    server.multicall = True
    for host in hosts:
        server.listRPMs(hostID=host['id'], arches=rpmArchFilter, queryOpts={'countOnly': True})
    rpmCounts = server.multiCall()

    for host, [numRPMs] in zip(hosts, rpmCounts):
        host['rpms'] = numRPMs
        if numRPMs > maxRPMs:
            maxRPMs = numRPMs
    
    values['hostArch'] = hostArch
    hostArchList = server.getAllArches()
    hostArchList.sort()
    values['hostArchList'] = hostArchList
    values['rpmArch'] = rpmArch
    values['rpmArchList'] = hostArchList + ['noarch', 'src']
    
    if order == None:
        order = '-rpms'
    values['order'] = order

    graphWidth = 400.0
    values['graphWidth'] = graphWidth
    values['maxRPMs'] = maxRPMs
    values['increment'] = graphWidth / maxRPMs
    kojiweb.util.paginateList(values, hosts, start, 'hosts', 'host', order)

    return _genHTML(req, 'rpmsbyhost.chtml')

def packagesbyuser(req, start=None, order=None):
    values = _initValues(req, 'Packages by User', 'reports')
    server = _getServer(req)

    maxPackages = 1
    users = server.listUsers()

    server.multicall = True
    for user in users:
        server.count('listPackages', userID=user['id'], with_dups=True)
    packageCounts = server.multiCall()

    for user, [numPackages] in zip(users, packageCounts):
        user['packages'] = numPackages
        if numPackages > maxPackages:
            maxPackages = numPackages

    if order == None:
        order = '-packages'
    values['order'] = order

    graphWidth = 400.0
    values['graphWidth'] = graphWidth
    values['maxPackages'] = maxPackages
    values['increment'] = graphWidth / maxPackages
    kojiweb.util.paginateList(values, users, start, 'users', 'user', order)

    return _genHTML(req, 'packagesbyuser.chtml')

def tasksbyhost(req, start=None, order='-tasks', hostArch=None):
    values = _initValues(req, 'Tasks by Host', 'reports')
    server = _getServer(req)

    maxTasks = 1
    
    hostArchFilter = hostArch
    if hostArchFilter == 'ix86':
        hostArchFilter = ['i386', 'i486', 'i586', 'i686']
    
    hosts = server.listHosts(arches=hostArchFilter)

    server.multicall = True
    for host in hosts:
        server.listTasks(opts={'host_id': host['id']}, queryOpts={'countOnly': True})
    taskCounts = server.multiCall()

    for host, [numTasks] in zip(hosts, taskCounts):
        host['tasks'] = numTasks
        if numTasks > maxTasks:
            maxTasks = numTasks
    
    values['hostArch'] = hostArch
    hostArchList = server.getAllArches()
    hostArchList.sort()
    values['hostArchList'] = hostArchList
    
    values['order'] = order

    graphWidth = 400.0
    values['graphWidth'] = graphWidth
    values['maxTasks'] = maxTasks
    values['increment'] = graphWidth / maxTasks
    kojiweb.util.paginateList(values, hosts, start, 'hosts', 'host', order)

    return _genHTML(req, 'tasksbyhost.chtml')

def tasksbyuser(req, start=None, order='-tasks'):
    values = _initValues(req, 'Tasks by User', 'reports')
    server = _getServer(req)

    maxTasks = 1
    
    users = server.listUsers()

    server.multicall = True
    for user in users:
        server.listTasks(opts={'owner': user['id']}, queryOpts={'countOnly': True})
    taskCounts = server.multiCall()

    for user, [numTasks] in zip(users, taskCounts):
        user['tasks'] = numTasks
        if numTasks > maxTasks:
            maxTasks = numTasks
        
    values['order'] = order

    graphWidth = 400.0
    values['graphWidth'] = graphWidth
    values['maxTasks'] = maxTasks
    values['increment'] = graphWidth / maxTasks
    kojiweb.util.paginateList(values, users, start, 'users', 'user', order)

    return _genHTML(req, 'tasksbyuser.chtml')

def buildsbystatus(req, days='7'):
    values = _initValues(req, 'Builds by Status', 'reports')
    server = _getServer(req)

    days = int(days)
    if days != -1:
        seconds = 60 * 60 * 24 * days
        dateAfter = time.time() - seconds
    else:
        dateAfter = None
    values['days'] = days

    server.multicall = True
    # use taskID=-1 to filter out builds with a null task_id (imported rather than built in koji)
    server.listBuilds(completeAfter=dateAfter, state=koji.BUILD_STATES['COMPLETE'], taskID=-1, queryOpts={'countOnly': True})
    server.listBuilds(completeAfter=dateAfter, state=koji.BUILD_STATES['FAILED'], taskID=-1, queryOpts={'countOnly': True})
    server.listBuilds(completeAfter=dateAfter, state=koji.BUILD_STATES['CANCELED'], taskID=-1, queryOpts={'countOnly': True})
    [[numSucceeded], [numFailed], [numCanceled]] = server.multiCall()
    
    values['numSucceeded'] = numSucceeded
    values['numFailed'] = numFailed
    values['numCanceled'] = numCanceled

    maxBuilds = 1
    for value in (numSucceeded, numFailed, numCanceled):
        if value > maxBuilds:
            maxBuilds = value

    graphWidth = 400.0
    values['graphWidth'] = graphWidth
    values['maxBuilds'] = maxBuilds
    values['increment'] = graphWidth / maxBuilds

    return _genHTML(req, 'buildsbystatus.chtml')

def buildsbytarget(req, days='7', start=None, order='-builds'):
    values = _initValues(req, 'Builds by Target', 'reports')
    server = _getServer(req)

    days = int(days)
    if days != -1:
        seconds = 60 * 60 * 24 * days
        dateAfter = time.time() - seconds
    else:
        dateAfter = None
    values['days'] = days

    targets = {}
    maxBuilds = 1

    tasks = server.listTasks(opts={'method': 'build', 'completeAfter': dateAfter, 'decode': True})

    for task in tasks:
        targetName = task['request'][1]
        target = targets.get(targetName)
        if not target:
            target = {'name': targetName}
            targets[targetName] = target
        builds = target.get('builds', 0) + 1
        target['builds'] = builds
        if builds > maxBuilds:
            maxBuilds = builds

    kojiweb.util.paginateList(values, targets.values(), start, 'targets', 'target', order)    

    values['order'] = order

    graphWidth = 400.0
    values['graphWidth'] = graphWidth
    values['maxBuilds'] = maxBuilds
    values['increment'] = graphWidth / maxBuilds

    return _genHTML(req, 'buildsbytarget.chtml')
    
def recentbuilds(req, user=None, tag=None, package=None):
    values = _initValues(req, 'Recent Build RSS')
    server = _getServer(req)

    tagObj = None
    if tag != None:
        if tag.isdigit():
            tag = int(tag)
        tagObj = server.getTag(tag)

    userObj = None
    if user != None:
        if user.isdigit():
            user = int(user)
        userObj = server.getUser(user)

    packageObj = None
    if package:
        if package.isdigit():
            package = int(package)
        packageObj = server.getPackage(package)

    if tagObj != None:
        builds = server.listTagged(tagObj['id'], inherit=True, package=(packageObj and packageObj['name'] or None),
                                   owner=(userObj and userObj['name'] or None))
        builds.sort(kojiweb.util.sortByKeyFunc('-completion_time', noneGreatest=True))
        builds = builds[:20]
    else:
        kwargs = {}
        if userObj:
            kwargs['userID'] = userObj['id']
        if packageObj:
            kwargs['packageID'] = packageObj['id']
        builds = server.listBuilds(queryOpts={'order': '-completion_time', 'limit': 20}, **kwargs)

    server.multicall = True
    for build in builds:
        if build['task_id']:
            server.getTaskInfo(build['task_id'], request=True)
        else:
            server.echo(None)
    tasks = server.multiCall()

    server.multicall = True
    queryOpts = {'limit': 3}
    for build in builds:
        if build['state'] == koji.BUILD_STATES['COMPLETE']:
            server.getChangelogEntries(build['build_id'], queryOpts=queryOpts)
        else:
            server.echo(None)
    clogs = server.multiCall()

    for i in range(len(builds)):
        task = tasks[i][0]
        if isinstance(task, list):
            # this is the output of server.echo(None) above
            task = None
        builds[i]['task'] = task
        builds[i]['changelog'] = clogs[i][0]
    
    values['tag'] = tagObj
    values['user'] = userObj
    values['package'] = packageObj
    values['builds'] = builds
    values['weburl'] = _getBaseURL(req)

    req.content_type = 'text/xml'
    return _genHTML(req, 'recentbuilds.chtml')

_infoURLs = {'package': 'packageinfo?packageID=%(id)i',
             'build': 'buildinfo?buildID=%(id)i',
             'tag': 'taginfo?tagID=%(id)i',
             'target': 'buildtargetinfo?targetID=%(id)i',
             'user': 'userinfo?userID=%(id)i',
             'host': 'hostinfo?hostID=%(id)i',
             'rpm': 'rpminfo?rpmID=%(id)i',
             'maven': 'archiveinfo?archiveID=%(id)i',
             'win': 'archiveinfo?archiveID=%(id)i'}

_VALID_SEARCH_CHARS = r"""a-zA-Z0-9"""
_VALID_SEARCH_SYMS = r""" @.,_/\()%+-*?|[]^$"""
_VALID_SEARCH_RE = re.compile('^[' + _VALID_SEARCH_CHARS + re.escape(_VALID_SEARCH_SYMS) + ']+$')

def search(req, start=None, order='name'):
    values = _initValues(req, 'Search', 'search')
    server = _getServer(req)
    values['error'] = None

    form = req.form
    if form.has_key('terms') and form['terms']:
        terms = form['terms'].value
        type = form['type'].value
        match = form['match'].value
        values['terms'] = terms
        values['type'] = type
        values['match'] = match

        if not _VALID_SEARCH_RE.match(terms):
            values['error'] = 'Invalid search terms<br/>' + \
                'Search terms may contain only these characters: ' + \
                _VALID_SEARCH_CHARS + _VALID_SEARCH_SYMS
            return _genHTML(req, 'search.chtml')

        if match == 'regexp':
            try:
                re.compile(terms)
            except:
                values['error'] = 'Invalid regular expression'
                return _genHTML(req, 'search.chtml')

        infoURL = _infoURLs.get(type)
        if not infoURL:
            raise koji.GenericError, 'unknown search type: %s' % type
        values['infoURL'] = infoURL
        values['order'] = order
        
        results = kojiweb.util.paginateMethod(server, values, 'search', args=(terms, type, match),
                                              start=start, dataName='results', prefix='result', order=order)
        if not start and len(results) == 1:
            # if we found exactly one result, skip the result list and redirect to the info page
            # (you're feeling lucky)
            mod_python.util.redirect(req, infoURL % results[0])
        else:
            if type == 'maven':
                typeLabel = 'Maven artifacts'
            elif type == 'win':
                typeLabel = 'Windows artifacts'
            else:
                typeLabel = '%ss' % type
            values['typeLabel'] = typeLabel
            return _genHTML(req, 'searchresults.chtml')
    else:
        return _genHTML(req, 'search.chtml')

def watchlogs(req, taskID):
    values = _initValues(req)
    if isinstance(taskID, list):
        values['tasks'] = ', '.join(taskID)
    else:
        values['tasks'] = taskID

    html = """
<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Strict//EN"
          "http://www.w3.org/TR/xhtml1/DTD/xhtml1-strict.dtd">
<html>
  <head>
    <script type="text/javascript" src="/koji-static/js/watchlogs.js"></script>
    <title>Logs for task %(tasks)s | %(siteName)s</title>
  </head>
  <body onload="watchLogs('logs')">
    <pre id="logs">
<span>Loading logs for task %(tasks)s...</span>
    </pre>
  </body>
</html>
""" % values
    return html
