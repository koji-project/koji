# authentication module
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

import socket
import string
import random
import base64
import krbV
import koji
import cgi      #for parse_qs
from context import context
from mod_python import apache

# 1 - load session if provided
#       - check uri for session id
#       - load session info from db
#       - validate session
# 2 - create a session
#       - maybe in two steps
#       -

class Session(object):

    def __init__(self,args=None,hostip=None):
        self.logged_in = False
        self.id = None
        self.master = None
        self.key = None
        self.user_id = None
        self.hostip = None
        self.user_data = {}
        self.message = ''
        self.exclusive = False
        self.lockerror = None
        self.callnum = None
        #get session data from request
        if args is None:
            req = getattr(context,'req',None)
            args = getattr(req,'args',None)
            if not args:
                self.message = 'no session args'
                return
            args = cgi.parse_qs(args,strict_parsing=True)
        if hostip is None:
            hostip = context.req.get_remote_host(apache.REMOTE_NOLOOKUP)
            if hostip == '127.0.0.1':
                hostip = socket.gethostbyname(socket.gethostname())
        try:
            id = long(args['session-id'][0])
            key = args['session-key'][0]
        except KeyError, field:
            raise koji.AuthError, '%s not specified in session args' % field
        try:
            callnum = args['callnum'][0]
        except:
            callnum = None
        #lookup the session
        c = context.cnx.cursor()
        fields = {
            'authtype': 'authtype',
            'callnum': 'callnum',
            'exclusive': 'exclusive',
            'expired': 'expired',
            'master': 'master',
            'start_time': 'start_time',
            'update_time': 'update_time',
            'EXTRACT(EPOCH FROM start_time)': 'start_ts',
            'EXTRACT(EPOCH FROM update_time)': 'update_ts',
            'user_id': 'user_id',
            }
        fields, aliases = zip(*fields.items())
        q = """
        SELECT %s FROM sessions
        WHERE id = %%(id)i
        AND key = %%(key)s
        AND hostip = %%(hostip)s
        FOR UPDATE
        """ % ",".join(fields)
        c.execute(q,locals())
        row = c.fetchone()
        if not row:
            raise koji.AuthError, 'Invalid session or bad credentials'
        session_data = dict(zip(aliases, row))
        #check for expiration
        if session_data['expired']:
            raise koji.AuthExpired, 'session "%i" has expired' % id
        #check for callnum sanity
        if callnum is not None:
            try:
                callnum = int(callnum)
            except (ValueError,TypeError):
                raise koji.AuthError, "Invalid callnum: %r" % callnum
            lastcall = session_data['callnum']
            if lastcall is not None:
                if lastcall > callnum:
                    raise koji.SequenceError, "%d > %d (session %d)" \
                            % (lastcall,callnum,id)
                elif lastcall == callnum:
                    #Some explanation:
                    #This function is one of the few that performs its own commit.
                    #However, our storage of the current callnum is /after/ that
                    #commit. This means the the current callnum only gets commited if
                    #a commit happens afterward.
                    #We only schedule a commit for dml operations, so if we find the
                    #callnum in the db then a previous attempt succeeded but failed to
                    #return. Data was changed, so we cannot simply try the call again.
                    raise koji.RetryError, \
                        "unable to retry call %d (method %s) for session %d" \
                        % (callnum, getattr(context, 'method', 'UNKNOWN'), id)

        # read user data
        #historical note:
        # we used to get a row lock here as an attempt to maintain sanity of exclusive
        # sessions, but it was an imperfect approach and the lock could cause some
        # performance issues.
        fields = ('name','status','usertype')
        q = """SELECT %s FROM users WHERE id=%%(user_id)s""" % ','.join(fields)
        c.execute(q,session_data)
        user_data = dict(zip(fields,c.fetchone()))

        if user_data['status'] != koji.USER_STATUS['NORMAL']:
            raise koji.AuthError, 'logins by %s are not allowed' % user_data['name']
        #check for exclusive sessions
        if session_data['exclusive']:
            #we are the exclusive session for this user
            self.exclusive = True
        else:
            #see if an exclusive session exists
            q = """SELECT id FROM sessions WHERE user_id=%(user_id)s
            AND "exclusive" = TRUE AND expired = FALSE"""
            #should not return multiple rows (unique constraint)
            c.execute(q,session_data)
            row = c.fetchone()
            if row:
                (excl_id,) = row
                if excl_id == session_data['master']:
                    #(note excl_id cannot be None)
                    #our master session has the lock
                    self.exclusive = True
                else:
                    #a session unrelated to us has the lock
                    self.lockerror = "User locked by another session"
                    # we don't enforce here, but rely on the dispatcher to enforce
                    # if appropriate (otherwise it would be impossible to steal
                    # an exclusive session with the force option).

        # update timestamp
        q = """UPDATE sessions SET update_time=NOW() WHERE id = %(id)i"""
        c.execute(q,locals())
        #save update time
        context.cnx.commit()

        #update callnum (this is deliberately after the commit)
        #see earlier note near RetryError
        if callnum is not None:
            q = """UPDATE sessions SET callnum=%(callnum)i WHERE id = %(id)i"""
            c.execute(q,locals())

        # record the login data
        self.id = id
        self.key = key
        self.hostip = hostip
        self.callnum = callnum
        self.user_id = session_data['user_id']
        self.authtype = session_data['authtype']
        self.master = session_data['master']
        self.session_data = session_data
        self.user_data = user_data
        # we look up perms, groups, and host_id on demand, see __getattr__
        self._perms = None
        self._groups = None
        self._host_id = ''
        self.logged_in = True

    def __getattr__(self, name):
        # grab perm and groups data on the fly
        if name == 'perms':
            if self._perms is None:
                #in a dict for quicker lookup
                self._perms = dict([[name,1] for name in get_user_perms(self.user_id)])
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
            raise AttributeError, "%s" % name

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
            raise koji.AuthLockError, self.lockerror
        return True

    def checkLoginAllowed(self, user_id):
        """Verify that the user is allowed to login"""
        cursor = context.cnx.cursor()
        query = """SELECT name, usertype, status FROM users WHERE id = %(user_id)i"""
        cursor.execute(query, locals())
        result = cursor.fetchone()
        if not result:
            raise koji.AuthError, 'invalid user_id: %s' % user_id
        name, usertype, status = result
        
        if status != koji.USER_STATUS['NORMAL']:
            raise koji.AuthError, 'logins by %s are not allowed' % name

    def login(self,user,password,opts=None):
        """create a login session"""
        if opts is None:
            opts = {}
        if not isinstance(password,str) or len(password) == 0:
            raise koji.AuthError, 'invalid username or password'
        if self.logged_in:
            raise koji.GenericError, "Already logged in"
        hostip = opts.get('hostip')
        if hostip is None:
            hostip = context.req.get_remote_host(apache.REMOTE_NOLOOKUP)
            if hostip == '127.0.0.1':
                hostip = socket.gethostbyname(socket.gethostname())

        # check passwd
        c = context.cnx.cursor()
        q = """SELECT id FROM users
        WHERE name = %(user)s AND password = %(password)s"""
        c.execute(q,locals())
        r = c.fetchone()
        if not r:
            raise koji.AuthError, 'invalid username or password'
        user_id = r[0]

        self.checkLoginAllowed(user_id)

        #create session and return
        sinfo = self.createSession(user_id, hostip, koji.AUTHTYPE_NORMAL)
        session_id = sinfo['session-id']
        context.cnx.commit()
        return sinfo

    def krbLogin(self, krb_req, proxyuser=None):
        """Authenticate the user using the base64-encoded
        AP_REQ message in krb_req.  If proxyuser is not None,
        log in that user instead of the user associated with the
        Kerberos principal.  The principal must be an authorized
        "proxy_principal" in the server config."""
        if self.logged_in:
            raise koji.AuthError, "Already logged in"

        if not (context.opts.get('AuthPrincipal') and context.opts.get('AuthKeytab')):
            raise koji.AuthError, 'not configured for Kerberos authentication'

        ctx = krbV.default_context()
        srvprinc = krbV.Principal(name=context.opts.get('AuthPrincipal'), context=ctx)
        srvkt = krbV.Keytab(name=context.opts.get('AuthKeytab'), context=ctx)

        ac = krbV.AuthContext(context=ctx)
        ac.flags = krbV.KRB5_AUTH_CONTEXT_DO_SEQUENCE|krbV.KRB5_AUTH_CONTEXT_DO_TIME
        conninfo = self.getConnInfo()
        ac.addrs = conninfo

        # decode and read the authentication request
        req = base64.decodestring(krb_req)
        ac, opts, sprinc, ccreds = ctx.rd_req(req, server=srvprinc, keytab=srvkt,
                                              auth_context=ac,
                                              options=krbV.AP_OPTS_MUTUAL_REQUIRED)
        cprinc = ccreds[2]

        # Successfully authenticated via Kerberos, now log in
        if proxyuser:
            proxyprincs = [princ.strip() for princ in context.opts.get('ProxyPrincipals', '').split(',')]
            if cprinc.name in proxyprincs:
                login_principal = proxyuser
            else:
                raise koji.AuthError, \
                      'Kerberos principal %s is not authorized to log in other users' % cprinc.name
        else:
            login_principal = cprinc.name
        user_id = self.getUserIdFromKerberos(login_principal)
        if not user_id:
            if context.opts.get('LoginCreatesUser'):
                user_id = self.createUserFromKerberos(login_principal)
            else:
                raise koji.AuthError, 'Unknown Kerberos principal: %s' % login_principal

        self.checkLoginAllowed(user_id)

        hostip = context.req.connection.remote_ip
        if hostip == '127.0.0.1':
            hostip = socket.gethostbyname(socket.gethostname())

        sinfo = self.createSession(user_id, hostip, koji.AUTHTYPE_KERB)

        # encode the reply
        rep = ctx.mk_rep(auth_context=ac)
        rep_enc = base64.encodestring(rep)

        # encrypt and encode the login info
        sinfo_priv = ac.mk_priv('%(session-id)s %(session-key)s' % sinfo)
        sinfo_enc = base64.encodestring(sinfo_priv)

        return (rep_enc, sinfo_enc, conninfo)

    def getConnInfo(self):
        """Return a tuple containing connection information
        in the following format:
        (local ip addr, local port, remote ip, remote port)"""
        # For some reason req.connection.{local,remote}_addr contain port info,
        # but no IP info.  Use req.connection.{local,remote}_ip for that instead.
        # See: http://lists.planet-lab.org/pipermail/devel-community/2005-June/001084.html
        # local_ip seems to always be set to the same value as remote_ip,
        # so get the local ip via a different method
        # local_ip = context.req.connection.local_ip
        local_ip = socket.gethostbyname(context.req.hostname)
        remote_ip = context.req.connection.remote_ip

        # it appears that calling setports() with *any* value results in authentication
        # failing with "Incorrect net address", so return 0 (which prevents
        # python-krbV from calling setports())
        # local_port = context.req.connection.local_addr[1]
        # remote_port = context.req.connection.remote_addr[1]
        local_port = 0
        remote_port = 0

        return (local_ip, local_port, remote_ip, remote_port)

    def sslLogin(self, proxyuser=None):
        if self.logged_in:
            raise koji.AuthError, "Already logged in"

        # populate standard CGI variables
        context.req.add_common_vars()
        env = context.req.subprocess_env
    
        if env.get('HTTPS') != 'on':
            raise koji.AuthError, 'cannot call sslLogin() via a non-https connection'

        if env.get('SSL_CLIENT_VERIFY') != 'SUCCESS':
            raise koji.AuthError, 'could not verify client: %s' % env.get('SSL_CLIENT_VERIFY')

        name_dn_component = context.opts.get('DNUsernameComponent', 'CN')
        client_name = env.get('SSL_CLIENT_S_DN_%s' % name_dn_component)
        if not client_name:
            raise koji.AuthError, 'unable to get user information (%s) from client certificate' % name_dn_component

        if proxyuser:
            client_dn = env.get('SSL_CLIENT_S_DN')
            proxy_dns = [dn.strip() for dn in context.opts.get('ProxyDNs', '').split('|')]
            if client_dn in proxy_dns:
                # the SSL-authenticated user authorized to login other users
                username = proxyuser
            else:
                raise koji.AuthError, '%s is not authorized to login other users' % client_dn
        else:
            username = client_name
        
        cursor = context.cnx.cursor()
        query = """SELECT id FROM users
        WHERE name = %(username)s"""
        cursor.execute(query, locals())
        result = cursor.fetchone()
        if result:
            user_id = result[0]
        else:
            if context.opts.get('LoginCreatesUser'):
                user_id = self.createUser(username)
            else:
                raise koji.AuthError, 'Unknown user: %s' % username

        self.checkLoginAllowed(user_id)
            
        hostip = context.req.connection.remote_ip
        if hostip == '127.0.0.1':
            hostip = socket.gethostbyname(socket.gethostname())

        sinfo = self.createSession(user_id, hostip, koji.AUTHTYPE_SSL)
        return sinfo

    def makeExclusive(self,force=False):
        """Make this session exclusive"""
        c = context.cnx.cursor()
        if self.master is not None:
            raise koji.GenericError, "subsessions cannot become exclusive"
        if self.exclusive:
            #shouldn't happen
            raise koji.GenericError, "session is already exclusive"
        user_id = self.user_id
        session_id = self.id
        #acquire a row lock on the user entry
        q = """SELECT id FROM users WHERE id=%(user_id)s FOR UPDATE"""
        c.execute(q,locals())
        # check that no other sessions for this user are exclusive
        q = """SELECT id FROM sessions WHERE user_id=%(user_id)s
        AND expired = FALSE AND "exclusive" = TRUE
        FOR UPDATE"""
        c.execute(q,locals())
        row = c.fetchone()
        if row:
            if force:
                #expire the previous exclusive session and try again
                (excl_id,) = row
                q = """UPDATE sessions SET expired=TRUE,"exclusive"=NULL WHERE id=%(excl_id)s"""
                c.execute(q,locals())
            else:
                raise koji.AuthLockError, "Cannot get exclusive session"
        #mark this session exclusive
        q = """UPDATE sessions SET "exclusive"=TRUE WHERE id=%(session_id)s"""
        c.execute(q,locals())
        context.cnx.commit()

    def makeShared(self):
        """Drop out of exclusive mode"""
        c = context.cnx.cursor()
        session_id = self.id
        q = """UPDATE sessions SET "exclusive"=NULL WHERE id=%(session_id)s"""
        c.execute(q,locals())
        context.cnx.commit()

    def logout(self):
        """expire a login session"""
        if not self.logged_in:
            #XXX raise an error?
            raise koji.AuthError, "Not logged in"
        update = """UPDATE sessions
        SET expired=TRUE,exclusive=NULL
        WHERE id = %(id)i OR master = %(id)i"""
        #note we expire subsessions as well
        c = context.cnx.cursor()
        c.execute(update, {'id': self.id})
        context.cnx.commit()
        self.logged_in = False

    def logoutChild(self, session_id):
        """expire a subsession"""
        if not self.logged_in:
            #XXX raise an error?
            raise koji.AuthError, "Not logged in"
        update = """UPDATE sessions
        SET expired=TRUE,exclusive=NULL
        WHERE id = %(session_id)i AND master = %(master)i"""
        master = self.id
        c = context.cnx.cursor()
        c.execute(update, locals())
        context.cnx.commit()

    def createSession(self, user_id, hostip, authtype, master=None):
        """Create a new session for the given user.

        Return a map containing the session-id and session-key.
        If master is specified, create a subsession
        """
        c = context.cnx.cursor()

        # generate a random key
        alnum = string.ascii_letters + string.digits
        key = "%s-%s" %(user_id,
                ''.join([ random.choice(alnum) for x in range(1,20) ]))
        # use sha? sha.new(phrase).hexdigest()

        # get a session id
        q = """SELECT nextval('sessions_id_seq')"""
        c.execute(q, {})
        (session_id,) = c.fetchone()

        #add session id to database
        q = """
        INSERT INTO sessions (id, user_id, key, hostip, authtype, master)
        VALUES (%(session_id)i, %(user_id)i, %(key)s, %(hostip)s, %(authtype)i, %(master)s)
        """
        c.execute(q,locals())
        context.cnx.commit()

        #return session info
        return {'session-id' : session_id, 'session-key' : key}

    def subsession(self):
        "Create a subsession"
        if not self.logged_in:
            raise koji.AuthError, "Not logged in"
        master = self.master
        if master is None:
            master=self.id
        return self.createSession(self.user_id, self.hostip, self.authtype,
                    master=master)

    def getPerms(self):
        if not self.logged_in:
            return []
        return self.perms.keys()

    def hasPerm(self, name):
        if not self.logged_in:
            return False
        return self.perms.has_key(name)

    def assertPerm(self, name):
        if not self.hasPerm(name) and not self.hasPerm('admin'):
            raise koji.ActionNotAllowed, "%s permission required" % name

    def assertLogin(self):
        if not self.logged_in:
            raise koji.ActionNotAllowed, "you must be logged in for this operation"

    def hasGroup(self, group_id):
        if not self.logged_in:
            return False
        #groups indexed by id
        return self.groups.has_key(group_id)

    def isUser(self, user_id):
        if not self.logged_in:
            return False
        return ( self.user_id == user_id or self.hasGroup(user_id) )

    def assertUser(self, user_id):
        if not self.isUser(user_id) and not self.hasPerm('admin'):
            raise koji.ActionNotAllowed, "not owner"

    def _getHostId(self):
        '''Using session data, find host id (if there is one)'''
        if self.user_id is None:
            return None
        c=context.cnx.cursor()
        q="""SELECT id FROM host WHERE user_id = %(uid)d"""
        c.execute(q,{'uid' : self.user_id })
        r=c.fetchone()
        c.close()
        if r:
            return r[0]
        else:
            return None

    def getHostId(self):
        #for compatibility
        return self.host_id

    def getUserIdFromKerberos(self, krb_principal):
        """Return the user ID associated with a particular Kerberos principal.
        If no user with the given princpal if found, return None."""
        c = context.cnx.cursor()
        q = """SELECT id FROM users WHERE krb_principal = %(krb_principal)s"""
        c.execute(q,locals())
        r = c.fetchone()
        c.close()
        if r:
            return r[0]
        else:
            return None

    def createUser(self, name, usertype=None, status=None, krb_principal=None):
        """
        Create a new user, using the provided values.
        Return the user_id of the newly-created user.
        """
        if not name:
            raise koji.GenericError, 'a user must have a non-empty name'
        
        if usertype == None:
            usertype = koji.USERTYPES['NORMAL']
        elif not koji.USERTYPES.get(usertype):
            raise koji.GenericError, 'invalid user type: %s' % usertype

        if status == None:
            status = koji.USER_STATUS['NORMAL']
        elif not koji.USER_STATUS.get(status):
            raise koji.GenericError, 'invalid status: %s' % status
        
        cursor = context.cnx.cursor()
        select = """SELECT nextval('users_id_seq')"""
        cursor.execute(select, locals())
        user_id = cursor.fetchone()[0]

        insert = """INSERT INTO users (id, name, usertype, status, krb_principal)
        VALUES (%(user_id)i, %(name)s, %(usertype)i, %(status)i, %(krb_principal)s)"""
        cursor.execute(insert, locals())
        context.cnx.commit()

        return user_id

    def createUserFromKerberos(self, krb_principal):
        """Create a new user, based on the Kerberos principal.  Their
        username will be everything before the "@" in the principal.
        Return the ID of the newly created user."""
        atidx = krb_principal.find('@')
        if atidx == -1:
            raise koji.AuthError, 'invalid Kerberos principal: %s' % krb_principal
        user_name = krb_principal[:atidx]

        return self.createUser(user_name, krb_principal=krb_principal)

def get_user_groups(user_id):
    """Get user groups

    returns a dictionary where the keys are the group ids and the values
    are the group names"""
    c = context.cnx.cursor()
    t_group = koji.USERTYPES['GROUP']
    q = """SELECT group_id,name
    FROM user_groups JOIN users ON group_id = users.id
    WHERE active = TRUE AND users.usertype=%(t_group)i
        AND user_id=%(user_id)i"""
    c.execute(q,locals())
    return dict(c.fetchall())

def get_user_perms(user_id):
    c = context.cnx.cursor()
    q = """SELECT name
    FROM user_perms JOIN permissions ON perm_id = permissions.id
    WHERE active = TRUE AND user_id=%(user_id)s"""
    c.execute(q,locals())
    #return a list of permissions by name
    return [row[0] for row in c.fetchall()]

def get_user_data(user_id):
    c = context.cnx.cursor()
    fields = ('name','status','usertype')
    q = """SELECT %s FROM users WHERE id=%%(user_id)s""" % ','.join(fields)
    c.execute(q,locals())
    row = c.fetchone()
    if not row:
        return None
    return dict(zip(fields,row))

def login(*args,**opts):
    return context.session.login(*args,**opts)

def krbLogin(*args, **opts):
    return context.session.krbLogin(*args, **opts)

def sslLogin(*args, **opts):
    return context.session.sslLogin(*args, **opts)

def logout():
    return context.session.logout()

def subsession():
    return context.session.subsession()

def logoutChild(session_id):
    return context.session.logoutChild(session_id)

def exclusiveSession(*args,**opts):
    """Make this session exclusive"""
    return context.session.makeExclusive(*args,**opts)

def sharedSession():
    """Drop out of exclusive mode"""
    return context.session.makeShared()


if __name__ == '__main__':
    # XXX - testing defaults
    import db
    db.setDBopts( database = "test", user = "test")
    print "Connecting to db"
    context.cnx = db.connect()
    print "starting session 1"
    sess = Session(None,hostip='127.0.0.1')
    print "Session 1: %s" % sess
    print "logging in with session 1"
    session_info = sess.login('host/1','foobar',{'hostip':'127.0.0.1'})
    #wrap values in lists
    session_info = dict([ [k,[v]] for k,v in session_info.iteritems()])
    print "Session 1: %s" % sess
    print "Session 1 info: %r" % session_info
    print "Creating session 2"
    s2 = Session(session_info,'127.0.0.1')
    print "Session 2: %s " % s2
