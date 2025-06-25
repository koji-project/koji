# authentication module
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
#       Mike Bonnet <mikeb@redhat.com>

from __future__ import absolute_import

import logging
import random
import re
import socket
import string
import time

import six
from six.moves import range, urllib
import koji
from koji.context import context
from koji.util import to_list

from .db import DeleteProcessor, InsertProcessor, QueryProcessor, UpdateProcessor, nextval


# 1 - load session if provided
#       - check uri for session id
#       - load session info from db
#       - validate session
# 2 - create a session
#       - maybe in two steps
#       -


RetryWhitelist = [
    'host.taskWait',
    'host.taskUnwait',
    'host.taskSetWait',
    'host.updateHost',
    'host.setBuildRootState',
    'repoExpire',
    'repoDelete',
    'repoProblem',
]

AUTH_METHODS = ['login', 'sslLogin']

logger = logging.getLogger('koji.auth')


class Session(object):

    def __init__(self, args=None, hostip=None):
        self.logged_in = False
        self.id = None
        self.master = None
        self.key = None
        self.user_id = None
        self.authtype = None
        self.hostip = None
        self.user_data = {}
        self.message = ''
        self.exclusive = False
        self.lockerror = None
        self.callnum = callnum = None
        # we look up perms, groups, and host_id on demand, see __getattr__
        self._perms = None
        self._groups = None
        self._host_id = ''
        environ = getattr(context, 'environ', {})
        args = environ.get('QUERY_STRING', '')
        # prefer new header-based sessions
        if 'HTTP_KOJI_SESSION_ID' in environ:
            self.id = int(environ['HTTP_KOJI_SESSION_ID'])
            self.key = environ['HTTP_KOJI_SESSION_KEY']
            try:
                if 'HTTP_KOJI_SESSION_CALLNUM' in environ:
                    # this is the field that the koji client has sent since 1.31
                    callnum = int(environ['HTTP_KOJI_SESSION_CALLNUM'])
                else:
                    # before 1.35, the hub was mistakenly checking this field
                    # we still accept it for backwards compatibility
                    callnum = int(environ['HTTP_KOJI_CALLNUM'])
            except KeyError:
                callnum = None
        elif not context.opts['DisableURLSessions'] and args is not None:
            # old deprecated method with session values in query string
            # Option will be turned off by default in future release and removed later
            if not args:
                self.message = 'no session header or session args'
                return
            args = urllib.parse.parse_qs(args, strict_parsing=True)
            try:
                self.id = int(args['session-id'][0])
                self.key = args['session-key'][0]
            except KeyError as field:
                raise koji.AuthError('%s not specified in session args' % field)
            try:
                callnum = args['callnum'][0]
            except Exception:
                callnum = None
        else:
            self.message = 'no Koji-Session-* headers'
            return
        hostip = self.get_remote_ip(override=hostip)
        # lookup the session
        # sort for stability (unittests)

        fields = (('authtype', 'authtype'), ('callnum', 'callnum'), ('exclusive', 'exclusive'),
                  ('expired', 'expired'), ('master', 'master'), ('start_time', 'start_time'),
                  ('update_time', 'update_time'), ("date_part('epoch', start_time)", 'start_ts'),
                  ("date_part('epoch', update_time)", 'update_ts'), ('user_id', 'user_id'),
                  ('renew_time', 'renew_time'), ("date_part('epoch', renew_time)", 'renew_ts'))
        columns, aliases = zip(*fields)

        query = QueryProcessor(tables=['sessions'], columns=columns, aliases=aliases,
                               clauses=['id = %(id)i', 'key = %(key)s', 'hostip = %(hostip)s',
                                        'closed IS FALSE'],
                               values={'id': self.id, 'key': self.key, 'hostip': hostip},
                               opts={'rowlock': True})
        session_data = query.executeOne(strict=False)
        if not session_data:
            query = QueryProcessor(tables=['sessions'], columns=['key', 'hostip'],
                                   clauses=['id = %(id)i'], values={'id': self.id})
            row = query.executeOne(strict=False)
            if row:
                if self.key != row['key']:
                    logger.warning("Session ID %s is not related to session key %s.",
                                   self.id, self.key)
                elif hostip != row['hostip']:
                    logger.warning("Session ID %s is not related to host IP %s.", self.id, hostip)
            raise koji.AuthError('Invalid session or bad credentials')

        if not session_data['expired'] and context.opts['SessionRenewalTimeout'] != 0:
            if session_data['renew_ts']:
                renewal_cutoff = (session_data['renew_ts'] +
                                  context.opts['SessionRenewalTimeout'] * 60)
            else:
                renewal_cutoff = (session_data['start_ts'] +
                                  context.opts['SessionRenewalTimeout'] * 60)
            if time.time() > renewal_cutoff:
                session_data['expired'] = True
                update = UpdateProcessor('sessions',
                                         data={'expired': True},
                                         clauses=['id = %(id)s OR master = %(id)s'],
                                         values={'id': self.id})
                update.execute()
                context.cnx.commit()

        if session_data['expired']:
            if getattr(context, 'method') not in AUTH_METHODS:
                raise koji.AuthExpired('session "%s" has expired' % self.id)

        # check for callnum sanity
        if callnum is not None:
            try:
                callnum = int(callnum)
            except (ValueError, TypeError):
                raise koji.AuthError("Invalid callnum: %r" % callnum)
            lastcall = session_data['callnum']
            if lastcall is not None:
                if lastcall > callnum:
                    raise koji.SequenceError("%s > %s (session %s)" % (lastcall, callnum, self.id))
                elif lastcall == callnum:
                    # Some explanation:
                    # This function is one of the few that performs its own commit.
                    # However, our storage of the current callnum is /after/ that
                    # commit. This means the the current callnum only gets committed if
                    # a commit happens afterward.
                    # We only schedule a commit for dml operations, so if we find the
                    # callnum in the db then a previous attempt succeeded but failed to
                    # return. Data was changed, so we cannot simply try the call again.
                    method = getattr(context, 'method', 'UNKNOWN')
                    if method not in RetryWhitelist:
                        raise koji.RetryError(
                            "unable to retry call %s (method %s) for session %s" %
                            (callnum, method, self.id))

        if session_data['expired']:
            return

        # read user data
        # historical note:
        # we used to get a row lock here as an attempt to maintain sanity of exclusive
        # sessions, but it was an imperfect approach and the lock could cause some
        # performance issues.
        query = QueryProcessor(tables=['users'], columns=['name', 'status', 'usertype'],
                               clauses=['id=%(user_id)s'],
                               values={'user_id': session_data['user_id']})
        user_data = query.executeOne()

        if user_data['status'] != koji.USER_STATUS['NORMAL']:
            raise koji.AuthError('logins by %s are not allowed' % user_data['name'])
        # check for exclusive sessions
        if session_data['exclusive']:
            # we are the exclusive session for this user
            self.exclusive = True
        else:
            # see if an exclusive session exists
            query = QueryProcessor(tables=['sessions'], columns=['id'],
                                   clauses=['user_id=%(user_id)s', 'exclusive = TRUE',
                                            'closed = FALSE'],
                                   values=session_data)
            excl_id = query.singleValue(strict=False)

            if excl_id:
                if excl_id == session_data['master']:
                    # (note excl_id cannot be None)
                    # our master session has the lock
                    self.exclusive = True
                else:
                    # a session unrelated to us has the lock
                    self.lockerror = "User locked by another session"
                    # we don't enforce here, but rely on the dispatcher to enforce
                    # if appropriate (otherwise it would be impossible to steal
                    # an exclusive session with the force option).

        # update timestamp
        update = UpdateProcessor('sessions', rawdata={'update_time': 'NOW()'},
                                 clauses=['id = %(id)i'], values={'id': self.id})
        update.execute()
        context.cnx.commit()
        # update callnum (this is deliberately after the commit)
        # see earlier note near RetryError
        if callnum is not None:
            update = UpdateProcessor('sessions', data={'callnum': callnum},
                                     clauses=['id = %(id)i'], values={'id': self.id})
            update.execute()
            # we only want to commit the callnum change if there are other commits
            context.commit_pending = False

        # record the login data
        self.hostip = hostip
        self.callnum = callnum
        self.user_id = session_data['user_id']
        self.authtype = session_data['authtype']
        self.master = session_data['master']
        self.session_data = session_data
        self.user_data = user_data
        self.logged_in = True

    def __getattr__(self, name):
        # grab perm and groups data on the fly
        if name == 'perms':
            if self._perms is None:
                # in a dict for quicker lookup
                self._perms = dict([[name, 1] for name in get_user_perms(self.user_id)])
            return self._perms
        elif name == 'groups':
            if self._groups is None:
                self._groups = get_user_groups(self.user_id)
            return self._groups
        elif name == 'host_id':
            if self._host_id == '':
                self._host_id = self._getHostId()
            return self._host_id
        else:
            raise AttributeError("%s" % name)

    def __str__(self):
        # convenient display for debugging
        if not self.logged_in:
            s = "session: not logged in"
        else:
            s = "session %d: %r" % (self.id, self.__dict__)
        if self.message:
            s += " (%s)" % self.message
        return s

    def validate(self):
        if self.lockerror:
            raise koji.AuthLockError(self.lockerror)
        return True

    def get_remote_ip(self, override=None):
        if not context.opts['CheckClientIP']:
            return '-'
        elif override is not None:
            return override
        else:
            hostip = context.environ['REMOTE_ADDR']
            # XXX - REMOTE_ADDR not promised by wsgi spec
            if hostip == '127.0.0.1':
                hostip = socket.gethostbyname(socket.gethostname())
            return hostip

    def checkLoginAllowed(self, user_id):
        """Verify that the user is allowed to login"""
        query = QueryProcessor(tables=['users'], columns=['name', 'usertype', 'status'],
                               clauses=['id = %(user_id)i'], values={'user_id': user_id})
        result = query.executeOne(strict=False)
        if not result:
            raise koji.AuthError('invalid user_id: %s' % user_id)

        if result['status'] != koji.USER_STATUS['NORMAL']:
            raise koji.AuthError('logins by %s are not allowed' % result['name'])

    def login(self, user, password, opts=None, renew=False, exclusive=False):
        """create a login session"""
        if opts is None:
            opts = {}
        if not isinstance(password, str) or len(password) == 0:
            raise koji.AuthError('invalid username or password')
        if self.logged_in:
            raise koji.AuthError("Already logged in")
        hostip = self.get_remote_ip(override=opts.get('hostip'))

        # check passwd
        query = QueryProcessor(tables=['users'], columns=['id'],
                               clauses=['name = %(user)s', 'password = %(password)s'],
                               values={'user': user, 'password': password})
        user_id = query.singleValue(strict=False)
        if not user_id:
            raise koji.AuthError('invalid username or password')

        self.checkLoginAllowed(user_id)

        # create session and return
        sinfo = self.createSession(user_id, hostip, koji.AUTHTYPES['NORMAL'], renew=renew)
        if sinfo and exclusive and not self.exclusive:
            self.makeExclusive()
        context.cnx.commit()
        return sinfo

    def getConnInfo(self):
        """Return a tuple containing connection information
        in the following format:
        (local ip addr, local port, remote ip, remote port)"""
        # For some reason req.connection.{local,remote}_addr contain port info,
        # but no IP info.  Use req.connection.{local,remote}_ip for that instead.
        # See: http://lists.planet-lab.org/pipermail/devel-community/2005-June/001084.html
        # local_ip seems to always be set to the same value as remote_ip,
        # so get the local ip via a different method
        local_ip = socket.gethostbyname(context.environ['SERVER_NAME'])
        remote_ip = context.environ['REMOTE_ADDR']
        # XXX - REMOTE_ADDR not promised by wsgi spec

        # it appears that calling setports() with *any* value results in authentication
        # failing with "Incorrect net address", so return 0 (which prevents
        # python-krbV from calling setports())
        local_port = 0
        remote_port = 0

        return (local_ip, local_port, remote_ip, remote_port)

    def sslLogin(self, proxyuser=None, proxyauthtype=None, renew=False, exclusive=None):

        """Login into brew via SSL. proxyuser name can be specified and if it is
        allowed in the configuration file then connection is allowed to login as
        that user. By default we assume that proxyuser is coming via same
        authentication mechanism but proxyauthtype can be set to koji.AUTHTYPE['*']
        value for different handling. Typical case is proxying kerberos user via
        web ui which itself is authenticated via SSL certificate. (See kojiweb
        for usage).

        proxyauthtype is working only if AllowProxyAuthType option is set to
        'On' in the hub.conf
        """
        if self.logged_in:
            raise koji.AuthError("Already logged in")

        # we use REMOTE_USER to identify user
        if context.environ.get('REMOTE_USER'):
            # it is kerberos principal rather than user's name.
            username = context.environ.get('REMOTE_USER')
            client_dn = username
            authtype = koji.AUTHTYPES['GSSAPI']
        else:
            if context.environ.get('SSL_CLIENT_VERIFY') != 'SUCCESS':
                raise koji.AuthError('could not verify client: %s' %
                                     context.environ.get('SSL_CLIENT_VERIFY'))

            name_dn_component = context.opts.get('DNUsernameComponent', 'CN')
            username = context.environ.get('SSL_CLIENT_S_DN_%s' % name_dn_component)
            if not username:
                raise koji.AuthError(
                    'unable to get user information (%s) from client certificate' %
                    name_dn_component)
            client_dn = context.environ.get('SSL_CLIENT_S_DN')
            authtype = koji.AUTHTYPES['SSL']

        if proxyuser:
            if authtype == koji.AUTHTYPES['GSSAPI']:
                delimiter = ','
                proxy_opt = 'ProxyPrincipals'
            else:
                delimiter = '|'
                proxy_opt = 'ProxyDNs'
            proxy_dns = [dn.strip() for dn in context.opts.get(proxy_opt, '').split(delimiter)]

            if client_dn in proxy_dns:
                # the user authorized to login other users
                username = proxyuser
            else:
                raise koji.AuthError('%s is not authorized to login other users' % client_dn)

            # in this point we can continue with proxied user in same way as if it is not proxied
            if proxyauthtype is not None:
                if not context.opts['AllowProxyAuthType'] and authtype != proxyauthtype:
                    raise koji.AuthError("Proxy must use same auth mechanism as hub (behaviour "
                                         "can be overriden via AllowProxyAuthType hub option)")
                if proxyauthtype not in (koji.AUTHTYPES['GSSAPI'], koji.AUTHTYPES['SSL']):
                    raise koji.AuthError(
                        "Proxied authtype %s is not valid for sslLogin" % proxyauthtype)
                authtype = proxyauthtype

        if authtype == koji.AUTHTYPES['GSSAPI'] and '@' in username:
            user_id = self.getUserIdFromKerberos(username)
        else:
            user_id = self.getUserId(username)
        if not user_id:
            if context.opts.get('LoginCreatesUser'):
                if authtype == koji.AUTHTYPES['GSSAPI'] and '@' in username:
                    user_id = self.createUserFromKerberos(username)
                else:
                    user_id = self.createUser(username)
            else:
                raise koji.AuthError('Unknown user: %s' % username)

        self.checkLoginAllowed(user_id)

        hostip = self.get_remote_ip()

        sinfo = self.createSession(user_id, hostip, authtype, renew=renew)
        if sinfo and exclusive and not self.exclusive:
            self.makeExclusive()
        return sinfo

    def makeExclusive(self, force=False):
        """Make this session exclusive"""
        if self.master is not None:
            raise koji.GenericError("subsessions cannot become exclusive")
        if self.exclusive:
            # shouldn't happen
            raise koji.GenericError("session is already exclusive")
        user_id = self.user_id
        session_id = self.id
        # acquire a row lock on the user entry
        query = QueryProcessor(tables=['users'], columns=['id'], clauses=['id=%(user_id)s'],
                               values={'user_id': user_id}, opts={'rowlock': True})
        query.execute()
        # check that no other sessions for this user are exclusive (including expired)
        query = QueryProcessor(tables=['sessions'], columns=['id'],
                               clauses=['user_id=%(user_id)s', 'closed = FALSE',
                                        'exclusive = TRUE'],
                               values={'user_id': user_id}, opts={'rowlock': True})
        excl_id = query.singleValue(strict=False)
        if excl_id:
            if force:
                # close the previous exclusive sessions and try again
                update = UpdateProcessor('sessions',
                                         data={'expired': True, 'exclusive': None, 'closed': True},
                                         clauses=['id=%(excl_id)s'], values={'excl_id': excl_id},)
                update.execute()
            else:
                raise koji.AuthLockError("Cannot get exclusive session")
        # mark this session exclusive
        update = UpdateProcessor('sessions', data={'exclusive': True},
                                 clauses=['id=%(session_id)s'], values={'session_id': session_id})
        update.execute()
        context.cnx.commit()

    def makeShared(self):
        """Drop out of exclusive mode"""
        session_id = self.id
        update = UpdateProcessor('sessions', data={'exclusive': None},
                                 clauses=['id=%(session_id)s'], values={'session_id': session_id})
        update.execute()
        context.cnx.commit()

    def logout(self, session_id=None):
        """close a login session"""
        if not self.logged_in:
            # XXX raise an error?
            raise koji.AuthError("Not logged in")

        if session_id:
            if not context.session.hasPerm('admin'):
                query = QueryProcessor(tables=['sessions'], columns=['id'],
                                       clauses=['user_id = %(user_id)i', 'id = %(session_id)s'],
                                       values={'user_id': self.user_id, 'session_id': session_id})
                if not query.singleValue():
                    raise koji.ActionNotAllowed('only admins or owner may logout other session')
            ses_id = session_id
        else:
            ses_id = self.id
        update = UpdateProcessor('sessions',
                                 data={'expired': True, 'exclusive': None, 'closed': True},
                                 clauses=['id = %(id)i OR master = %(id)i'],
                                 values={'id': ses_id})
        update.execute()
        context.cnx.commit()
        if not session_id:
            self.logged_in = False

    def logoutChild(self, session_id):
        """close a subsession"""
        if not self.logged_in:
            # XXX raise an error?
            raise koji.AuthError("Not logged in")
        update = UpdateProcessor('sessions',
                                 data={'expired': True, 'exclusive': None, 'closed': True},
                                 clauses=['id = %(session_id)i', 'master = %(master)i'],
                                 values={'session_id': session_id, 'master': self.id})
        update.execute()
        context.cnx.commit()

    def createSession(self, user_id, hostip, authtype, master=None, renew=False):
        """Create a new session for the given user.

        Return a map containing the session-id and session-key.
        If master is specified, create a subsession
        """
        # generate a random key
        alnum = string.ascii_letters + string.digits
        key = "%s-%s" % (user_id,
                         ''.join([random.choice(alnum) for x in range(1, 20)]))
        # use sha? sha.new(phrase).hexdigest()

        if renew and self.id is not None:
            # just update key
            session_id = self.id
            self.key = key
            if self.master:
                # check if master session died meanwhile (expired is ok)
                query = QueryProcessor(tables=['sessions'],
                                       clauses=['id = %(master_id)d', 'closed IS FALSE'],
                                       values={'master_id': self.master},
                                       opts={'countOnly': True})
                if query.executeOne() == 0:
                    return None

            update = UpdateProcessor('sessions',
                                     clauses=['id=%(id)i'],
                                     rawdata={'update_time': 'NOW()', 'renew_time': 'NOW()'},
                                     data={'key': self.key, 'expired': False},
                                     values={'id': self.id})
            update.execute()
        else:
            # get a session id
            session_id = nextval('sessions_id_seq')
            # add session id to database
            insert = InsertProcessor('sessions',
                                     data={'id': session_id, 'user_id': user_id, 'key': key,
                                           'hostip': hostip, 'authtype': authtype,
                                           'master': master})
            insert.execute()
        context.cnx.commit()

        # return session info
        return {
            'session-id': session_id,
            'session-key': key,
            'header-auth': True,  # signalize to client to use new session handling in 1.30
        }

    def subsession(self):
        "Create a subsession"
        if not self.logged_in:
            raise koji.AuthError("Not logged in")
        master = self.master
        if master is None:
            master = self.id
        return self.createSession(self.user_id, self.hostip, self.authtype, master=master)

    def getPerms(self):
        if not self.logged_in:
            return []
        return to_list(self.perms.keys())

    def hasPerm(self, name):
        if not self.logged_in:
            return False
        return name in self.perms

    def assertPerm(self, name):
        if not self.hasPerm(name) and not self.hasPerm('admin'):
            msg = "%s permission required" % name
            if self.logged_in:
                msg += ' (logged in as %s)' % self.user_data['name']
            else:
                msg += ' (user not logged in)'
            raise koji.ActionNotAllowed(msg)

    def assertLogin(self):
        if not self.logged_in:
            raise koji.ActionNotAllowed("you must be logged in for this operation")

    def hasGroup(self, group_id):
        if not self.logged_in:
            return False
        # groups indexed by id
        return group_id in self.groups

    def isUser(self, user_id):
        if not self.logged_in:
            return False
        return (self.user_id == user_id or self.hasGroup(user_id))

    def assertUser(self, user_id):
        if not self.isUser(user_id) and not self.hasPerm('admin'):
            raise koji.ActionNotAllowed("not owner")

    def _getHostId(self):
        '''Using session data, find host id (if there is one)'''
        if self.user_id is None:
            return None
        query = QueryProcessor(tables=['host'], columns=['id'], clauses=['user_id = %(uid)d'],
                               values={'uid': self.user_id})
        return query.singleValue(strict=False)

    def getHostId(self):
        # for compatibility
        return self.host_id

    def getUserId(self, username):
        """Return the user ID associated with a particular username. If no user
        with the given username if found, return None."""
        query = QueryProcessor(tables=['users'], columns=['id'], clauses=['name = %(username)s'],
                               values={'username': username})
        return query.singleValue(strict=False)

    def getUserIdFromKerberos(self, krb_principal):
        """Return the user ID associated with a particular Kerberos principal.
        If no user with the given princpal if found, return None."""
        self.checkKrbPrincipal(krb_principal)
        query = QueryProcessor(tables=['users'], columns=['id'],
                               joins=['user_krb_principals ON '
                                      'users.id = user_krb_principals.user_id'],
                               clauses=['krb_principal = %(krb_principal)s'],
                               values={'krb_principal': krb_principal})
        return query.singleValue(strict=False)

    def createUser(self, name, usertype=None, status=None, krb_principal=None,
                   krb_princ_check=True):
        """
        Create a new user, using the provided values.
        Return the user_id of the newly-created user.
        """
        if not name:
            raise koji.GenericError('a user must have a non-empty name')

        if usertype is None:
            usertype = koji.USERTYPES['NORMAL']
        elif not koji.USERTYPES.get(usertype):
            raise koji.GenericError('invalid user type: %s' % usertype)

        if status is None:
            status = koji.USER_STATUS['NORMAL']
        elif not koji.USER_STATUS.get(status):
            raise koji.GenericError('invalid status: %s' % status)

        # check if krb_principal is allowed
        if krb_princ_check:
            self.checkKrbPrincipal(krb_principal)

        user_id = nextval('users_id_seq')

        insert = InsertProcessor('users',
                                 data={'id': user_id, 'name': name, 'usertype': usertype,
                                       'status': status})
        insert.execute()
        if krb_principal:
            insert = InsertProcessor('user_krb_principals',
                                     data={'user_id': user_id, 'krb_principal': krb_principal})
            insert.execute()
        context.cnx.commit()

        return user_id

    def setKrbPrincipal(self, name, krb_principal, krb_princ_check=True):
        if krb_princ_check:
            self.checkKrbPrincipal(krb_principal)
        if isinstance(name, six.integer_types):
            clauses = ['id = %(name)i']
        else:
            clauses = ['name = %(name)s']
        query = QueryProcessor(tables=['users'], columns=['id'], clauses=clauses,
                               values={'name': name})
        user_id = query.singleValue(strict=False)
        if not user_id:
            context.cnx.rollback()
            raise koji.AuthError('No such user: %s' % name)
        insert = InsertProcessor('user_krb_principals',
                                 data={'user_id': user_id, 'krb_principal': krb_principal})
        insert.execute()
        context.cnx.commit()
        return user_id

    def removeKrbPrincipal(self, name, krb_principal):
        clauses = ['krb_principal = %(krb_principal)s']
        if isinstance(name, six.integer_types):
            clauses.extend(['id = %(name)i'])
        else:
            clauses.extend(['name = %(name)s'])
        query = QueryProcessor(tables=['users'], columns=['id'],
                               joins=['user_krb_principals '
                                      'ON users.id = user_krb_principals.user_id'],
                               clauses=clauses,
                               values={'krb_principal': krb_principal, 'name': name})
        user_id = query.singleValue(strict=False)
        if not user_id:
            context.cnx.rollback()
            raise koji.AuthError(
                'cannot remove Kerberos Principal:'
                ' %(krb_principal)s with user %(name)s' % locals())
        cursor = context.cnx.cursor()
        delete = DeleteProcessor(table='user_krb_principals',
                                 clauses=['user_id = %(user_id)i',
                                          'krb_principal = %(krb_principal)s'],
                                 values={'user_id': user_id, 'krb_principal': krb_principal})
        delete.execute()
        context.cnx.commit()
        return user_id

    def createUserFromKerberos(self, krb_principal):
        """Create a new user, based on the Kerberos principal.  Their
        username will be everything before the "@" in the principal.
        Return the ID of the newly created user."""
        atidx = krb_principal.find('@')
        if atidx == -1:
            raise koji.AuthError('invalid Kerberos principal: %s' % krb_principal)
        user_name = krb_principal[:atidx]

        # check if user already exists
        query = QueryProcessor(tables=['users'], columns=['id', 'krb_principal'],
                               joins=['LEFT JOIN user_krb_principals ON '
                                      'users.id = user_krb_principals.user_id'],
                               clauses=['name = %(user_name)s'],
                               values={'user_name': user_name})
        r = query.execute()
        if not r:
            return self.createUser(user_name, krb_principal=krb_principal,
                                   krb_princ_check=False)
        else:
            existing_user_krb_princs = [row['krb_principal'] for row in r]
            if krb_principal in existing_user_krb_princs:
                # do not set Kerberos principal if it already exists
                return r[0]['id']
            return self.setKrbPrincipal(user_name, krb_principal, krb_princ_check=False)

    def checkKrbPrincipal(self, krb_principal):
        """Check if the Kerberos principal is allowed"""
        if krb_principal is None:
            return
        allowed_realms = context.opts.get('AllowedKrbRealms', '*')
        if allowed_realms == '*':
            return
        allowed_realms = re.split(r'\s*,\s*', allowed_realms)
        atidx = krb_principal.find('@')
        if atidx == -1 or atidx == len(krb_principal) - 1:
            raise koji.AuthError(
                'invalid Kerberos principal: %s' % krb_principal)
        realm = krb_principal[atidx + 1:]
        if realm not in allowed_realms:
            raise koji.AuthError(
                "Kerberos principal's realm: %s is not allowed" % realm)


def get_user_groups(user_id):
    """Get user groups

    returns a dictionary where the keys are the group ids and the values
    are the group names"""
    t_group = koji.USERTYPES['GROUP']
    query = QueryProcessor(tables=['user_groups'], columns=['group_id', 'name'],
                           clauses=['active IS TRUE', 'users.usertype=%(t_group)i',
                                    'user_id=%(user_id)i'],
                           joins=['users ON group_id = users.id'],
                           values={'t_group': t_group, 'user_id': user_id})
    groups = {}
    for gdata in query.execute():
        groups[gdata['group_id']] = gdata['name']
    return groups


def get_user_perms(user_id, with_groups=True, inheritance_data=False):
    """
    :param int user_id: User ID
    :param bool with_groups: Add also permissions from all groups and their inheritance chain
    :param bool inheritance_data: Return extended data about permissions sources
    :returns list[str]: in case of inheritance_data=False
    :returns dict[str, list[str]]: in case of inheritance_data=True - keys are permissions' names,
                                   values list of groups which are in inheritance and provides
                                   given permission.
    """
    if inheritance_data and not with_groups:
        raise koji.ParameterError("inheritance option implies with_groups")

    # individual permissions
    perms = {}
    query = QueryProcessor(tables=['user_perms'], columns=['name'],
                           clauses=['active IS TRUE', 'user_id=%(user_id)s'],
                           joins=['permissions ON perm_id = permissions.id'],
                           values={'user_id': user_id})
    for perm in query.execute():
        perms[perm['name']] = [None]

    if with_groups:
        columns = ['permissions.name']
        aliases = ['name']
        joins = [
            'user_perms ON user_perms.user_id = user_groups.group_id',
            'permissions ON perm_id = permissions.id',
        ]
        if inheritance_data:
            # inheritance data adds one more join and as function
            # can be called relatively often (e.g. in hub policy tests)
            # it is a bit faster to ignore this join for "default" code path
            columns.append('users.name')
            aliases.append('group')
            joins.append('users ON user_groups.group_id = users.id')
        query = QueryProcessor(tables=['user_groups'],
                               columns=columns,
                               aliases=aliases,
                               clauses=[
                                   'user_groups.active IS TRUE',
                                   'user_perms.active IS TRUE',
                                   'user_groups.user_id=%(user_id)s'],
                               joins=joins,
                               values={'user_id': user_id})
        for row in query.execute():
            if inheritance_data:
                perms.setdefault(row['name'], []).append(row['group'])
            else:
                # group name wouldn't be used in this case
                perms.setdefault(row['name'], [])
    if inheritance_data:
        return perms
    else:
        return list(perms.keys())


def get_user_data(user_id):
    query = QueryProcessor(tables=['users'], columns=['name', 'status', 'usertype'],
                           clauses=['id=%(user_id)s'], values={'user_id': user_id})
    return query.executeOne(strict=False)


def login(*args, **opts):
    """Create a login session with plain user/password credentials.

    :param str user: username
    :param str password: password
    :param dict opts: curently can contain only 'host_ip' key for overriding client IP address

    :returns dict: session info
    """

    return context.session.login(*args, **opts)


def sslLogin(*args, **opts):
    """Login via SSL certificate

    :param str proxyuser: proxy username
    :returns dict: session info
    """
    return context.session.sslLogin(*args, **opts)


def logout(session_id=None):
    """expire a login session"""
    return context.session.logout(session_id)


def subsession():
    """Create a subsession"""
    return context.session.subsession()


def logoutChild(session_id):
    """expire a subsession

    :param int subsession_id: subsession ID (for current session)
    """
    return context.session.logoutChild(session_id)


def exclusiveSession(*args, **opts):
    """Make this session exclusive"""
    return context.session.makeExclusive(*args, **opts)


def sharedSession():
    """Drop out of exclusive mode"""
    return context.session.makeShared()
