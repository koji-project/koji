# coding=utf-8
from __future__ import absolute_import
from __future__ import division
import optparse
import os
import random
import requests
import six
import socket
import string
import sys
import time
from contextlib import closing
from six.moves import range

try:
    import krbV
except ImportError:  # pragma: no cover
    krbV = None

import koji
from koji.util import to_list
# import parse_arches to current namespace for backward compatibility
from koji import parse_arches

# for compatibility with plugins based on older version of lib
# Use optparse imports directly in new code.
OptionParser = optparse.OptionParser

greetings = ('hello', 'hi', 'yo', "what's up", "g'day", 'back to work',
             'bonjour',
             'hallo',
             'ciao',
             'hola',
            u'olá',
            u'dobrý den',
            u'zdravstvuite',
            u'góðan daginn',
             'hej',
             'tervehdys',
            u'grüezi',
            u'céad míle fáilte',
            u'hylô',
            u'bună ziua',
            u'jó napot',
             'dobre dan',
            u'你好',
            u'こんにちは',
            u'नमस्कार',
            u'안녕하세요')

ARGMAP = {'None': None,
          'True': True,
          'False': False}


def _(args):
    """Stub function for translation"""
    return args


def arg_filter(arg):
    try:
        return int(arg)
    except ValueError:
        pass
    try:
        return float(arg)
    except ValueError:
        pass
    if arg in ARGMAP:
        return ARGMAP[arg]
    #handle lists/dicts?
    return arg


categories = {
    'admin' : 'admin commands',
    'build' : 'build commands',
    'search' : 'search commands',
    'download' : 'download commands',
    'monitor'  : 'monitor commands',
    'info' : 'info commands',
    'bind' : 'bind commands',
    'misc' : 'miscellaneous commands',
}


def get_epilog_str(progname=None):
    if progname is None:
        progname = os.path.basename(sys.argv[0]) or 'koji'
    categories_ordered=', '.join(sorted(['all'] + to_list(categories.keys())))
    epilog_str = '''
Try "%(progname)s --help" for help about global options
Try "%(progname)s help" to get all available commands
Try "%(progname)s <command> --help" for help about the options of a particular command
Try "%(progname)s help <category>" to get commands under a particular category
Available categories are: %(categories)s
''' % ({'progname': progname, 'categories': categories_ordered})
    return _(epilog_str)


def ensure_connection(session):
    try:
        ret = session.getAPIVersion()
    except six.moves.xmlrpc_client.ProtocolError:
        error(_("Error: Unable to connect to server"))
    if ret != koji.API_VERSION:
        warn(_("WARNING: The server is at API version %d and the client is at %d" % (ret, koji.API_VERSION)))


def print_task_headers():
    """Print the column headers"""
    print("ID       Pri  Owner                State    Arch       Name")


def print_task(task,depth=0):
    """Print a task"""
    task = task.copy()
    task['state'] = koji.TASK_STATES.get(task['state'],'BADSTATE')
    fmt = "%(id)-8s %(priority)-4s %(owner_name)-20s %(state)-8s %(arch)-10s "
    if depth:
        indent = "  "*(depth-1) + " +"
    else:
        indent = ''
    label = koji.taskLabel(task)
    print(''.join([fmt % task, indent, label]))


def print_task_recurse(task,depth=0):
    """Print a task and its children"""
    print_task(task,depth)
    for child in task.get('children',()):
        print_task_recurse(child,depth+1)


class TaskWatcher(object):

    def __init__(self,task_id,session,level=0,quiet=False):
        self.id = task_id
        self.session = session
        self.info = None
        self.level = level
        self.quiet = quiet

    #XXX - a bunch of this stuff needs to adapt to different tasks

    def str(self):
        if self.info:
            label = koji.taskLabel(self.info)
            return "%s%d %s" % ('  ' * self.level, self.id, label)
        else:
            return "%s%d" % ('  ' * self.level, self.id)

    def __str__(self):
        return self.str()

    def get_failure(self):
        """Print information about task completion"""
        if self.info['state'] != koji.TASK_STATES['FAILED']:
            return ''
        error = None
        try:
            self.session.getTaskResult(self.id)
        except (six.moves.xmlrpc_client.Fault,koji.GenericError) as e:
            error = e
        if error is None:
            # print("%s: complete" % self.str())
            # We already reported this task as complete in update()
            return ''
        else:
            return '%s: %s' % (error.__class__.__name__, str(error).strip())

    def update(self):
        """Update info and log if needed.  Returns True on state change."""
        if self.is_done():
            # Already done, nothing else to report
            return False
        last = self.info
        self.info = self.session.getTaskInfo(self.id, request=True)
        if self.info is None:
            if not self.quiet:
                print("No such task id: %i" % self.id)
            sys.exit(1)
        state = self.info['state']
        if last:
            #compare and note status changes
            laststate = last['state']
            if laststate != state:
                if not self.quiet:
                    print("%s: %s -> %s" % (self.str(), self.display_state(last), self.display_state(self.info)))
                return True
            return False
        else:
            # First time we're seeing this task, so just show the current state
            if not self.quiet:
                print("%s: %s" % (self.str(), self.display_state(self.info)))
            return False

    def is_done(self):
        if self.info is None:
            return False
        state = koji.TASK_STATES[self.info['state']]
        return (state in ['CLOSED','CANCELED','FAILED'])

    def is_success(self):
        if self.info is None:
            return False
        state = koji.TASK_STATES[self.info['state']]
        return (state == 'CLOSED')

    def display_state(self, info):
        # We can sometimes be passed a task that is not yet open, but
        # not finished either.  info would be none.
        if not info:
            return 'unknown'
        if info['state'] == koji.TASK_STATES['OPEN']:
            if info['host_id']:
                host = self.session.getHost(info['host_id'])
                return 'open (%s)' % host['name']
            else:
                return 'open'
        elif info['state'] == koji.TASK_STATES['FAILED']:
            return 'FAILED: %s' % self.get_failure()
        else:
            return koji.TASK_STATES[info['state']].lower()


def display_tasklist_status(tasks):
    free = 0
    open = 0
    failed = 0
    done = 0
    for task_id in tasks.keys():
        status = tasks[task_id].info['state']
        if status == koji.TASK_STATES['FAILED']:
            failed += 1
        elif status == koji.TASK_STATES['CLOSED'] or status == koji.TASK_STATES['CANCELED']:
            done += 1
        elif status == koji.TASK_STATES['OPEN'] or status == koji.TASK_STATES['ASSIGNED']:
            open += 1
        elif status == koji.TASK_STATES['FREE']:
            free += 1
    print("  %d free  %d open  %d done  %d failed" % (free, open, done, failed))


def display_task_results(tasks):
    for task in [task for task in tasks.values() if task.level == 0]:
        state = task.info['state']
        task_label = task.str()

        if state == koji.TASK_STATES['CLOSED']:
            print('%s completed successfully' % task_label)
        elif state == koji.TASK_STATES['FAILED']:
            print('%s failed' % task_label)
        elif state == koji.TASK_STATES['CANCELED']:
            print('%s was canceled' % task_label)
        else:
            # shouldn't happen
            print('%s has not completed' % task_label)


def watch_tasks(session, tasklist, quiet=False, poll_interval=60, ki_handler=None):
    if not tasklist:
        return
    if not quiet:
        print("Watching tasks (this may be safely interrupted)...")
    if ki_handler is None:
        def ki_handler(progname, tasks, quiet):
            if not quiet:
                tlist = ['%s: %s' % (t.str(), t.display_state(t.info))
                         for t in tasks.values() if not t.is_done()]
                print(
"""Tasks still running. You can continue to watch with the '%s watch-task' command.
Running Tasks:
%s""" % (progname, '\n'.join(tlist)))
    sys.stdout.flush()
    rv = 0
    try:
        tasks = {}
        for task_id in tasklist:
            tasks[task_id] = TaskWatcher(task_id, session, quiet=quiet)
        while True:
            all_done = True
            for task_id, task in list(tasks.items()):
                changed = task.update()
                if not task.is_done():
                    all_done = False
                else:
                    if changed:
                        # task is done and state just changed
                        if not quiet:
                            display_tasklist_status(tasks)
                    if task.level == 0 and not task.is_success():
                        rv = 1
                for child in session.getTaskChildren(task_id):
                    child_id = child['id']
                    if not child_id in tasks.keys():
                        tasks[child_id] = TaskWatcher(child_id, session, task.level + 1, quiet=quiet)
                        tasks[child_id].update()
                        # If we found new children, go through the list again,
                        # in case they have children also
                        all_done = False
            if all_done:
                if not quiet:
                    print('')
                    display_task_results(tasks)
                break

            sys.stdout.flush()
            time.sleep(poll_interval)
    except KeyboardInterrupt:
        if tasks:
            progname = os.path.basename(sys.argv[0]) or 'koji'
            ki_handler(progname, tasks, quiet)
        raise
    return rv


def bytes_to_stdout(contents):
    """Helper function for writing bytes to stdout"""
    if six.PY2:
        sys.stdout.write(contents)
    else:
        sys.stdout.buffer.write(contents)


def watch_logs(session, tasklist, opts, poll_interval):
    print("Watching logs (this may be safely interrupted)...")

    def _isDone(session, taskId):
        info = session.getTaskInfo(taskId)
        if info is None:
            print("No such task id: %i" % taskId)
            sys.exit(1)
        state = koji.TASK_STATES[info['state']]
        return (state in ['CLOSED','CANCELED','FAILED'])

    offsets = {}
    for task_id in tasklist:
        offsets[task_id] = {}

    lastlog = None
    while True:
        for task_id in tasklist[:]:
            if _isDone(session, task_id):
                tasklist.remove(task_id)

            output = list_task_output_all_volumes(session, task_id)
            # convert to list of (file, volume)
            files = []
            for filename, volumes in six.iteritems(output):
                files += [(filename, volume) for volume in volumes]

            if opts.log:
                logs = [file_volume for file_volume in files if file_volume[0] == opts.log]
            else:
                logs = [file_volume for file_volume in files if file_volume[0].endswith('log')]

            taskoffsets = offsets[task_id]
            for log, volume in logs:
                contents = 'placeholder'
                while contents:
                    if (log, volume) not in taskoffsets:
                        taskoffsets[(log, volume)] = 0

                    contents = session.downloadTaskOutput(task_id, log, taskoffsets[(log, volume)], 16384, volume=volume)
                    taskoffsets[(log, volume)] += len(contents)
                    if contents:
                        currlog = "%d:%s:%s:" % (task_id, volume, log)
                        if currlog != lastlog:
                            if lastlog:
                                sys.stdout.write("\n")
                            sys.stdout.write("==> %s <==\n" % currlog)
                            lastlog = currlog
                        bytes_to_stdout(contents)


            if opts.follow:
                for child in session.getTaskChildren(task_id):
                    if child['id'] not in tasklist:
                        tasklist.append(child['id'])
                        offsets[child['id']] = {}

        if not tasklist:
            break

        time.sleep(poll_interval)


def list_task_output_all_volumes(session, task_id):
    """List task output with all volumes, or fake it"""
    try:
        return session.listTaskOutput(task_id, all_volumes=True)
    except koji.GenericError as e:
        if 'got an unexpected keyword argument' not in str(e):
            raise
    # otherwise leave off the option and fake it
    output = session.listTaskOutput(task_id)
    return dict([fn, ['DEFAULT']] for fn in output)


def unique_path(prefix):
    """Create a unique path fragment by appending a path component
    to prefix.  The path component will consist of a string of letter and numbers
    that is unlikely to be a duplicate, but is not guaranteed to be unique."""
    # Use time() in the dirname to provide a little more information when
    # browsing the filesystem.
    # For some reason repr(time.time()) includes 4 or 5
    # more digits of precision than str(time.time())
    return '%s/%r.%s' % (prefix, time.time(),
                      ''.join([random.choice(string.ascii_letters) for i in range(8)]))


def _unique_path(prefix):
    koji.util.deprecated('_unique_path is deprecated, use unique_path instead.'
                         ' See: https://pagure.io/koji/issue/975')
    return unique_path(prefix)


def _format_size(size):
    if (size / 1073741824 >= 1):
        return "%0.2f GiB" % (size / 1073741824.0)
    if (size / 1048576 >= 1):
        return "%0.2f MiB" % (size / 1048576.0)
    if (size / 1024 >=1):
        return "%0.2f KiB" % (size / 1024.0)
    return "%0.2f B" % (size)


def _format_secs(t):
    h = t / 3600
    t %= 3600
    m = t / 60
    s = t % 60
    return "%02d:%02d:%02d" % (h, m, s)


def _progress_callback(uploaded, total, piece, time, total_time):
    if total == 0:
        percent_done = 0.0
    else:
        percent_done = float(uploaded)/float(total)
    percent_done_str = "%02d%%" % (percent_done * 100)
    data_done = _format_size(uploaded)
    elapsed = _format_secs(total_time)

    speed = "- B/sec"
    if (time):
        if (uploaded != total):
            speed = _format_size(float(piece)/float(time)) + "/sec"
        else:
            speed = _format_size(float(total)/float(total_time)) + "/sec"

    # write formated string and flush
    sys.stdout.write("[% -36s] % 4s % 8s % 10s % 14s\r" % ('='*(int(percent_done*36)), percent_done_str, elapsed, data_done, speed))
    sys.stdout.flush()


def _running_in_bg():
    try:
        return (not os.isatty(0)) or (os.getpgrp() != os.tcgetpgrp(0))
    except OSError:
        return True


def linked_upload(localfile, path, name=None):
    """Link a file into the (locally writable) workdir, bypassing upload"""
    old_umask = os.umask(0o02)
    try:
        if name is None:
            name = os.path.basename(localfile)
        dest_dir = os.path.join(koji.pathinfo.work(), path)
        dst = os.path.join(dest_dir, name)
        koji.ensuredir(dest_dir)
        # fix uid/gid to keep httpd happy
        st = os.stat(koji.pathinfo.work())
        os.chown(dest_dir, st.st_uid, st.st_gid)
        print("Linking rpm to: %s" % dst)
        os.link(localfile, dst)
    finally:
        os.umask(old_umask)


def download_file(url, relpath, quiet=False, noprogress=False, size=None, num=None):
    """Download files from remote"""

    if '/' in relpath:
        koji.ensuredir(os.path.dirname(relpath))
    if not quiet:
        if size and num:
            print(_("Downloading [%d/%d]: %s") % (num, size, relpath))
        else:
            print(_("Downloading: %s") % relpath)


    with closing(requests.get(url, stream=True)) as response:
        # raise error if occured
        response.raise_for_status()
        length = response.headers.get('content-length')
        f = open(relpath, 'wb')
        if length is None:
            f.write(response.content)
            length = len(response.content)
            if not (quiet or noprogress):
                _download_progress(length, length)
        else:
            l = 0
            length = int(length)
            for chunk in response.iter_content(chunk_size=65536):
                l += len(chunk)
                f.write(chunk)
                if not (quiet or noprogress):
                    _download_progress(length, l)
            f.close()

    if not (quiet or noprogress):
        print('')


def _download_progress(download_t, download_d):
    if download_t == 0:
        percent_done = 0.0
    else:
        percent_done = float(download_d) / float(download_t)
    percent_done_str = "%3d%%" % (percent_done * 100)
    data_done = _format_size(download_d)

    sys.stdout.write("[% -36s] % 4s % 10s\r" % ('=' * (int(percent_done * 36)), percent_done_str, data_done))
    sys.stdout.flush()


def error(msg=None, code=1):
    if msg:
        sys.stderr.write(msg + "\n")
        sys.stderr.flush()
    sys.exit(code)


def warn(msg):
    sys.stderr.write(msg + "\n")
    sys.stderr.flush()


def has_krb_creds():
    if krbV is None:
        return False
    try:
        ctx = krbV.default_context()
        ccache = ctx.default_ccache()
        ccache.principal()
        return True
    except krbV.Krb5Error:
        return False


def activate_session(session, options):
    """Test and login the session is applicable"""
    if isinstance(options, dict):
        options = optparse.Values(options)
    noauth = options.authtype == "noauth" or getattr(options, 'noauth', False)
    runas = getattr(options, 'runas', None)
    if noauth:
        #skip authentication
        pass
    elif options.authtype == "ssl" or os.path.isfile(options.cert) and options.authtype is None:
        # authenticate using SSL client cert
        session.ssl_login(options.cert, None, options.serverca, proxyuser=runas)
    elif options.authtype == "password" or getattr(options, 'user', None) and options.authtype is None:
        # authenticate using user/password
        session.login()
    elif options.authtype == "kerberos" or has_krb_creds() and options.authtype is None:
        try:
            if getattr(options, 'keytab', None) and getattr(options, 'principal', None):
                session.krb_login(principal=options.principal, keytab=options.keytab, proxyuser=runas)
            else:
                session.krb_login(proxyuser=runas)
        except socket.error as e:
            warn(_("Could not connect to Kerberos authentication service: %s") % e.args[1])
        except Exception as e:
            if krbV is not None and isinstance(e, krbV.Krb5Error):
                error(_("Kerberos authentication failed: %s (%s)") % (e.args[1], e.args[0]))
            else:
                raise
    if not noauth and not session.logged_in:
        error(_("Unable to log in, no authentication methods available"))
    ensure_connection(session)
    if getattr(options, 'debug', None):
        print("successfully connected to hub")


def _list_tasks(options, session):
    "Retrieve a list of tasks"

    callopts = {
        'state' : [koji.TASK_STATES[s] for s in ('FREE', 'OPEN', 'ASSIGNED')],
        'decode' : True,
    }

    if getattr(options, 'mine', False):
        if getattr(options, 'user', None):
            raise koji.GenericError("Can't specify 'mine' and 'user' in same time")
        user = session.getLoggedInUser()
        if not user:
            print("Unable to determine user")
            sys.exit(1)
        callopts['owner'] = user['id']
    if getattr(options, 'user', None):
        user = session.getUser(options.user)
        if not user:
            print("No such user: %s" % options.user)
            sys.exit(1)
        callopts['owner'] = user['id']
    if getattr(options, 'arch', None):
        callopts['arch'] = parse_arches(options.arch, to_list=True)
    if getattr(options, 'method', None):
        callopts['method'] = options.method
    if getattr(options, 'channel', None):
        chan = session.getChannel(options.channel)
        if not chan:
            print("No such channel: %s" % options.channel)
            sys.exit(1)
        callopts['channel_id'] = chan['id']
    if getattr(options, 'host', None):
        host = session.getHost(options.host)
        if not host:
            print("No such host: %s" % options.host)
            sys.exit(1)
        callopts['host_id'] = host['id']

    qopts = {'order' : 'priority,create_time'}
    tasklist = session.listTasks(callopts, qopts)
    tasks = dict([(x['id'], x) for x in tasklist])

    #thread the tasks
    for t in tasklist:
        if t['parent'] is not None:
            parent = tasks.get(t['parent'])
            if parent:
                parent.setdefault('children',[])
                parent['children'].append(t)
                t['sub'] = True

    return tasklist
