# core web interface handlers for koji
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
import http.cookies
import logging
import mimetypes
import os
import os.path
import re
import sys
import time
import itertools

import koji
from koji.tasks import parse_task_params
import kojiweb.util
from koji.server import ServerRedirect
from kojiweb.util import _genHTML, _getValidTokens, _initValues, formatRPM, SafeValue
from koji.util import extract_build_task


# Convenience definition of a commonly-used sort function
def _sortbyname(x):
    return x['name']


_VALID_ARCH_RE = re.compile(r'^[\w-]+$', re.ASCII)


def _validate_arch(arch):
    # archs (ASCII alnum + _ + -)
    if not arch:
        return None
    elif _VALID_ARCH_RE.match(arch):
        return arch
    else:
        raise koji.GenericError("No such arch: %r" % arch)


def _convert_if_int(value):
    # if value is digit, converts value to integer, otherwise it returns raw value
    if value.isdigit():
        return int(value)
    else:
        return value


# loggers
authlogger = logging.getLogger('koji.auth')


def _setUserCookie(environ, user):
    options = environ['koji.options']
    # include the current time in the cookie so we can verify that
    # someone is not using an expired cookie
    value = user + ':' + str(int(time.time()))
    if not options['Secret'].value:
        raise koji.AuthError('Unable to authenticate, server secret not configured')
    digest_string = value + options['Secret'].value
    digest_string = digest_string.encode('utf-8')
    shasum = hashlib.sha256(digest_string)
    value = "%s:%s" % (shasum.hexdigest(), value)
    cookies = http.cookies.SimpleCookie()
    cookies['user'] = value
    c = cookies['user']  # morsel instance
    c['secure'] = True
    c['path'] = os.path.dirname(environ['SCRIPT_NAME'])
    # the Cookie module treats integer expire times as relative seconds
    c['expires'] = int(options['LoginTimeout']) * 60 * 60
    out = c.OutputString()
    out += '; HttpOnly; SameSite=Strict'
    environ['koji.headers'].append(['Set-Cookie', out])
    environ['koji.headers'].append(['Cache-Control', 'no-cache="Set-Cookie, Set-Cookie2"'])


def _clearUserCookie(environ):
    cookies = http.cookies.SimpleCookie()
    cookies['user'] = ''
    c = cookies['user']  # morsel instance
    c['path'] = os.path.dirname(environ['SCRIPT_NAME'])
    c['expires'] = 0
    out = c.OutputString()
    environ['koji.headers'].append(['Set-Cookie', out])


def _getUserCookie(environ):
    options = environ['koji.options']
    cookies = http.cookies.SimpleCookie(environ.get('HTTP_COOKIE', ''))
    if 'user' not in cookies:
        return None
    value = cookies['user'].value
    parts = value.split(":", 1)
    if len(parts) != 2:
        authlogger.warning('malformed user cookie: %s' % value)
        return None
    sig, value = parts
    if not options['Secret'].value:
        raise koji.AuthError('Unable to authenticate, server secret not configured')
    digest_string = value + options['Secret'].value
    digest_string = digest_string.encode('utf-8')
    shasum = hashlib.sha256(digest_string)
    if shasum.hexdigest() != sig:
        authlogger.warning('invalid user cookie: %s:%s', sig, value)
        return None
    parts = value.split(":", 1)
    if len(parts) != 2:
        authlogger.warning('invalid signed user cookie: %s:%s', sig, value)
        # no embedded timestamp
        return None
    user, timestamp = parts
    try:
        timestamp = float(timestamp)
    except ValueError:
        authlogger.warning('invalid time in signed user cookie: %s:%s', sig, value)
        return None
    if (time.time() - timestamp) > (int(options['LoginTimeout']) * 60 * 60):
        authlogger.info('expired user cookie: %s', value)
        return None
    # Otherwise, cookie is valid and current
    return user


def _gssapiLogin(environ, session, principal):
    options = environ['koji.options']
    wprinc = options['WebPrincipal']
    keytab = options['WebKeytab']
    ccache = options['WebCCache']
    authtype = options['WebAuthType']
    return session.gssapi_login(principal=wprinc, keytab=keytab,
                                ccache=ccache, proxyuser=principal, proxyauthtype=authtype)


def _sslLogin(environ, session, username):
    options = environ['koji.options']
    client_cert = options['WebCert']
    server_ca = options['KojiHubCA']
    authtype = options['WebAuthType']
    return session.ssl_login(client_cert, None, server_ca,
                             proxyuser=username, proxyauthtype=authtype)


def _assertLogin(environ):
    session = environ['koji.session']
    options = environ['koji.options']
    if 'koji.currentLogin' not in environ or 'koji.currentUser' not in environ:
        raise Exception('_getServer() must be called before _assertLogin()')
    elif environ['koji.currentLogin'] and environ['koji.currentUser']:
        if options['WebCert']:
            if not _sslLogin(environ, session, environ['koji.currentLogin']):
                raise koji.AuthError('could not login %s via SSL' % environ['koji.currentLogin'])
        elif options['WebPrincipal']:
            if not _gssapiLogin(environ, environ['koji.session'], environ['koji.currentLogin']):
                raise koji.AuthError(
                    'could not login using principal: %s' % environ['koji.currentLogin'])
        else:
            raise koji.AuthError(
                'KojiWeb is incorrectly configured for authentication, '
                'contact the system administrator')

        # verify a valid authToken was passed in to avoid CSRF
        authToken = environ['koji.form'].getfirst('a', '')
        validTokens = _getValidTokens(environ)
        if authToken and authToken in validTokens:
            # we have a token and it's valid
            pass
        else:
            # their authToken is likely expired
            # send them back to the page that brought them here so they
            # can re-click the link with a valid authToken
            _redirectBack(environ, page=None,
                          forceSSL=(_getBaseURL(environ).startswith('https://')))
            assert False  # pragma: no cover
    else:
        _redirect(environ, 'login')
        assert False  # pragma: no cover


def _getServer(environ):
    options = environ['koji.options']
    opts = {}
    if os.path.exists(options['KojiHubCA']):
        opts['serverca'] = options['KojiHubCA']

    session = koji.ClientSession(options['KojiHubURL'], opts=opts)

    environ['koji.currentLogin'] = _getUserCookie(environ)
    if environ['koji.currentLogin']:
        environ['koji.currentUser'] = session.getUser(environ['koji.currentLogin'])
        if not environ['koji.currentUser']:
            raise koji.AuthError(
                'could not get user for principal: %s' % environ['koji.currentLogin'])
        _setUserCookie(environ, environ['koji.currentLogin'])
    else:
        environ['koji.currentUser'] = None

    environ['koji.session'] = session
    return session


def _construct_url(environ, page):
    port = environ['SERVER_PORT']
    host = environ['SERVER_NAME']
    url_scheme = environ['wsgi.url_scheme']
    if (url_scheme == 'https' and port == '443') or \
            (url_scheme == 'http' and port == '80'):
        return "%s://%s%s" % (url_scheme, host, page)
    return "%s://%s:%s%s" % (url_scheme, host, port, page)


def _getBaseURL(environ):
    base = environ['SCRIPT_NAME']
    return _construct_url(environ, base)


def _redirect(environ, location):
    environ['koji.redirect'] = location
    raise ServerRedirect


def _redirectBack(environ, page, forceSSL):
    localurl = '%s://%s' % (environ['REQUEST_SCHEME'], environ['SERVER_NAME'])
    if page:
        # We'll work with the page we were given
        pass
    elif environ.get('HTTP_REFERER', '').startswith(localurl):
        page = environ['HTTP_REFERER']
    else:
        page = 'index'

    # Modify the scheme if necessary
    if page.startswith('http'):
        pass
    elif page.startswith('/'):
        page = _construct_url(environ, page)
    else:
        page = _getBaseURL(environ) + '/' + page
    if forceSSL:
        page = page.replace('http:', 'https:')
    else:
        page = page.replace('https:', 'http:')

    # and redirect to the page
    _redirect(environ, page)


def login(environ, page=None):
    session = _getServer(environ)
    options = environ['koji.options']

    if options['WebAuthType'] == koji.AUTHTYPES['SSL']:
        ## Clients authenticate to KojiWeb by SSL, so extract
        ## the username via the (verified) client certificate
        if environ['wsgi.url_scheme'] != 'https':
            dest = 'login'
            if page:
                dest = dest + '?page=' + page
            _redirectBack(environ, dest, forceSSL=True)
            return

        if environ.get('SSL_CLIENT_VERIFY') != 'SUCCESS':
            raise koji.AuthError('could not verify client: %s' % environ.get('SSL_CLIENT_VERIFY'))

        # use the subject's common name as their username
        username = environ.get('SSL_CLIENT_S_DN_CN')
        if not username:
            raise koji.AuthError('unable to get user information from client certificate')
    elif options['WebAuthType'] == koji.AUTHTYPES['GSSAPI']:
        ## Clients authenticate to KojiWeb by Kerberos, so extract
        ## the username via the REMOTE_USER which will be the
        ## Kerberos principal
        principal = environ.get('REMOTE_USER')
        if not principal:
            raise koji.AuthError(
                'configuration error: mod_auth_gssapi should have performed authentication before '
                'presenting this page')

        username = principal
    else:
        raise koji.AuthError(
            'configuration error: set WebAuthType or on of WebPrincipal/WebCert options')

    ## This now is how we proxy the user to the hub
    if options['WebCert']:
        if not _sslLogin(environ, session, username):
            raise koji.AuthError('could not login %s using SSL certificates' % username)

        authlogger.info('Successful SSL authentication by %s', username)
    elif options['WebPrincipal']:
        if not _gssapiLogin(environ, session, username):
            raise koji.AuthError('could not login using principal: %s' % username)

        authlogger.info('Successful Kerberos authentication by %s', username)
    else:
        raise koji.AuthError(
            'KojiWeb is incorrectly configured for authentication, contact the system '
            'administrator')

    _setUserCookie(environ, username)
    # To protect the session cookie, we must forceSSL
    _redirectBack(environ, page, forceSSL=True)


def logout(environ, page=None):
    user = _getUserCookie(environ)
    _clearUserCookie(environ)
    if user:
        authlogger.info('Logout by %s', user)

    _redirectBack(environ, page, forceSSL=False)


def index(environ, packageOrder='package_name', packageStart=None):
    values = _initValues(environ)
    server = _getServer(environ)

    opts = environ['koji.options']
    user = environ['koji.currentUser']

    values['builds'] = server.listBuilds(
        userID=(user and user['id'] or None),
        queryOpts={'order': '-build_id', 'limit': 10}
    )

    taskOpts = {'parent': None, 'decode': True}
    if user:
        taskOpts['owner'] = user['id']
    if opts.get('HiddenUsers'):
        taskOpts['not_owner'] = [
            int(userid) for userid in opts['HiddenUsers'].split()
        ]
    values['tasks'] = server.listTasks(
        opts=taskOpts,
        queryOpts={'order': '-id', 'limit': 10}
    )

    values['order'] = '-id'

    if user:
        kojiweb.util.paginateResults(server, values, 'listPackages',
                                     kw={'userID': user['id'], 'with_dups': True},
                                     start=packageStart, dataName='packages', prefix='package',
                                     order=packageOrder, pageSize=10)

        notifs = server.getBuildNotifications(user['id'])
        notifs.sort(key=lambda x: x['id'])
        with server.multicall() as m:
            for notif in notifs:
                notif['package'] = None
                if notif['package_id']:
                    notif['package'] = m.getPackage(notif['package_id'])

                notif['tag'] = None
                if notif['tag_id']:
                    # it's possible a notification could reference a deleted tag
                    notif['tag'] = m.getTag(notif['tag_id'], event='auto')
        for notif in notifs:
            if notif['package']:
                notif['package'] = notif['package'].result
            if notif['tag']:
                notif['tag'] = notif['tag'].result
        values['notifs'] = notifs

    values['user'] = user
    values['welcomeMessage'] = environ['koji.options']['KojiGreeting']

    values['koji'] = koji

    return _genHTML(environ, 'index.html.j2', jinja=True)


def notificationedit(environ, notificationID):
    server = _getServer(environ)
    _assertLogin(environ)

    notificationID = int(notificationID)
    notification = server.getBuildNotification(notificationID)
    if notification is None:
        raise koji.GenericError('no notification with ID: %i' % notificationID)

    form = environ['koji.form']

    if 'save' in form:
        package_id = form.getfirst('package')
        if package_id == 'all':
            package_id = None
        else:
            package_id = int(package_id)

        tag_id = form.getfirst('tag')
        if tag_id == 'all':
            tag_id = None
        else:
            tag_id = int(tag_id)

        if 'success_only' in form:
            success_only = True
        else:
            success_only = False

        server.updateNotification(notification['id'], package_id, tag_id, success_only)

        _redirect(environ, 'index')
    elif 'cancel' in form:
        _redirect(environ, 'index')
    else:
        values = _initValues(environ, 'Edit Notification')

        values['notif'] = notification
        packages = server.listPackagesSimple(queryOpts={'order': 'package_name'})
        values['packages'] = packages
        tags = server.listTags(queryOpts={'order': 'name'})
        values['tags'] = tags

        return _genHTML(environ, 'notificationedit.html.j2', jinja=True)


def notificationcreate(environ):
    server = _getServer(environ)
    _assertLogin(environ)

    form = environ['koji.form']

    if 'add' in form:
        user = environ['koji.currentUser']
        if not user:
            raise koji.GenericError('not logged-in')

        package_id = form.getfirst('package')
        if package_id == 'all':
            package_id = None
        else:
            package_id = int(package_id)

        tag_id = form.getfirst('tag')
        if tag_id == 'all':
            tag_id = None
        else:
            tag_id = int(tag_id)

        if 'success_only' in form:
            success_only = True
        else:
            success_only = False

        server.createNotification(user['id'], package_id, tag_id, success_only)

        _redirect(environ, 'index')
    elif 'cancel' in form:
        _redirect(environ, 'index')
    else:
        values = _initValues(environ, 'Edit Notification')

        values['notif'] = None
        packages = server.listPackagesSimple(queryOpts={'order': 'package_name'})
        values['packages'] = packages
        tags = server.listTags(queryOpts={'order': 'name'})
        values['tags'] = tags

        return _genHTML(environ, 'notificationedit.html.j2', jinja=True)


def notificationdelete(environ, notificationID):
    server = _getServer(environ)
    _assertLogin(environ)

    notificationID = int(notificationID)
    notification = server.getBuildNotification(notificationID)
    if not notification:
        raise koji.GenericError('no notification with ID: %i' % notificationID)

    server.deleteNotification(notification['id'])

    _redirect(environ, 'index')


# All Tasks
_TASKS = ['build',
          'buildSRPMFromSCM',
          'rebuildSRPM',
          'buildArch',
          'chainbuild',
          'maven',
          'buildMaven',
          'chainmaven',
          'wrapperRPM',
          'winbuild',
          'vmExec',
          'waitrepo',
          'tagBuild',
          'newRepo',
          'createrepo',
          'distRepo',
          'createdistrepo',
          'buildNotification',
          'tagNotification',
          'dependantTask',
          'livecd',
          'createLiveCD',
          'appliance',
          'createAppliance',
          'image',
          'indirectionimage',
          'createImage',
          'livemedia',
          'createLiveMedia']
# Tasks that can exist without a parent
_TOPLEVEL_TASKS = ['build', 'buildNotification', 'chainbuild', 'maven', 'chainmaven', 'wrapperRPM',
                   'winbuild', 'newRepo', 'distRepo', 'tagBuild', 'tagNotification', 'waitrepo',
                   'livecd', 'appliance', 'image', 'livemedia']
# Tasks that can have children
_PARENT_TASKS = ['build', 'chainbuild', 'maven', 'chainmaven', 'winbuild', 'newRepo', 'distRepo',
                 'wrapperRPM', 'livecd', 'appliance', 'image', 'livemedia']


def tasks(environ, owner=None, state='active', view='tree', method='all', hostID=None,
          channelID=None, start=None, order='-id'):
    values = _initValues(environ, 'Tasks', 'tasks')
    server = _getServer(environ)

    if view not in ('tree', 'toplevel', 'flat'):
        raise koji.GenericError("Invalid value for view: %r" % view)

    opts = {'decode': True}
    if owner:
        owner = _convert_if_int(owner)
        ownerObj = server.getUser(owner, strict=True)
        opts['owner'] = ownerObj['id']
        values['owner'] = ownerObj['name']
        values['ownerObj'] = ownerObj
    else:
        values['owner'] = None
        values['ownerObj'] = None

    values['users'] = server.listUsers(queryOpts={'order': 'name'})

    if method in _TASKS + environ['koji.options']['Tasks']:
        opts['method'] = method
    else:
        method = 'all'
    values['method'] = method
    values['alltasks'] = sorted(_TASKS + environ['koji.options']['Tasks'])

    treeEnabled = True
    if hostID or (method not in ['all'] + _PARENT_TASKS + environ['koji.options']['ParentTasks']):
        # force flat view if we're filtering by a hostID or a task that never has children
        if view == 'tree':
            view = 'flat'
        # don't let them choose tree view either
        treeEnabled = False
    values['treeEnabled'] = treeEnabled

    toplevelEnabled = True
    if method not in ['all'] + _TOPLEVEL_TASKS + environ['koji.options']['ToplevelTasks']:
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
        opts['state'] = [koji.TASK_STATES['FREE'],
                         koji.TASK_STATES['OPEN'],
                         koji.TASK_STATES['ASSIGNED']]
    elif state == 'all':
        pass
    else:
        # Assume they've passed in a state name
        opts['state'] = [koji.TASK_STATES[state.upper()]]
    values['state'] = state

    if hostID:
        hostID = _convert_if_int(hostID)
        host = server.getHost(hostID, strict=True)
        opts['host_id'] = host['id']
        values['host'] = host
        values['hostID'] = host['id']
    else:
        values['host'] = None
        values['hostID'] = None

    if channelID:
        channelID = _convert_if_int(channelID)
        channel = server.getChannel(channelID, strict=True)
        opts['channel_id'] = channel['id']
        values['channel'] = channel
        values['channelID'] = channel['id']
    else:
        values['channel'] = None
        values['channelID'] = None

    loggedInUser = environ['koji.currentUser']
    values['loggedInUser'] = loggedInUser

    values['order'] = order

    tasks = kojiweb.util.paginateMethod(server, values, 'listTasks', kw={'opts': opts},
                                        start=start, dataName='tasks', prefix='task',
                                        order=order, first_page_count=False)

    if view == 'tree':
        server.multicall = True
        for task in tasks:
            server.getTaskDescendents(task['id'], request=True)
        descendentList = server.multiCall()
        for task, [descendents] in zip(tasks, descendentList):
            task['descendents'] = descendents

    values['S'] = SafeValue
    values['koji'] = koji

    return _genHTML(environ, 'tasks.html.j2', jinja=True)


def taskinfo(environ, taskID):
    server = _getServer(environ)
    values = _initValues(environ, 'Task Info', 'tasks')

    taskID = int(taskID)
    task = server.getTaskInfo(taskID, request=True)
    if not task:
        raise koji.GenericError('No such task ID: %s' % taskID)

    values['title'] = koji.taskLabel(task) + ' | Task Info'

    try:
        params = parse_task_params(task['method'], task['request'])
    except TypeError:
        # unknown tasks/plugins
        params = {'args': task['request']}
    values['task'] = task
    values['params'] = params
    if 'opts' in params:
        values['opts'] = params.pop('opts')
    else:
        values['opts'] = {}

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

    values['estCompletion'] = None
    if taskBuild and taskBuild['state'] == koji.BUILD_STATES['BUILDING']:
        avgDuration = server.getAverageBuildDuration(taskBuild['package_id'])
        if avgDuration is not None:
            avgDelta = datetime.timedelta(seconds=avgDuration)
            startTime = datetime.datetime.fromtimestamp(taskBuild['creation_ts'])
            values['estCompletion'] = startTime + avgDelta

    buildroots = server.listBuildroots(taskID=task['id'])
    values['buildroots'] = buildroots

    def _get_tag(tag_id):
        if not tag_id:
            return None
        elif isinstance(tag_id, dict):
            return tag_id
        else:
            info = server.getTag(tag_id, event='auto')
            if info and 'revoke_event' in info:
                info['name'] = "%(name)s (deleted)" % info
            return info

    if 'root' in params:
        params['build_tag'] = _get_tag(params.pop('root'))
    if 'tag_id' in params:
        params['destination_tag'] = _get_tag(params.pop('tag_id'))
    if 'tag' in params:
        params['tag'] = _get_tag(params.pop('tag'))
    if 'tag_info' in params:
        params['destination_tag'] = _get_tag(params.pop('tag_info'))
    if 'from_info' in params:
        params['source tag'] = _get_tag(params.pop('from_info'))
    if 'build_info' in params:
        params['build'] = server.getBuild(params.pop('build_info'))
    if 'build_id' in params:
        params['build'] = server.getBuild(params.pop('build_id'))
    if 'user_info' in params:
        params['user'] = server.getUser(params.pop('user_info'))
    if 'task_list' in params:
        tmp = []
        for t in params.pop('task_list'):
            base = parse_task_params(t[0], t[1])
            base['method'] = t[0]
            base['opts'] = t[2]
            tmp.append(base)
        params['task_list'] = tmp
    if 'wait_list' in params:
        params['wait_list'] = [server.getTaskInfo(t) for t in params['wait_list']]
    for key in ('target', 'build_target', 'target_info'):
        if key in params:
            params['build_target'] = server.getBuildTarget(params.pop(key))
            break
    if 'build_tag' in params:
        params['build_tag'] = _get_tag(params.pop('build_tag'))
    if 'task_id' in params:
        params['task'] = server.getTaskInfo(params.pop('task_id'), request=True)
    if 'repo_id' in params:
        params['repo'] = server.repoInfo(params.pop('repo_id'))
    if 'buildrootID' in params:
        params['buildroot'] = server.getBuildroot(params.pop('buildrootID'))

    taskBuilds = []
    if task['state'] in (koji.TASK_STATES['CLOSED'], koji.TASK_STATES['FAILED']):
        try:
            result = server.getTaskResult(task['id'])
        except Exception:
            excClass, exc = sys.exc_info()[:2]
            values['result'] = exc
            values['excClass'] = excClass
        if not values.get('result'):
            values['result'] = result
            values['excClass'] = None
            if task['method'] == 'buildContainer' and 'koji_builds' in result:
                taskBuilds = [
                    server.getBuild(int(buildID)) for buildID in result['koji_builds']]
    else:
        values['result'] = None
        values['excClass'] = None

    if taskBuild and taskBuild['build_id'] not in [x['build_id'] for x in taskBuilds]:
        taskBuilds.append(taskBuild)
    values['taskBuilds'] = taskBuilds

    full_result_text, abbr_result_text = kojiweb.util.task_result_to_html(
        values['result'], values['excClass'], abbr_postscript='...')
    values['full_result_text'] = full_result_text
    values['abbr_result_text'] = abbr_result_text

    topurl = environ['koji.options']['KojiFilesURL']
    pathinfo = koji.PathInfo(topdir=topurl)
    values['pathinfo'] = pathinfo

    paths = []  # (volume, relpath) tuples
    for relname, volumes in server.listTaskOutput(task['id'], all_volumes=True).items():
        paths += [(volume, relname) for volume in volumes]
    values['output'] = sorted(paths, key=_sortByExtAndName)
    if environ['koji.currentUser']:
        values['perms'] = server.getUserPerms(environ['koji.currentUser']['id'])
    else:
        values['perms'] = []

    values['koji'] = koji
    values['S'] = SafeValue

    return _genHTML(environ, 'taskinfo.html.j2', jinja=True)


def taskstatus(environ, taskID):
    server = _getServer(environ)

    taskID = int(taskID)
    task = server.getTaskInfo(taskID)
    if not task:
        return ''
    files = server.listTaskOutput(taskID, stat=True, all_volumes=True)
    output = '%i:%s\n' % (task['id'], koji.TASK_STATES[task['state']])
    for filename, volumes_data in files.items():
        for volume, file_stats in volumes_data.items():
            output += '%s:%s:%s\n' % (volume, filename, file_stats['st_size'])
    return output


def resubmittask(environ, taskID):
    server = _getServer(environ)
    _assertLogin(environ)

    taskID = int(taskID)
    newTaskID = server.resubmitTask(taskID)
    _redirect(environ, 'taskinfo?taskID=%i' % newTaskID)


def canceltask(environ, taskID):
    server = _getServer(environ)
    _assertLogin(environ)

    taskID = int(taskID)
    server.cancelTask(taskID)
    _redirect(environ, 'taskinfo?taskID=%i' % taskID)


def freetask(environ, taskID):
    server = _getServer(environ)
    _assertLogin(environ)

    taskID = int(taskID)
    server.freeTask(taskID)
    _redirect(environ, 'taskinfo?taskID=%i' % taskID)


def _sortByExtAndName(item):
    """Sort filename tuples key function, first by extension, and then by name."""
    kRoot, kExt = os.path.splitext(os.path.basename(item[1]))
    return (kExt, kRoot)


def getfile(environ, taskID, name, volume='DEFAULT', offset=None, size=None):
    server = _getServer(environ)
    taskID = int(taskID)

    output = server.listTaskOutput(taskID, stat=True, all_volumes=True)
    try:
        file_info = output[name][volume]
    except KeyError:
        raise koji.GenericError('no file "%s" output by task %i' % (name, taskID))

    mime_guess = mimetypes.guess_type(name, strict=False)[0]
    if mime_guess:
        ctype = mime_guess
    else:
        if name.endswith('.log') or name.endswith('.ks'):
            ctype = 'text/plain'
        else:
            ctype = 'application/octet-stream'
    if ctype != 'text/plain':
        environ['koji.headers'].append(['Content-Disposition', 'attachment; filename=%s' % name])
    environ['koji.headers'].append(['Content-Type', ctype])

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

    # environ['koji.headers'].append(['Content-Length', str(size)])
    return _chunk_file(server, environ, taskID, name, offset, size, volume)


def _chunk_file(server, environ, taskID, name, offset, size, volume):
    remaining = size
    while True:
        if remaining <= 0:
            break
        chunk_size = 1048576
        if remaining < chunk_size:
            chunk_size = remaining
        content = server.downloadTaskOutput(taskID, name,
                                            offset=offset, size=chunk_size, volume=volume)
        if not content:
            break
        yield content
        content_length = len(content)
        offset += content_length
        remaining -= content_length


def tags(environ, start=None, order=None, childID=None):
    values = _initValues(environ, 'Tags', 'tags')
    server = _getServer(environ)

    if order is None:
        order = 'name'
    values['order'] = order

    kojiweb.util.paginateMethod(server, values, 'listTags', kw=None,
                                start=start, dataName='tags', prefix='tag', order=order)

    if environ['koji.currentUser']:
        values['perms'] = server.getUserPerms(environ['koji.currentUser']['id'])
    else:
        values['perms'] = []

    if childID is None:
        values['childID'] = None
    else:
        values['childID'] = int(childID)

    return _genHTML(environ, 'tags.html.j2', jinja=True)


_PREFIX_CHARS = [chr(char) for char in list(range(48, 58)) + list(range(97, 123))]


def packages(environ, tagID=None, userID=None, order='package_name', start=None, prefix=None,
             inherited='1', blocked='1'):
    values = _initValues(environ, 'Packages', 'packages')
    server = _getServer(environ)
    tag = None
    if tagID is not None:
        tagID = _convert_if_int(tagID)
        tag = server.getTag(tagID, strict=True)
    values['tagID'] = tagID
    values['tag'] = tag
    user = None
    if userID is not None:
        userID = _convert_if_int(userID)
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
    blocked = int(blocked)
    values['blocked'] = blocked

    kojiweb.util.paginateMethod(server, values, 'listPackages',
                                kw={'tagID': tagID,
                                    'userID': userID,
                                    'prefix': prefix,
                                    'inherited': bool(inherited),
                                    'with_blocked': bool(blocked)},
                                start=start, dataName='packages', prefix='package', order=order)

    values['chars'] = _PREFIX_CHARS

    return _genHTML(environ, 'packages.html.j2', jinja=True)


def packageinfo(environ, packageID, tagOrder='name', tagStart=None, buildOrder='-completion_time',
                buildStart=None):
    values = _initValues(environ, 'Package Info', 'packages')
    server = _getServer(environ)

    packageID = _convert_if_int(packageID)
    package = server.getPackage(packageID)
    if package is None:
        raise koji.GenericError('No such package ID: %s' % packageID)

    values['title'] = package['name'] + ' | Package Info'

    values['package'] = package
    values['packageID'] = package['id']

    kojiweb.util.paginateMethod(server, values, 'listTags', kw={'package': package['id']},
                                start=tagStart, dataName='tags', prefix='tag', order=tagOrder)
    kojiweb.util.paginateMethod(server, values, 'listBuilds', kw={'packageID': package['id']},
                                start=buildStart, dataName='builds', prefix='build',
                                order=buildOrder)

    return _genHTML(environ, 'packageinfo.html.j2', jinja=True)


def taginfo(environ, tagID, all='0', packageOrder='package_name', packageStart=None,
            buildOrder='-completion_time', buildStart=None, childID=None):
    values = _initValues(environ, 'Tag Info', 'tags')
    server = _getServer(environ)

    tagID = _convert_if_int(tagID)
    tag = server.getTag(tagID, strict=True, event='auto')

    values['title'] = tag['name'] + ' | Tag Info'
    values['tag'] = tag
    values['tagID'] = tag['id']
    if 'revoke_event' in tag:
        values['delete_ts'] = server.getEvent(tag['revoke_event'])['ts']
        return _genHTML(environ, 'taginfo_deleted.html.j2', jinja=True)

    all = int(all)

    numPackages = server.count('listPackages', tagID=tag['id'], inherited=True, with_owners=False,
                               with_blocked=False)
    numPackagesBlocked = server.count('listPackages', tagID=tag['id'], inherited=True,
                                      with_owners=False)
    numBuilds = server.count('listTagged', tag=tag['id'], inherit=True)
    values['numPackages'] = numPackages
    values['numPackagesBlocked'] = numPackagesBlocked
    values['numBuilds'] = numBuilds

    inheritance = server.getFullInheritance(tag['id'])
    tagsByChild = {}
    for parent in inheritance:
        child_id = parent['child_id']
        if child_id not in tagsByChild:
            tagsByChild[child_id] = []
        tagsByChild[child_id].append(child_id)

    srcTargets = server.getBuildTargets(buildTagID=tag['id'])
    srcTargets.sort(key=_sortbyname)
    destTargets = server.getBuildTargets(destTagID=tag['id'])
    destTargets.sort(key=_sortbyname)

    values['inheritance'] = inheritance
    values['tagsByChild'] = tagsByChild
    values['srcTargets'] = srcTargets
    values['destTargets'] = destTargets
    values['all'] = all
    values['repo'] = server.getRepo(tag['id'], state=koji.REPO_READY)
    values['external_repos'] = server.getExternalRepoList(tag['id'])

    child = None
    if childID is not None:
        childID = _convert_if_int(childID)
        child = server.getTag(childID, strict=True)
    values['child'] = child

    if environ['koji.currentUser']:
        values['perms'] = server.getUserPerms(environ['koji.currentUser']['id'])
    else:
        values['perms'] = []
    permList = server.getAllPerms()
    allPerms = dict([(perm['id'], perm['name']) for perm in permList])
    values['allPerms'] = allPerms

    return _genHTML(environ, 'taginfo.html.j2', jinja=True)


def tagcreate(environ):
    server = _getServer(environ)
    _assertLogin(environ)

    mavenEnabled = server.mavenEnabled()

    form = environ['koji.form']

    if 'add' in form:
        params = {}
        name = form['name'].value
        params['arches'] = form['arches'].value
        params['locked'] = 'locked' in form
        permission = form['permission'].value
        if permission != 'none':
            params['perm'] = int(permission)
        if mavenEnabled:
            params['maven_support'] = bool('maven_support' in form)
            params['maven_include_all'] = bool('maven_include_all' in form)

        tagID = server.createTag(name, **params)

        _redirect(environ, 'taginfo?tagID=%i' % tagID)
    elif 'cancel' in form:
        _redirect(environ, 'tags')
    else:
        values = _initValues(environ, 'Add Tag', 'tags')

        values['mavenEnabled'] = mavenEnabled

        values['tag'] = None
        values['permissions'] = server.getAllPerms()

        return _genHTML(environ, 'tagedit.html.j2', jinja=True)


def tagedit(environ, tagID):
    server = _getServer(environ)
    _assertLogin(environ)

    mavenEnabled = server.mavenEnabled()

    tagID = int(tagID)
    tag = server.getTag(tagID)
    if tag is None:
        raise koji.GenericError('no tag with ID: %i' % tagID)

    form = environ['koji.form']

    if 'save' in form:
        params = {}
        params['name'] = form['name'].value
        params['arches'] = form['arches'].value
        params['locked'] = bool('locked' in form)
        permission = form['permission'].value
        if permission == 'none':
            params['perm'] = None
        else:
            params['perm'] = int(permission)
        if mavenEnabled:
            params['maven_support'] = bool('maven_support' in form)
            params['maven_include_all'] = bool('maven_include_all' in form)

        server.editTag(tag['id'], **params)

        _redirect(environ, 'taginfo?tagID=%i' % tag['id'])
    elif 'cancel' in form:
        _redirect(environ, 'taginfo?tagID=%i' % tag['id'])
    else:
        values = _initValues(environ, 'Edit Tag', 'tags')

        values['mavenEnabled'] = mavenEnabled

        values['tag'] = tag
        values['permissions'] = server.getAllPerms()

        return _genHTML(environ, 'tagedit.html.j2', jinja=True)


def tagdelete(environ, tagID):
    server = _getServer(environ)
    _assertLogin(environ)

    tagID = int(tagID)
    tag = server.getTag(tagID)
    if tag is None:
        raise koji.GenericError('no tag with ID: %i' % tagID)

    server.deleteTag(tag['id'])

    _redirect(environ, 'tags')


def tagparent(environ, tagID, parentID, action):
    server = _getServer(environ)
    _assertLogin(environ)

    tag = server.getTag(int(tagID), strict=True)
    parent = server.getTag(int(parentID), strict=True)

    if action in ('add', 'edit'):
        form = environ['koji.form']

        if 'add' in form or 'save' in form:
            newDatum = {}
            newDatum['parent_id'] = parent['id']
            newDatum['priority'] = int(form.getfirst('priority'))
            maxdepth = form.getfirst('maxdepth')
            maxdepth = len(maxdepth) > 0 and int(maxdepth) or None
            newDatum['maxdepth'] = maxdepth
            newDatum['intransitive'] = bool('intransitive' in form)
            newDatum['noconfig'] = bool('noconfig' in form)
            newDatum['pkg_filter'] = form.getfirst('pkg_filter')

            data = server.getInheritanceData(tag['id'])
            data.append(newDatum)

            server.setInheritanceData(tag['id'], data)
        elif 'cancel' in form:
            pass
        else:
            values = _initValues(environ, action.capitalize() + ' Parent Tag', 'tags')
            values['tag'] = tag
            values['parent'] = parent

            inheritanceData = server.getInheritanceData(tag['id'])
            maxPriority = 0
            for datum in inheritanceData:
                if datum['priority'] > maxPriority:
                    maxPriority = datum['priority']
            values['maxPriority'] = maxPriority
            inheritanceData = [datum for datum in inheritanceData
                               if datum['parent_id'] == parent['id']]
            if len(inheritanceData) == 0:
                values['inheritanceData'] = None
            elif len(inheritanceData) == 1:
                values['inheritanceData'] = inheritanceData[0]
            else:
                raise koji.GenericError(
                    'tag %i has tag %i listed as a parent more than once' %
                    (tag['id'], parent['id']))

            return _genHTML(environ, 'tagparent.html.j2', jinja=True)
    elif action == 'remove':
        data = server.getInheritanceData(tag['id'])
        for datum in data:
            if datum['parent_id'] == parent['id']:
                datum['delete link'] = True
                break
        else:
            raise koji.GenericError('tag %i is not a parent of tag %i' % (parent['id'], tag['id']))

        server.setInheritanceData(tag['id'], data)
    else:
        raise koji.GenericError('unknown action: %s' % action)

    _redirect(environ, 'taginfo?tagID=%i' % tag['id'])


def externalrepoinfo(environ, extrepoID):
    values = _initValues(environ, 'External Repo Info', 'tags')
    server = _getServer(environ)

    extrepoID = _convert_if_int(extrepoID)
    extRepo = server.getExternalRepo(extrepoID, strict=True)
    repoTags = server.getTagExternalRepos(repo_info=extRepo['id'])

    values['title'] = extRepo['name'] + ' | External Repo Info'
    values['extRepo'] = extRepo
    values['repoTags'] = repoTags

    return _genHTML(environ, 'externalrepoinfo.html.j2', jinja=True)


def buildinfo(environ, buildID):
    values = _initValues(environ, 'Build Info', 'builds')
    server = _getServer(environ)
    topurl = environ['koji.options']['KojiFilesURL']
    pathinfo = koji.PathInfo(topdir=topurl)

    buildID = int(buildID)

    try:
        build = server.getBuild(buildID, strict=True)
    except koji.GenericError:
        raise koji.GenericError("No such build ID: %i" % buildID)

    values['title'] = koji.buildLabel(build) + ' | Build Info'

    tags = server.listTags(build['id'])
    tags.sort(key=_sortbyname)
    rpms = server.listBuildRPMs(build['id'])
    rpms.sort(key=_sortbyname)
    typeinfo = server.getBuildType(buildID)
    archiveIndex = {}
    for btype in typeinfo:
        archives = server.listArchives(build['id'], type=btype, queryOpts={'order': 'filename'})
        idx = archiveIndex.setdefault(btype, {})
        for archive in archives:
            if btype == 'maven':
                archive['display'] = archive['filename']
                archive['dl_url'] = '/'.join([pathinfo.mavenbuild(build),
                                              pathinfo.mavenfile(archive)])
            elif btype == 'win':
                archive['display'] = pathinfo.winfile(archive)
                archive['dl_url'] = '/'.join([pathinfo.winbuild(build), pathinfo.winfile(archive)])
            elif btype == 'image':
                archive['display'] = archive['filename']
                archive['dl_url'] = '/'.join([pathinfo.imagebuild(build), archive['filename']])
            else:
                archive['display'] = archive['filename']
                archive['dl_url'] = '/'.join([pathinfo.typedir(build, btype), archive['filename']])
            ext = os.path.splitext(archive['filename'])[1][1:]
            idx.setdefault(ext, []).append(archive)

    rpmsByArch = {}
    debuginfos = []
    for rpm in rpms:
        if koji.is_debuginfo(rpm['name']):
            debuginfos.append(rpm)
        else:
            rpmsByArch.setdefault(rpm['arch'], []).append(rpm)
    # add debuginfos at the end
    for rpm in debuginfos:
        rpmsByArch.setdefault(rpm['arch'], []).append(rpm)

    if 'src' in rpmsByArch:
        srpm = rpmsByArch['src'][0]
        result = server.getRPMHeaders(srpm['id'], headers=RPM_HEADERS)
        for header in RPM_HEADERS:
            values[header] = koji.fixEncoding(result.get(header))
        values['changelog'] = server.getChangelogEntries(build['id'])

    task_id = extract_build_task(build)
    if task_id:
        task = server.getTaskInfo(task_id, request=True)
        # get the summary, description, and changelogs from the built srpm
        # if the build is not yet complete
        if build['state'] != koji.BUILD_STATES['COMPLETE']:
            srpm_tasks = server.listTasks(opts={'parent': task['id'],
                                                'method': 'buildSRPMFromSCM'})
            if srpm_tasks:
                srpm_task = srpm_tasks[0]
                if srpm_task['state'] == koji.TASK_STATES['CLOSED']:
                    srpm_path = None
                    for output in server.listTaskOutput(srpm_task['id']):
                        if output.endswith('.src.rpm'):
                            srpm_path = output
                            break
                    if srpm_path:
                        srpm_headers = server.getRPMHeaders(taskID=srpm_task['id'],
                                                            filepath=srpm_path,
                                                            headers=RPM_HEADERS)
                        if srpm_headers:
                            for header in RPM_HEADERS:
                                values[header] = koji.fixEncoding(srpm_headers.get(header))
                        changelog = server.getChangelogEntries(taskID=srpm_task['id'],
                                                               filepath=srpm_path)
                        if changelog:
                            values['changelog'] = changelog
    else:
        task = None

    # get logs
    logs = server.getBuildLogs(buildID)
    logs_by_dir = {}
    for loginfo in logs:
        loginfo['dl_url'] = "%s/%s" % (topurl, loginfo['path'])
        logdir = loginfo['dir']
        if logdir == '.':
            logdir = ''
        logs_by_dir.setdefault(logdir, []).append(loginfo)
    values['logs_by_dir'] = logs_by_dir

    values['build'] = build
    values['tags'] = tags
    values['rpmsByArch'] = rpmsByArch
    values['task'] = task
    values['typeinfo'] = typeinfo
    values['archiveIndex'] = archiveIndex

    if environ['koji.currentUser']:
        values['perms'] = server.getUserPerms(environ['koji.currentUser']['id'])
    else:
        values['perms'] = []
    for header in RPM_HEADERS + ['changelog']:
        if header not in values:
            values[header] = None

    # We added the start_time field in 2015 as part of Koji's content
    # generator feature. Builds before that point have a null value for
    # start_time. Fall back to creation_ts in those cases.
    # Currently new_build() has data.setdefault('start_time', 'NOW'), so all
    # recent builds should have a value for the field.
    values['start_ts'] = build.get('start_ts') or build['creation_ts']
    # the build start time is not accurate for maven and win builds, get it from the
    # task start time instead
    if 'maven' in typeinfo or 'win' in typeinfo:
        if task:
            values['start_ts'] = task['start_ts']
    if 'module' in typeinfo:
        module_tag = None
        module_tag_name = typeinfo['module'].get('content_koji_tag')
        if module_tag_name:
            module_tag = server.getTag(module_tag_name, event='auto')
        values['module_tag'] = module_tag
        values['module_id'] = typeinfo['module'].get('module_build_service_id')
        values['mbs_web_url'] = environ['koji.options']['MBS_WEB_URL']
    if build['state'] == koji.BUILD_STATES['BUILDING']:
        avgDuration = server.getAverageBuildDuration(build['package_id'])
        if avgDuration is not None:
            avgDelta = datetime.timedelta(seconds=avgDuration)
            startTime = datetime.datetime.fromtimestamp(build['creation_ts'])
            values['estCompletion'] = startTime + avgDelta
        else:
            values['estCompletion'] = None

    values['pathinfo'] = pathinfo
    values['koji'] = koji
    return _genHTML(environ, 'buildinfo.html.j2', jinja=True)


def builds(environ, userID=None, tagID=None, packageID=None, state=None, order='-build_id',
           start=None, prefix=None, inherited='1', latest='1', type=None):
    values = _initValues(environ, 'Builds', 'builds')
    server = _getServer(environ)

    user = None
    if userID:
        userID = _convert_if_int(userID)
        user = server.getUser(userID, strict=True)
    values['userID'] = userID
    values['user'] = user

    loggedInUser = environ['koji.currentUser']
    values['loggedInUser'] = loggedInUser

    values['users'] = server.listUsers(queryOpts={'order': 'name'})

    tag = None
    if tagID:
        tagID = _convert_if_int(tagID)
        tag = server.getTag(tagID, strict=True)
    values['tagID'] = tagID
    values['tag'] = tag

    package = None
    if packageID:
        packageID = _convert_if_int(packageID)
        package = server.getPackage(packageID, strict=True)
    values['packageID'] = packageID
    values['package'] = package

    if state == 'all':
        state = None
    elif state is not None:
        state = int(state)
    values['state'] = state

    if prefix:
        prefix = prefix.lower()[0]
    if prefix not in _PREFIX_CHARS:
        prefix = None
    values['prefix'] = prefix

    values['order'] = order

    btypes = sorted([b['name'] for b in server.listBTypes()])
    if type in btypes:
        pass
    elif type == 'all':
        type = None
    else:
        type = None
    values['type'] = type
    values['btypes'] = btypes

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
        kojiweb.util.paginateResults(server, values, 'listTagged',
                                     kw={'tag': tag['id'],
                                         'package': (package and package['name'] or None),
                                         'owner': (user and user['name'] or None),
                                         'type': type,
                                         'inherit': bool(inherited), 'latest': bool(latest),
                                         'prefix': prefix},
                                     start=start, dataName='builds', prefix='build', order=order)
    else:
        kojiweb.util.paginateMethod(server, values, 'listBuilds',
                                    kw={'userID': (user and user['id'] or None),
                                        'packageID': (package and package['id'] or None),
                                        'type': type,
                                        'state': state, 'prefix': prefix},
                                    start=start, dataName='builds', prefix='build', order=order)

    values['chars'] = _PREFIX_CHARS
    values['koji'] = koji

    return _genHTML(environ, 'builds.html.j2', jinja=True)


def users(environ, order='name', start=None, prefix=None):
    values = _initValues(environ, 'Users', 'users')
    server = _getServer(environ)

    if prefix:
        prefix = prefix.lower()[0]
    if prefix not in _PREFIX_CHARS:
        prefix = None
    values['prefix'] = prefix

    values['order'] = order

    kojiweb.util.paginateMethod(server, values, 'listUsers', kw={'prefix': prefix},
                                start=start, dataName='users', prefix='user', order=order)

    values['chars'] = _PREFIX_CHARS

    return _genHTML(environ, 'users.html.j2', jinja=True)


def userinfo(environ, userID, packageOrder='package_name', packageStart=None,
             buildOrder='-completion_time', buildStart=None):
    values = _initValues(environ, 'User Info', 'users')
    server = _getServer(environ)

    userID = _convert_if_int(userID)
    user = server.getUser(userID, strict=True)

    values['title'] = user['name'] + ' | User Info'

    values['user'] = user
    values['userID'] = userID
    values['owner'] = user['name']
    values['taskCount'] = server.listTasks(opts={'owner': user['id'], 'parent': None},
                                           queryOpts={'countOnly': True})

    kojiweb.util.paginateResults(server, values, 'listPackages',
                                 kw={'userID': user['id'], 'with_dups': True},
                                 start=packageStart, dataName='packages', prefix='package',
                                 order=packageOrder, pageSize=10)

    kojiweb.util.paginateMethod(server, values, 'listBuilds', kw={'userID': user['id']},
                                start=buildStart, dataName='builds', prefix='build',
                                order=buildOrder, pageSize=10)

    return _genHTML(environ, 'userinfo.html.j2', jinja=True)


# headers shown in rpminfo and buildinfo pages
RPM_HEADERS = ['summary', 'description', 'license', 'disturl', 'vcs']


def rpminfo(environ, rpmID, fileOrder='name', fileStart=None, buildrootOrder='-id',
            buildrootStart=None):
    values = _initValues(environ, 'RPM Info', 'builds')
    server = _getServer(environ)

    rpmID = int(rpmID)
    try:
        rpm = server.getRPM(rpmID, strict=True)
    except koji.GenericError:
        raise koji.GenericError('No such RPM ID: %i' % rpmID)

    values['title'] = formatRPM(rpm, link=False) + SafeValue(' | RPM Info')

    build = None
    if rpm['build_id'] is not None:
        build = server.getBuild(rpm['build_id'])
    builtInRoot = None
    if rpm['buildroot_id'] is not None:
        builtInRoot = server.getBuildroot(rpm['buildroot_id'])
    if rpm['external_repo_id'] == 0:
        dep_names = {
            koji.DEP_REQUIRE: 'requires',
            koji.DEP_PROVIDE: 'provides',
            koji.DEP_OBSOLETE: 'obsoletes',
            koji.DEP_CONFLICT: 'conflicts',
            koji.DEP_SUGGEST: 'suggests',
            koji.DEP_ENHANCE: 'enhances',
            koji.DEP_SUPPLEMENT: 'supplements',
            koji.DEP_RECOMMEND: 'recommends',
        }
        deps = server.getRPMDeps(rpm['id'])
        for dep_type in dep_names:
            values[dep_names[dep_type]] = [d for d in deps if d['type'] == dep_type]
            values[dep_names[dep_type]].sort(key=_sortbyname)
        result = server.getRPMHeaders(rpm['id'], headers=RPM_HEADERS)
        for header in RPM_HEADERS:
            values[header] = koji.fixEncoding(result.get(header))
    buildroots = kojiweb.util.paginateMethod(server, values, 'listBuildroots',
                                             kw={'rpmID': rpm['id']},
                                             start=buildrootStart,
                                             dataName='buildroots',
                                             prefix='buildroot',
                                             order=buildrootOrder)

    values['rpmID'] = rpmID
    values['rpm'] = rpm
    values['build'] = build
    values['builtInRoot'] = builtInRoot
    values['buildroots'] = buildroots

    kojiweb.util.paginateMethod(server, values, 'listRPMFiles', args=[rpm['id']],
                                start=fileStart, dataName='files', prefix='file', order=fileOrder)

    values['koji'] = koji
    values['time'] = time  # TODO rework template so it doesn't need this

    return _genHTML(environ, 'rpminfo.html.j2', jinja=True)


def archiveinfo(environ, archiveID, fileOrder='name', fileStart=None, buildrootOrder='-id',
                buildrootStart=None):
    values = _initValues(environ, 'Archive Info', 'builds')
    server = _getServer(environ)

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
    if archive['buildroot_id'] is not None:
        builtInRoot = server.getBuildroot(archive['buildroot_id'])
    kojiweb.util.paginateMethod(server, values, 'listArchiveFiles', args=[archive['id']],
                                start=fileStart, dataName='files', prefix='file', order=fileOrder)
    buildroots = kojiweb.util.paginateMethod(server, values, 'listBuildroots',
                                             kw={'archiveID': archive['id']},
                                             start=buildrootStart,
                                             dataName='buildroots',
                                             prefix='buildroot',
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
    values['show_rpm_components'] = server.listRPMs(imageID=archive['id'], queryOpts={'limit': 1})
    values['show_archive_components'] = server.listArchives(imageID=archive['id'],
                                                            queryOpts={'limit': 1})

    values['koji'] = koji

    return _genHTML(environ, 'archiveinfo.html.j2', jinja=True)


def fileinfo(environ, filename, rpmID=None, archiveID=None):
    values = _initValues(environ, 'File Info', 'builds')
    server = _getServer(environ)

    values['rpm'] = None
    values['archive'] = None

    if rpmID:
        rpmID = int(rpmID)
        rpm = server.getRPM(rpmID)
        if not rpm:
            raise koji.GenericError('No such RPM ID: %i' % rpmID)
        file = server.getRPMFile(rpm['id'], filename)
        if not file:
            raise koji.GenericError('no file %s in RPM %i' % (filename, rpmID))
        values['rpm'] = rpm
    elif archiveID:
        archiveID = int(archiveID)
        archive = server.getArchive(archiveID)
        if not archive:
            raise koji.GenericError('No such archive ID: %i' % archiveID)
        file = server.getArchiveFile(archive['id'], filename)
        if not file:
            raise koji.GenericError('no file %s in archive %i' % (filename, archiveID))
        values['archive'] = archive
    else:
        raise koji.GenericError('either rpmID or archiveID must be specified')

    values['title'] = file['name'] + ' | File Info'

    values['file'] = file

    return _genHTML(environ, 'fileinfo.html.j2', jinja=True)


def cancelbuild(environ, buildID):
    server = _getServer(environ)
    _assertLogin(environ)

    buildID = int(buildID)
    build = server.getBuild(buildID)
    if build is None:
        raise koji.GenericError('unknown build ID: %i' % buildID)

    result = server.cancelBuild(build['id'])
    if not result:
        raise koji.GenericError('unable to cancel build')

    _redirect(environ, 'buildinfo?buildID=%i' % build['id'])


def hosts(environ, state='enabled', start=None, order='name', ready='all', channel='all',
          arch='all'):
    values = _initValues(environ, 'Hosts', 'hosts')
    server = _getServer(environ)

    values['order'] = order

    hosts = server.listHosts()
    values['arches'] = sorted(set(itertools.chain(*[host['arches'].split() for host in hosts])))

    if state == 'enabled':
        hosts = [x for x in hosts if x['enabled']]
    elif state == 'disabled':
        hosts = [x for x in hosts if not x['enabled']]
    else:
        state = 'all'
    values['state'] = state

    if ready == 'yes':
        hosts = [x for x in hosts if x['ready']]
    elif ready == 'no':
        hosts = [x for x in hosts if not x['ready']]
    else:
        ready = 'all'
    values['ready'] = ready

    if arch != 'all':
        arch = _validate_arch(arch)
        if arch:
            hosts = [x for x in hosts if arch in x['arches'].split(' ')]
    else:
        arch = 'all'
    values['arch'] = arch

    with server.multicall() as m:
        list_channels = [m.listChannels(hostID=host['id']) for host in hosts]
    for host, channels in zip(hosts, list_channels):
        host['channels'] = []
        host['channels_id'] = []
        host['channels_enabled'] = []
        channels = sorted(channels.result, key=lambda x: x['name'])
        for chan in channels:
            host['channels'].append(chan['name'])
            host['channels_id'].append(chan['id'])
            if chan['enabled']:
                host['channels_enabled'].append('enabled')
            else:
                host['channels_enabled'].append('disabled')

    if channel != 'all':
        hosts = [x for x in hosts if channel in x['channels']]
    else:
        channel = 'all'
    values['channel'] = channel

    values['channels'] = sorted(server.listChannels(), key=lambda x: x['name'])

    for host in hosts:
        host['last_update'] = koji.formatTimeLong(host['update_ts'])

    # Paginate after retrieving last update info so we can sort on it
    kojiweb.util.paginateList(values, hosts, start, 'hosts', 'host', order)

    values['zip'] = zip  # TODO FIXME

    return _genHTML(environ, 'hosts.html.j2', jinja=True)


def hostinfo(environ, hostID=None, userID=None):
    values = _initValues(environ, 'Host Info', 'hosts')
    server = _getServer(environ)

    if hostID:
        hostID = _convert_if_int(hostID)
        host = server.getHost(hostID)
        if host is None:
            raise koji.GenericError('No such host ID: %s' % hostID)
    elif userID:
        userID = _convert_if_int(userID)
        hosts = server.listHosts(userID=userID)
        host = None
        if hosts:
            host = hosts[0]
        if host is None:
            raise koji.GenericError('No such host for user ID: %s' % userID)
    else:
        raise koji.GenericError('hostID or userID must be provided')

    values['title'] = host['name'] + ' | Host Info'

    channels = server.listChannels(host['id'])
    channels.sort(key=_sortbyname)
    for chan in channels:
        if chan['enabled']:
            chan['enabled'] = 'enabled'
        else:
            chan['enabled'] = 'disabled'
    buildroots = server.listBuildroots(hostID=host['id'],
                                       state=[state[1] for state in koji.BR_STATES.items()
                                              if state[0] != 'EXPIRED'])
    buildroots.sort(key=lambda x: x['create_event_time'], reverse=True)

    values['host'] = host
    values['channels'] = channels
    values['buildroots'] = buildroots
    values['lastUpdate'] = koji.formatTimeLong(host['update_ts'])
    if environ['koji.currentUser']:
        values['perms'] = server.getUserPerms(environ['koji.currentUser']['id'])
    else:
        values['perms'] = []

    return _genHTML(environ, 'hostinfo.html.j2', jinja=2)


def hostedit(environ, hostID):
    server = _getServer(environ)
    _assertLogin(environ)

    hostID = int(hostID)
    host = server.getHost(hostID)
    if host is None:
        raise koji.GenericError('no host with ID: %i' % hostID)

    form = environ['koji.form']

    if 'save' in form:
        arches = form['arches'].value
        capacity = float(form['capacity'].value)
        description = form['description'].value
        comment = form['comment'].value
        enabled = bool('enabled' in form)
        channels = form.getlist('channels')

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

        _redirect(environ, 'hostinfo?hostID=%i' % host['id'])
    elif 'cancel' in form:
        _redirect(environ, 'hostinfo?hostID=%i' % host['id'])
    else:
        values = _initValues(environ, 'Edit Host', 'hosts')

        values['host'] = host
        allChannels = server.listChannels()
        allChannels.sort(key=_sortbyname)
        values['allChannels'] = allChannels
        values['hostChannels'] = server.listChannels(hostID=host['id'])

        return _genHTML(environ, 'hostedit.html.j2', jinja=True)


def disablehost(environ, hostID):
    server = _getServer(environ)
    _assertLogin(environ)

    hostID = int(hostID)
    host = server.getHost(hostID, strict=True)
    server.disableHost(host['name'])

    _redirect(environ, 'hostinfo?hostID=%i' % host['id'])


def enablehost(environ, hostID):
    server = _getServer(environ)
    _assertLogin(environ)

    hostID = int(hostID)
    host = server.getHost(hostID, strict=True)
    server.enableHost(host['name'])

    _redirect(environ, 'hostinfo?hostID=%i' % host['id'])


def channelinfo(environ, channelID):
    values = _initValues(environ, 'Channel Info', 'hosts')
    server = _getServer(environ)

    channelID = int(channelID)
    channel = server.getChannel(channelID)
    print(channel)
    if channel is None:
        raise koji.GenericError('No such channel ID: %i' % channelID)

    values['title'] = channel['name'] + ' | Channel Info'

    states = [koji.TASK_STATES[s] for s in ('FREE', 'OPEN', 'ASSIGNED')]
    values['taskCount'] = \
        server.listTasks(opts={'channel_id': channelID, 'state': states},
                         queryOpts={'countOnly': True})

    hosts = server.listHosts(channelID=channelID)
    hosts.sort(key=_sortbyname)

    values['channel'] = channel
    values['hosts'] = hosts
    values['enabled_hosts'] = len([h for h in hosts if h['enabled']])
    values['ready_hosts'] = len([h for h in hosts if h['ready']])

    return _genHTML(environ, 'channelinfo.html.j2', jinja=True)


def buildrootinfo(environ, buildrootID):
    values = _initValues(environ, 'Buildroot Info', 'hosts')
    server = _getServer(environ)

    buildrootID = int(buildrootID)
    buildroot = server.getBuildroot(buildrootID)

    if buildroot is None:
        raise koji.GenericError('unknown buildroot ID: %i' % buildrootID)

    elif buildroot['br_type'] == koji.BR_TYPES['STANDARD']:
        template = 'buildrootinfo.html.j2'
        values['task'] = server.getTaskInfo(buildroot['task_id'], request=True)

    else:
        template = 'buildrootinfo_cg.html.j2'
        # TODO - fetch tools and extras info

    values['title'] = '%s | Buildroot Info' % kojiweb.util.brLabel(buildroot)
    values['buildroot'] = buildroot
    values['koji'] = koji

    return _genHTML(environ, template, jinja=True)


def rpmlist(environ, type, buildrootID=None, imageID=None, start=None, order='nvr'):
    """
    rpmlist requires a buildrootID OR an imageID to be passed in. From one
    of these values it will paginate a list of rpms included in the
    corresponding object. (buildroot or image)
    """

    values = _initValues(environ, 'RPM List', 'hosts')
    server = _getServer(environ)

    if buildrootID is not None:
        buildrootID = int(buildrootID)
        buildroot = server.getBuildroot(buildrootID)
        values['buildroot'] = buildroot
        if buildroot is None:
            raise koji.GenericError('unknown buildroot ID: %i' % buildrootID)

        if type == 'component':
            kojiweb.util.paginateMethod(server, values, 'listRPMs',
                                        kw={'componentBuildrootID': buildroot['id']},
                                        start=start, dataName='rpms',
                                        prefix='rpm', order=order)
        elif type == 'built':
            kojiweb.util.paginateMethod(server, values, 'listRPMs',
                                        kw={'buildrootID': buildroot['id']},
                                        start=start, dataName='rpms',
                                        prefix='rpm', order=order)
        else:
            raise koji.GenericError('unrecognized type of rpmlist')

    elif imageID is not None:
        imageID = int(imageID)
        image = server.getArchive(imageID)
        values['image'] = image
        if image is None:
            raise koji.GenericError('unknown image ID: %i' % imageID)
        # If/When future image types are supported, add elifs here if needed.
        if type == 'image':
            kojiweb.util.paginateMethod(server, values, 'listRPMs',
                                        kw={'imageID': imageID},
                                        start=start, dataName='rpms',
                                        prefix='rpm', order=order)
        else:
            raise koji.GenericError('unrecognized type of image rpmlist')

    else:
        # It is an error if neither buildrootID and imageID are defined.
        raise koji.GenericError('Both buildrootID and imageID are None')

    values['type'] = type
    values['order'] = order

    return _genHTML(environ, 'rpmlist.html.j2', jinja=True)


def archivelist(environ, type, buildrootID=None, imageID=None, start=None, order='filename'):
    values = _initValues(environ, 'Archive List', 'hosts')
    server = _getServer(environ)

    if buildrootID is not None:
        buildrootID = int(buildrootID)
        buildroot = server.getBuildroot(buildrootID)
        values['buildroot'] = buildroot

        if buildroot is None:
            raise koji.GenericError('unknown buildroot ID: %i' % buildrootID)

        if type == 'component':
            kojiweb.util.paginateMethod(server, values, 'listArchives',
                                        kw={'componentBuildrootID': buildroot['id']},
                                        start=start, dataName='archives', prefix='archive',
                                        order=order)
        elif type == 'built':
            kojiweb.util.paginateMethod(server, values, 'listArchives',
                                        kw={'buildrootID': buildroot['id']},
                                        start=start, dataName='archives', prefix='archive',
                                        order=order)
        else:
            raise koji.GenericError('unrecognized type of archivelist')
    elif imageID is not None:
        imageID = int(imageID)
        image = server.getArchive(imageID)
        values['image'] = image
        if image is None:
            raise koji.GenericError('unknown image ID: %i' % imageID)
        # If/When future image types are supported, add elifs here if needed.
        if type == 'image':
            kojiweb.util.paginateMethod(server, values, 'listArchives', kw={'imageID': imageID},
                                        start=start, dataName='archives', prefix='archive',
                                        order=order)
        else:
            raise koji.GenericError('unrecognized type of image archivelist')
    else:
        # It is an error if neither buildrootID and imageID are defined.
        raise koji.GenericError('Both buildrootID and imageID are None')

    values['type'] = type
    values['order'] = order

    return _genHTML(environ, 'archivelist.html.j2', jinja=True)


def buildtargets(environ, start=None, order='name'):
    values = _initValues(environ, 'Build Targets', 'buildtargets')
    server = _getServer(environ)

    kojiweb.util.paginateMethod(server, values, 'getBuildTargets',
                                start=start, dataName='targets', prefix='target', order=order)

    values['order'] = order
    if environ['koji.currentUser']:
        values['perms'] = server.getUserPerms(environ['koji.currentUser']['id'])
    else:
        values['perms'] = []

    return _genHTML(environ, 'buildtargets.html.j2', jinja=True)


def buildtargetinfo(environ, targetID=None, name=None):
    values = _initValues(environ, 'Build Target Info', 'buildtargets')
    server = _getServer(environ)

    target = None
    if targetID is not None:
        targetID = int(targetID)
        target = server.getBuildTarget(targetID)
    elif name is not None:
        target = server.getBuildTarget(name)

    if target is None:
        raise koji.GenericError('No such build target: %s' % (targetID or name))

    values['title'] = target['name'] + ' | Build Target Info'

    buildTag = server.getTag(target['build_tag'])
    destTag = server.getTag(target['dest_tag'])

    values['target'] = target
    values['buildTag'] = buildTag
    values['destTag'] = destTag
    if environ['koji.currentUser']:
        values['perms'] = server.getUserPerms(environ['koji.currentUser']['id'])
    else:
        values['perms'] = []

    return _genHTML(environ, 'buildtargetinfo.html.j2', jinja=True)


def buildtargetedit(environ, targetID):
    server = _getServer(environ)
    _assertLogin(environ)

    targetID = int(targetID)

    target = server.getBuildTarget(targetID)
    if target is None:
        raise koji.GenericError('No such build target: %s' % targetID)

    form = environ['koji.form']

    if 'save' in form:
        name = form.getfirst('name')
        buildTagID = int(form.getfirst('buildTag'))
        buildTag = server.getTag(buildTagID)
        if buildTag is None:
            raise koji.GenericError('No such tag ID: %i' % buildTagID)

        destTagID = int(form.getfirst('destTag'))
        destTag = server.getTag(destTagID)
        if destTag is None:
            raise koji.GenericError('No such tag ID: %i' % destTagID)

        server.editBuildTarget(target['id'], name, buildTag['id'], destTag['id'])

        _redirect(environ, 'buildtargetinfo?targetID=%i' % target['id'])
    elif 'cancel' in form:
        _redirect(environ, 'buildtargetinfo?targetID=%i' % target['id'])
    else:
        values = _initValues(environ, 'Edit Build Target', 'buildtargets')
        tags = server.listTags()
        tags.sort(key=_sortbyname)

        values['target'] = target
        values['tags'] = tags

        return _genHTML(environ, 'buildtargetedit.html.j2', jinja=True)


def buildtargetcreate(environ):
    server = _getServer(environ)
    _assertLogin(environ)

    form = environ['koji.form']

    if 'add' in form:
        # Use the str .value field of the StringField object,
        # since xmlrpclib doesn't know how to marshal the StringFields
        # returned by mod_python
        name = form.getfirst('name')
        buildTagID = int(form.getfirst('buildTag'))
        destTagID = int(form.getfirst('destTag'))

        server.createBuildTarget(name, buildTagID, destTagID)
        target = server.getBuildTarget(name)

        if target is None:
            raise koji.GenericError('error creating build target "%s"' % name)

        _redirect(environ, 'buildtargetinfo?targetID=%i' % target['id'])
    elif 'cancel' in form:
        _redirect(environ, 'buildtargets')
    else:
        values = _initValues(environ, 'Add Build Target', 'builtargets')

        tags = server.listTags()
        tags.sort(key=_sortbyname)

        values['target'] = None
        values['tags'] = tags

        return _genHTML(environ, 'buildtargetedit.html.j2')


def buildtargetdelete(environ, targetID):
    server = _getServer(environ)
    _assertLogin(environ)

    targetID = int(targetID)

    target = server.getBuildTarget(targetID)
    if target is None:
        raise koji.GenericError('No such build target: %i' % targetID)

    server.deleteBuildTarget(target['id'])

    _redirect(environ, 'buildtargets')


def reports(environ):
    _getServer(environ)
    values = _initValues(environ, 'Reports', 'reports')
    if environ['koji.currentUser']:
        values['loggedInUser'] = True
    else:
        values['loggedInUser'] = False
    return _genHTML(environ, 'reports.html.j2', jinja=True)


def buildsbyuser(environ, start=None, order='-builds'):
    values = _initValues(environ, 'Builds by User', 'reports')
    server = _getServer(environ)

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

    return _genHTML(environ, 'buildsbyuser.html.j2', jinja=True)


def rpmsbyhost(environ, start=None, order=None, hostArch=None, rpmArch=None):
    values = _initValues(environ, 'RPMs by Host', 'reports')
    server = _getServer(environ)

    hostArch = _validate_arch(hostArch)
    rpmArch = _validate_arch(rpmArch)

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
    hostArchList = sorted(server.getAllArches())
    values['hostArchList'] = hostArchList
    values['rpmArch'] = rpmArch
    values['rpmArchList'] = hostArchList + ['noarch', 'src']

    if order is None:
        order = '-rpms'
    values['order'] = order

    graphWidth = 400.0
    values['graphWidth'] = graphWidth
    values['maxRPMs'] = maxRPMs
    values['increment'] = graphWidth / maxRPMs
    kojiweb.util.paginateList(values, hosts, start, 'hosts', 'host', order)

    return _genHTML(environ, 'rpmsbyhost.html.j2', jinja=True)


def packagesbyuser(environ, start=None, order=None):
    values = _initValues(environ, 'Packages by User', 'reports')
    server = _getServer(environ)

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

    if order is None:
        order = '-packages'
    values['order'] = order

    graphWidth = 400.0
    values['graphWidth'] = graphWidth
    values['maxPackages'] = maxPackages
    values['increment'] = graphWidth / maxPackages
    kojiweb.util.paginateList(values, users, start, 'users', 'user', order)

    return _genHTML(environ, 'packagesbyuser.html.j2', jinja=True)


def tasksbyhost(environ, start=None, order='-tasks', hostArch=None):
    values = _initValues(environ, 'Tasks by Host', 'reports')
    server = _getServer(environ)

    maxTasks = 1

    hostArch = _validate_arch(hostArch)
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
    hostArchList = sorted(server.getAllArches())
    values['hostArchList'] = hostArchList

    values['order'] = order

    graphWidth = 400.0
    values['graphWidth'] = graphWidth
    values['maxTasks'] = maxTasks
    values['increment'] = graphWidth / maxTasks
    kojiweb.util.paginateList(values, hosts, start, 'hosts', 'host', order)

    return _genHTML(environ, 'tasksbyhost.html.j2', jinja=True)


def tasksbyuser(environ, start=None, order='-tasks'):
    values = _initValues(environ, 'Tasks by User', 'reports')
    server = _getServer(environ)

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

    return _genHTML(environ, 'tasksbyuser.html.j2', jinja=True)


def buildsbystatus(environ, days='7'):
    values = _initValues(environ, 'Builds by Status', 'reports')
    server = _getServer(environ)

    days = int(days)
    if days != -1:
        seconds = 60 * 60 * 24 * days
        dateAfter = time.time() - seconds
    else:
        dateAfter = None
    values['days'] = days

    server.multicall = True
    # use taskID=-1 to filter out builds with a null task_id (imported rather than built in koji)
    server.listBuilds(completeAfter=dateAfter, state=koji.BUILD_STATES['COMPLETE'], taskID=-1,
                      queryOpts={'countOnly': True})
    server.listBuilds(completeAfter=dateAfter, state=koji.BUILD_STATES['FAILED'], taskID=-1,
                      queryOpts={'countOnly': True})
    server.listBuilds(completeAfter=dateAfter, state=koji.BUILD_STATES['CANCELED'], taskID=-1,
                      queryOpts={'countOnly': True})
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

    return _genHTML(environ, 'buildsbystatus.html.j2', jinja=True)


def buildsbytarget(environ, days='7', start=None, order='-builds'):
    values = _initValues(environ, 'Builds by Target', 'reports')
    server = _getServer(environ)

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

    kojiweb.util.paginateList(values, list(targets.values()), start, 'targets', 'target', order)

    values['order'] = order

    graphWidth = 400.0
    values['graphWidth'] = graphWidth
    values['maxBuilds'] = maxBuilds
    values['increment'] = graphWidth / maxBuilds

    return _genHTML(environ, 'buildsbytarget.html.j2', jinja=True)


def _filter_hosts_by_arch(hosts, arch):
    if arch == '__all__':
        return hosts
    else:
        return [h for h in hosts if arch in h['arches'].split()]


def clusterhealth(environ, arch='__all__'):
    arch = _validate_arch(arch)
    values = _initValues(environ, 'Cluster health', 'reports')
    server = _getServer(environ)
    channels = server.listChannels()
    server.multicall = True
    for channel in channels:
        server.listHosts(channelID=channel['id'])
    max_enabled = 0
    max_capacity = 0
    arches = set()
    for channel, [hosts] in zip(channels, server.multiCall()):
        for host in hosts:
            arches |= set(host['arches'].split())
        hosts = _filter_hosts_by_arch(hosts, arch)
        channel['enabled_channel'] = channel['enabled']
        channel['enabled'] = len([x for x in hosts if x['enabled']])
        channel['disabled'] = len(hosts) - channel['enabled']
        channel['ready'] = len([x for x in hosts if x['ready']])
        channel['capacity'] = sum([x['capacity'] for x in hosts])
        channel['load'] = sum([x['task_load'] for x in hosts])
        if max_enabled < channel['enabled']:
            max_enabled = channel['enabled']
        if max_capacity < channel['capacity']:
            max_capacity = channel['capacity']

    graphWidth = 400.0
    # compute values for channels
    for channel in channels:
        try:
            channel['capacityPerc'] = channel['capacity'] / max_capacity * 100
        except ZeroDivisionError:
            channel['capacityPerc'] = 0
        try:
            channel['enabledPerc'] = channel['enabled'] / max_enabled * 100
        except ZeroDivisionError:
            channel['enabledPerc'] = 0
        if channel['capacity']:
            channel['perc_load'] = min(100, channel['load'] / channel['capacity'] * 100)
        else:
            channel['perc_load'] = 0.0
        if channel['enabled']:
            channel['perc_ready'] = min(100, channel['ready'] / channel['enabled'] * 100)
        else:
            channel['perc_ready'] = 0.0

    values['arch'] = arch
    values['arches'] = sorted(arches)
    values['graphWidth'] = graphWidth
    values['channels'] = sorted(channels, key=lambda x: x['name'])
    return _genHTML(environ, 'clusterhealth.html.j2', jinja=True)


def recentbuilds(environ, user=None, tag=None, package=None):
    values = _initValues(environ, 'Recent Build RSS')
    server = _getServer(environ)

    tagObj = None
    if tag is not None:
        tag = _convert_if_int(tag)
        tagObj = server.getTag(tag, strict=True)

    userObj = None
    if user is not None:
        user = _convert_if_int(user)
        userObj = server.getUser(user, strict=True)

    packageObj = None
    if package:
        package = _convert_if_int(package)
        packageObj = server.getPackage(package, strict=True)

    if tagObj is not None:
        builds = server.listTagged(tagObj['id'], inherit=True,
                                   package=(packageObj and packageObj['name'] or None),
                                   owner=(userObj and userObj['name'] or None))
        builds.sort(key=kojiweb.util.sortByKeyFuncNoneGreatest('completion_time'), reverse=True)
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
        task_id = extract_build_task(build)
        if task_id:
            server.getTaskInfo(task_id, request=True)
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
    values['weburl'] = _getBaseURL(environ)

    values['koji'] = koji

    environ['koji.headers'].append(['Content-Type', 'text/xml'])
    return _genHTML(environ, 'recentbuilds.html.j2', jinja=True)


_infoURLs = {'package': 'packageinfo?packageID=%(id)i',
             'build': 'buildinfo?buildID=%(id)i',
             'tag': 'taginfo?tagID=%(id)i',
             'target': 'buildtargetinfo?targetID=%(id)i',
             'user': 'userinfo?userID=%(id)i',
             'host': 'hostinfo?hostID=%(id)i',
             'rpm': 'rpminfo?rpmID=%(id)i',
             'maven': 'archiveinfo?archiveID=%(id)i',
             'win': 'archiveinfo?archiveID=%(id)i'}

_DEFAULT_SEARCH_ORDER = {
    # For searches against large tables, use '-id' to show most recent first
    'build': '-id',
    'rpm': '-id',
    'maven': '-id',
    'win': '-id',
    # for other tables, ordering by name makes much more sense
    'tag': 'name',
    'target': 'name',
    'package': 'name',
    # any type not listed will default to 'name'
}


def search(environ, start=None, order=None):
    if start is not None:
        start = int(start)
    values = _initValues(environ, 'Search', 'search')
    server = _getServer(environ)
    values['error'] = None

    form = environ['koji.form']
    if 'terms' in form and form['terms'].value:
        terms = form['terms'].value
        terms = terms.strip()
        type = form['type'].value
        match = form['match'].value
        values['terms'] = terms
        values['type'] = type
        values['match'] = match

        if match not in ('glob', 'regexp', 'exact'):
            raise koji.GenericError("No such match type: %r" % match)

        if match == 'regexp':
            try:
                re.compile(terms)
            except Exception:
                values['error'] = 'Invalid regular expression'
                values['terms'] = ''
                return _genHTML(environ, 'search.html.j2')

        infoURL = _infoURLs.get(type)
        if not infoURL:
            raise koji.GenericError('unknown search type: %s' % type)
        values['infoURL'] = infoURL
        order = order or _DEFAULT_SEARCH_ORDER.get(type, 'name')
        values['order'] = order

        results = kojiweb.util.paginateMethod(server, values, 'search', args=(terms, type, match),
                                              start=start, dataName='results', prefix='result',
                                              order=order)
        if not start and len(results) == 1:
            # if we found exactly one result, skip the result list and redirect to the info page
            # (you're feeling lucky)
            _redirect(environ, infoURL % results[0])
        else:
            if type == 'maven':
                typeLabel = 'Maven artifacts'
            elif type == 'win':
                typeLabel = 'Windows artifacts'
            else:
                typeLabel = '%ss' % type
            values['typeLabel'] = typeLabel
            return _genHTML(environ, 'search.html.j2', jinja=True)
    else:
        return _genHTML(environ, 'search.html.j2', jinja=True)


def api(environ):
    values = _initValues(environ, 'API', 'api')
    server = _getServer(environ)

    values['koji_hub_url'] = environ['koji.options']['KojiHubURL']
    values['methods'] = sorted(server._listapi(), key=lambda x: x['name'])
    values['web_version'] = koji.__version__
    try:
        values['koji_version'] = server.getKojiVersion()
    except koji.GenericError:
        values['koji_version'] = "Can't determine (older then 1.23)"

    return _genHTML(environ, 'api.html.j2', jinja=True)


def watchlogs(environ, taskID):
    values = _initValues(environ)
    if isinstance(taskID, list):
        values['tasks'] = ', '.join([int(x) for x in taskID])
    else:
        values['tasks'] = int(taskID)

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


def repoinfo(environ, repoID):
    values = _initValues(environ, 'Repo Info', 'tags')
    server = _getServer(environ)

    values['repo_id'] = repoID
    repoID = _convert_if_int(repoID)
    repo_info = server.repoInfo(repoID, strict=False)
    values['repo'] = repo_info
    if repo_info:
        topurl = environ['koji.options']['KojiFilesURL']
        pathinfo = koji.PathInfo(topdir=topurl)
        if repo_info['dist']:
            values['url'] = pathinfo.distrepo(repo_info['id'], repo_info['tag_name'])
        else:
            values['url'] = pathinfo.repo(repo_info['id'], repo_info['tag_name'])
        if repo_info['dist']:
            values['repo_json'] = os.path.join(
                pathinfo.distrepo(repo_info['id'], repo_info['tag_name']), 'repo.json')
        else:
            values['repo_json'] = os.path.join(
                pathinfo.repo(repo_info['id'], repo_info['tag_name']), 'repo.json')
    num_buildroots = len(server.listBuildroots(repoID=repoID)) or 0
    values['numBuildroots'] = num_buildroots
    values['state_name'] = kojiweb.util.repoState(repo_info['state'])
    values['create_time'] = kojiweb.util.formatTimeLong(repo_info['create_ts'])
    return _genHTML(environ, 'repoinfo.html.j2', jinja=True)


def activesession(environ, start=None, order=None):
    values = _initValues(environ, 'Active sessions', 'activesession')
    server = _getServer(environ)

    values['loggedInUser'] = environ['koji.currentUser']

    values['order'] = order
    activesess = []
    if environ['koji.currentUser']:
        activesess = server.getSessionInfo(details=True, user_id=values['loggedInUser']['id'])
    if activesess:
        current_timestamp = datetime.datetime.utcnow().timestamp()
        for a in activesess:
            a['lengthSession'] = kojiweb.util.formatTimestampDifference(
                a['start_time'], current_timestamp, in_days=True)

    kojiweb.util.paginateList(values, activesess, start, 'activesess', order=order)

    return _genHTML(environ, 'activesession.html.j2', jinja=True)


def activesessiondelete(environ, sessionID):
    server = _getServer(environ)
    _assertLogin(environ)

    sessionID = int(sessionID)

    server.logout(session_id=sessionID)

    _redirect(environ, 'activesession')


def buildroots(environ, repoID=None, order='id', start=None, state=None):
    values = _initValues(environ, 'Buildroots', 'buildroots')
    server = _getServer(environ)
    values['repoID'] = repoID
    values['order'] = order
    if state == 'all':
        state = None
    elif state is not None:
        state = int(state)
    values['state'] = state

    kojiweb.util.paginateMethod(server, values, 'listBuildroots',
                                kw={'repoID': repoID, 'state': state}, start=start,
                                dataName='buildroots', prefix='buildroot', order=order)

    values['koji'] = koji

    return _genHTML(environ, 'buildroots.html.j2', jinja=True)
