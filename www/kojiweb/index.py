import os
import os.path
import re
import sys
import mod_python
import mod_python.Cookie
import Cheetah.Template
import datetime
import time
import koji
import kojiweb.util

# Convenience definition of a commonly-used sort function
_sortbyname = kojiweb.util.sortByKeyFunc('name')

def _setUserCookie(req, user):
    options = req.get_options()
    cookie = mod_python.Cookie.SignedCookie('user', user,
                                            secret=options['Secret'],
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
        return cookies['user'].value
    else:
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
    else:
        mod_python.util.redirect(req, 'login')
        assert False

def _initValues(req, title='Build System Info', pageID='summary'):
    values = {}
    values['title'] = title
    values['pageID'] = pageID
    values['currentDate'] = str(datetime.datetime.now())
    
    req._values = values

    return values

def _genHTML(req, fileName):
    os.chdir(os.path.dirname(req.filename))

    if hasattr(req, 'currentUser'):
        req._values['currentUser'] = req.currentUser
    else:
        req._values['currentUser'] = None
        
    return Cheetah.Template.Template(file=fileName, searchList=[req._values], filter='EncodeUnicode').respond()

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

def _redirectBack(req, page):
    if page:
        mod_python.util.redirect(req, page)
    elif req.headers_in.get('Referer'):
        mod_python.util.redirect(req, req.headers_in.get('Referer'))
    else:
        mod_python.util.redirect(req, 'index')    

def login(req, page=None):
    session = _getServer(req)
    options = req.get_options()

    # try SSL first, fall back to Kerberos
    if options.get('WebCert'):
        req.add_common_vars()
        env = req.subprocess_env
        if not env.get('HTTPS') == 'on':
            https_url = options['KojiWebURL'].replace('http://', 'https://') + '/login'
            if req.args:
                https_url += '?' + req.args
            mod_python.util.redirect(req, https_url)
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

    _redirectBack(req, page)

def logout(req, page=None):
    _clearUserCookie(req)

    _redirectBack(req, page)

def index(req, packageOrder='package_name', packageStart=None, buildOrder='-completion_time', buildStart=None, taskOrder='-completion_time', taskStart=None):
    values = _initValues(req)
    server = _getServer(req)

    user = req.currentUser

    builds = kojiweb.util.paginateMethod(server, values, 'listBuilds', kw={'userID': (user and user['id'] or None)},
                                         start=buildStart, dataName='builds', prefix='build', order=buildOrder, pageSize=10)

    taskOpts = {'parent': None, 'decode': True}
    if user:
        taskOpts['owner'] = user['id']
    tasks = kojiweb.util.paginateMethod(server, values, 'listTasks', kw={'opts': taskOpts},
                                        start=taskStart, dataName='tasks', prefix='task', order=taskOrder, pageSize=10)

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

def tasks(req, owner=None, state='active', method='all', hostID=None, start=None, order='-completion_time'):
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

    if state in ('active', 'toplevel') and method == 'all' and not hostID:
        # If we're only showing active or toplevel tasks, and not filtering by host or method, only query the top-level tasks as well,
        # and then retrieve the task children so we can do the nice tree display.
        treeDisplay = True
    else:
        treeDisplay = False
    values['treeDisplay'] = treeDisplay

    if method != 'all':
        opts['method'] = method
    values['method'] = method
    
    if state == 'active':
        opts['state'] = [koji.TASK_STATES['FREE'], koji.TASK_STATES['OPEN'], koji.TASK_STATES['ASSIGNED']]
        if treeDisplay:
            opts['parent'] = None
    elif state == 'toplevel':
        # Show all top-level tasks, no tree display
        opts['parent'] = None
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

    loggedInUser = req.currentUser
    values['loggedInUser'] = loggedInUser

    values['order'] = order

    tasks = kojiweb.util.paginateMethod(server, values, 'listTasks', kw={'opts': opts},
                                        start=start, dataName='tasks', prefix='task', order=order)
    
    if treeDisplay:
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
        values['taskBuild'] = builds[0]
    else:
        values['taskBuild'] = None

    buildroots = server.listBuildroots(taskID=task['id'])
    values['buildroots'] = buildroots

    if task['method'] == 'buildArch':
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

def getfile(req, taskID, name):
    server = _getServer(req)
    taskID = int(taskID)

    output = server.listTaskOutput(taskID, stat=True)
    file_info = output.get(name)
    if not file_info:
        raise koji.GenericError, 'no file "%s" output by task %i' % (name, taskID)
    
    if name.endswith('.rpm'):
        req.content_type = 'application/x-rpm'
        req.headers_out['Content-Disposition'] = 'attachment; filename=%s' % name
    elif name.endswith('.log'):
        req.content_type = 'text/plain'
    req.set_content_length(file_info['st_size'])

    offset = 0
    while True:
        content = server.downloadTaskOutput(taskID, name, offset=offset, size=65536)
        if not content:
            break
        req.write(content)
        offset += len(content)

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

def packages(req, tagID=None, userID=None, order='package_name', start=None, prefix=None, inherited='1'):
    values = _initValues(req, 'Packages', 'packages')
    server = _getServer(req)
    tag = None
    if tagID != None:
        tagID = int(tagID)
        tag = server.getTag(tagID)
    values['tagID'] = tagID
    values['tag'] = tag
    user = None
    if userID != None:
        userID = int(userID)
        user = server.getUser(userID)
    values['userID'] = userID
    values['user'] = user
    values['order'] = order
    if prefix:
        prefix = prefix.lower()
    values['prefix'] = prefix
    inherited = int(inherited)
    values['inherited'] = inherited
    
    packages = kojiweb.util.paginateResults(server, values, 'listPackages',
                                            kw={'tagID': tagID, 'userID': userID, 'prefix': prefix, 'inherited': bool(inherited)},
                                            start=start, dataName='packages', prefix='package', order=order)
    
    values['chars'] = [chr(char) for char in range(48, 58) + range(97, 123)]
    
    return _genHTML(req, 'packages.chtml')

def packageinfo(req, packageID, tagOrder='name', tagStart=None, buildOrder='-completion_time', buildStart=None):
    values = _initValues(req, 'Package Info', 'packages')
    server = _getServer(req)

    if packageID.isdigit():
        packageID = int(packageID)
    package = server.getPackage(packageID)
    if package == None:
        raise koji.GenericError, 'invalid package ID: %s' % packageID
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

    form = req.form

    if form.has_key('add'):
        name = form['name'].value
        arches = form['arches'].value
        if form.has_key('locked'):
            locked = True
        else:
            locked = False
        permission = form['permission'].value
        if permission == 'none':
            permission = None
        else:
            permission = int(permission)

        server.createTag(name)
        tag = server.getTag(name)
        
        if tag == None:
            raise koji.GenericError, 'error creating tag "%s"' % name

        server.editTag(tag['id'], name, arches, locked, permission)
        
        mod_python.util.redirect(req, 'taginfo?tagID=%i' % tag['id'])
    elif form.has_key('cancel'):
        mod_python.util.redirect(req, 'tags')
    else:
        values = _initValues(req, 'Add Tag', 'tags')

        values['tag'] = None
        values['permissions'] = server.getAllPerms()

        return _genHTML(req, 'tagedit.chtml')

def tagedit(req, tagID):
    server = _getServer(req)
    _assertLogin(req)

    tagID = int(tagID)
    tag = server.getTag(tagID)
    if tag == None:
        raise koji.GenericError, 'no tag with ID: %i' % tagID

    form = req.form

    if form.has_key('save'):
        name = form['name'].value
        arches = form['arches'].value
        locked = bool(form.has_key('locked'))
        permission = form['permission'].value
        if permission == 'none':
            permission = None
        else:
            permission = int(permission)

        server.editTag(tag['id'], name, arches, locked, permission)
        
        mod_python.util.redirect(req, 'taginfo?tagID=%i' % tag['id'])
    elif form.has_key('cancel'):
        mod_python.util.redirect(req, 'taginfo?tagID=%i' % tag['id'])
    else:
        values = _initValues(req, 'Edit Tag', 'tags')

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

def buildinfo(req, buildID):
    values = _initValues(req, 'Build Info', 'builds')
    server = _getServer(req)

    buildID = int(buildID)
    
    build = server.getBuild(buildID)
    tags = server.listTags(build['id'])
    tags.sort(_sortbyname)
    rpms = server.listBuildRPMs(build['id'])
    rpms.sort(_sortbyname)

    if build['task_id']:
        task = server.getTaskInfo(build['task_id'], request=True)
    else:
        task = None

    values['build'] = build
    values['tags'] = tags
    values['rpms'] = rpms
    values['task'] = task
    if req.currentUser:
        values['perms'] = server.getUserPerms(req.currentUser['id'])
    else:
        values['perms'] = []
    values['changelog'] = server.getChangelogEntries(build['id'])
    if build['state'] == koji.BUILD_STATES['BUILDING']:
        avgDuration = server.getAverageBuildDuration(build['package_id'])
        if avgDuration != None:
            avgDelta = datetime.timedelta(seconds=avgDuration)
            startTime = datetime.datetime.fromtimestamp(
                time.mktime(time.strptime(koji.formatTime(build['creation_time']), '%Y-%m-%d %H:%M:%S'))
                )
            values['estCompletion'] = startTime + avgDelta
        else:
            values['estCompletion'] = None

    values['downloadBase'] = req.get_options().get('KojiPackagesURL', 'http://localhost/packages')

    return _genHTML(req, 'buildinfo.chtml')

def builds(req, userID=None, tagID=None, state=None, order='-completion_time', start=None, prefix=None, inherited='1'):
    values = _initValues(req, 'Builds', 'builds')
    server = _getServer(req)

    user = None
    if userID != None:
        if userID.isdigit():
            userID = int(userID)
        user = server.getUser(userID, strict=True)
    values['userID'] = userID
    values['user'] = user

    tag = None
    if tagID != None:
        if tagID.isdigit():
            tagID = int(tagID)
        tag = server.getTag(tagID, strict=True)
    values['tagID'] = tagID
    values['tag'] = tag

    if state == 'all':
        state = None
    elif state != None:
        state = int(state)
    values['state'] = state

    if prefix:
        prefix = prefix.lower()
    values['prefix'] = prefix
    
    values['order'] = order
    inherited = int(inherited)
    values['inherited'] = inherited

    if tag:
        # don't need to consider 'state' here, since only completed builds would be tagged
        builds = kojiweb.util.paginateResults(server, values, 'listTagged', kw={'tag': tag['id'], 'inherit': bool(inherited), 'prefix': prefix},
                                              start=start, dataName='builds', prefix='build', order=order)
    else:
        builds = kojiweb.util.paginateMethod(server, values, 'listBuilds', kw={'userID': (user and user['id'] or None), 'state': state, 'prefix': prefix},
                                             start=start, dataName='builds', prefix='build', order=order)
    
    values['chars'] = [chr(char) for char in range(48, 58) + range(97, 123)]

    return _genHTML(req, 'builds.chtml')

def users(req, order='name', start=None, prefix=None):
    values = _initValues(req, 'Users', 'users')
    server = _getServer(req)

    if prefix:
        prefix = prefix.lower()
    values['prefix'] = prefix

    values['order'] = order

    users = kojiweb.util.paginateMethod(server, values, 'listUsers', kw={'prefix': prefix},
                                        start=start, dataName='users', prefix='user', order=order)

    values['chars'] = [chr(char) for char in range(48, 58) + range(97, 123)]
    
    return _genHTML(req, 'users.chtml')

def userinfo(req, userID, packageOrder='package_name', packageStart=None, buildOrder='-completion_time', buildStart=None):
    values = _initValues(req, 'User Info', 'users')
    server = _getServer(req)

    if userID.isdigit():
        userID = int(userID)
    user = server.getUser(userID, strict=True)
    
    values['user'] = user
    values['userID'] = userID
    
    packages = kojiweb.util.paginateResults(server, values, 'listPackages', kw={'userID': user['id'], 'with_dups': True},
                                            start=packageStart, dataName='packages', prefix='package', order=packageOrder, pageSize=10)
    
    builds = kojiweb.util.paginateMethod(server, values, 'listBuilds', kw={'userID': user['id']},
                                         start=buildStart, dataName='builds', prefix='build', order=buildOrder, pageSize=10)
    
    return _genHTML(req, 'userinfo.chtml')

def rpminfo(req, rpmID, fileOrder='name', fileStart=None):
    values = _initValues(req, 'RPM Info', 'builds')
    server = _getServer(req)

    rpmID = int(rpmID)
    rpm = server.getRPM(rpmID)
    build = server.getBuild(rpm['build_id'])
    builtInRoot = None
    if rpm['buildroot_id'] != None:
        builtInRoot = server.getBuildroot(rpm['buildroot_id'])
    requires = server.getRPMDeps(rpm['id'], koji.DEP_REQUIRE)
    requires.sort(_sortbyname)
    provides = server.getRPMDeps(rpm['id'], koji.DEP_PROVIDE)
    provides.sort(_sortbyname)
    obsoletes = server.getRPMDeps(rpm['id'], koji.DEP_OBSOLETE)
    obsoletes.sort(_sortbyname)
    conflicts = server.getRPMDeps(rpm['id'], koji.DEP_CONFLICT)
    conflicts.sort(_sortbyname)
    buildroots = server.listBuildroots(rpmID=rpm['id'])
    buildroots.sort(kojiweb.util.sortByKeyFunc('-create_event_time'))

    values['rpmID'] = rpmID
    values['rpm'] = rpm
    values['build'] = build
    values['builtInRoot'] = builtInRoot
    values['requires'] = requires
    values['provides'] = provides
    values['obsoletes'] = obsoletes
    values['conflicts'] = conflicts
    values['buildroots'] = buildroots
    
    files = kojiweb.util.paginateMethod(server, values, 'listRPMFiles', args=[rpm['id']],
                                        start=fileStart, dataName='files', prefix='file', order=fileOrder)

    return _genHTML(req, 'rpminfo.chtml')

def fileinfo(req, rpmID, filename):
    values = _initValues(req, 'File Info', 'builds')
    server = _getServer(req)

    rpmID = int(rpmID)
    rpm = server.getRPM(rpmID)
    if not rpm:
        raise koji.GenericError, 'invalid RPM ID: %i' % rpmID
    file = server.getRPMFile(rpmID, filename)
    if not file:
        raise koji.GenericError, 'no file %s in RPM %i' % (filename, rpmID)

    values['rpm'] = rpm
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

def hosts(req, start=None, order='name'):
    values = _initValues(req, 'Hosts', 'hosts')
    server = _getServer(req)

    values['order'] = order

    hosts = server.listHosts()
    
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
    if buildroot == None:
        raise koji.GenericError, 'unknown buildroot ID: %i' % buildrootID

    task = server.getTaskInfo(buildroot['task_id'], request=True)

    values['buildroot'] = buildroot
    values['task'] = task
    
    return _genHTML(req, 'buildrootinfo.chtml')

def rpmlist(req, buildrootID, type, start=None, order='nvr'):
    values = _initValues(req, 'RPM List', 'hosts')
    server = _getServer(req)

    buildrootID = int(buildrootID)
    buildroot = server.getBuildroot(buildrootID)
    if buildroot == None:
        raise koji.GenericError, 'unknown buildroot ID: %i' % buildrootID

    rpms = None
    if type == 'component':
        rpms = kojiweb.util.paginateMethod(server, values, 'listRPMs', kw={'componentBuildrootID': buildroot['id']},
                                           start=start, dataName='rpms', prefix='rpm', order=order)
    elif type == 'built':
        rpms = kojiweb.util.paginateMethod(server, values, 'listRPMs', kw={'buildrootID': buildroot['id']},
                                           start=start, dataName='rpms', prefix='rpm', order=order)

    values['buildroot'] = buildroot
    values['type'] = type

    values['order'] = order

    return _genHTML(req, 'rpmlist.chtml')

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
    
def recentbuilds(req, user=None, tag=None, userID=None, tagID=None):
    values = _initValues(req, 'Recent Build RSS')
    server = _getServer(req)
    
    tagObj = None
    if tag != None:
        tagObj = server.getTag(tag)
    elif tagID != None:
        tagID = int(tagID)
        tagObj = server.getTag(tagID)

    userObj = None
    if user != None:
        userObj = server.getUser(user)
    elif userID != None:
        userID = int(userID)
        userObj = server.getUser(userID)

    if tagObj != None:
        builds = server.listTagged(tagObj['id'], inherit=True)
        builds.sort(kojiweb.util.sortByKeyFunc('-completion_time', noneGreatest=True))
        builds = builds[:20]
    elif userObj != None:
        builds = server.listBuilds(userID=userObj['id'], queryOpts={'order': '-completion_time',
                                                                    'limit': 20})
    else:
        builds = server.listBuilds(queryOpts={'order': '-completion_time', 'limit': 20})

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
    values['builds'] = builds
    values['weburl'] = req.get_options().get('KojiWebURL', 'http://localhost/koji')

    req.content_type = 'text/xml'
    return _genHTML(req, 'recentbuilds.chtml')

_infoURLs = {'package': 'packageinfo?packageID=%(id)i',
             'build': 'buildinfo?buildID=%(id)i',
             'tag': 'taginfo?tagID=%(id)i',
             'target': 'buildtargetinfo?targetID=%(id)i',
             'user': 'userinfo?userID=%(id)i',
             'host': 'hostinfo?hostID=%(id)i',
             'rpm': 'rpminfo?rpmID=%(id)i',
             'file': 'fileinfo?rpmID=%(id)i&filename=%(name)s'}
             
def search(req, start=None, order='name'):
    values = _initValues(req, 'Search', 'search')
    server = _getServer(req)

    form = req.form
    if form.has_key('terms') and form['terms']:
        terms = form['terms'].value
        type = form['type'].value
        match = form['match'].value
        values['terms'] = terms
        values['type'] = type
        values['match'] = match

        if match == 'regexp':
            try:
                re.compile(terms)
            except:
                raise koji.GenericError, 'invalid regular expression: %s' % terms
        
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
            return _genHTML(req, 'searchresults.chtml')
    else:
        return _genHTML(req, 'search.chtml')

def watchlogs(req, taskID):
    html = """
<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Strict//EN"
          "http://www.w3.org/TR/xhtml1/DTD/xhtml1-strict.dtd">
<html>
  <head>
    <script type="text/javascript" src="/koji-static/js/jsolait/init.js"></script>
    <script type="text/javascript" src="/koji-static/js/watchlogs.js"></script>
    <title>Logs for task %i | Koji</title>
  </head>
  <body onload="main()">
    <pre id="logs">
Loading logs...
    </pre>
  </body>
</html>
""" % int(taskID)
    return html
