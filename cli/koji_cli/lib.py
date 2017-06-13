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
    categories_ordered=', '.join(sorted(['all'] + list(categories.keys())))
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

def parse_arches(arches, to_list=False):
    """Parse comma or space-separated list of arches and return
       only space-separated one."""
    arches = arches.replace(',', ' ').split()
    if to_list:
        return arches
    else:
        return ' '.join(arches)

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
        """Print infomation about task completion"""
        if self.info['state'] != koji.TASK_STATES['FAILED']:
            return ''
        error = None
        try:
            result = self.session.getTaskResult(self.id)
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

def watch_tasks(session,tasklist,quiet=False):
    global options
    if not tasklist:
        return
    if not quiet:
        print("Watching tasks (this may be safely interrupted)...")
    sys.stdout.flush()
    rv = 0
    try:
        tasks = {}
        for task_id in tasklist:
            tasks[task_id] = TaskWatcher(task_id,session,quiet=quiet)
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
                    if not task.is_success():
                        rv = 1
                for child in session.getTaskChildren(task_id):
                    child_id = child['id']
                    if not child_id in list(tasks.keys()):
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
            time.sleep(options.poll_interval)
    except KeyboardInterrupt:
        if tasks and not quiet:
            progname = os.path.basename(sys.argv[0]) or 'koji'
            tlist = ['%s: %s' % (t.str(), t.display_state(t.info))
                            for t in tasks.values() if not t.is_done()]
            print( \
"""Tasks still running. You can continue to watch with the '%s watch-task' command.
Running Tasks:
%s""" % (progname, '\n'.join(tlist)))
        raise
    return rv

def watch_logs(session, tasklist, opts):
    global options
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
                        sys.stdout.write(contents)

        if not tasklist:
            break

        time.sleep(options.poll_interval)


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
def _unique_path(prefix):
    """Create a unique path fragment by appending a path component
    to prefix.  The path component will consist of a string of letter and numbers
    that is unlikely to be a duplicate, but is not guaranteed to be unique."""
    # Use time() in the dirname to provide a little more information when
    # browsing the filesystem.
    # For some reason repr(time.time()) includes 4 or 5
    # more digits of precision than str(time.time())
    return '%s/%r.%s' % (prefix, time.time(),
                      ''.join([random.choice(string.ascii_letters) for i in range(8)]))

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
    except OSError as e:
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
        princ = ccache.principal()
        return True
    except krbV.Krb5Error:
        return False

def activate_session(session):
    """Test and login the session is applicable"""
    global options
    if options.authtype == "noauth" or options.noauth:
        #skip authentication
        pass
    elif options.authtype == "ssl" or os.path.isfile(options.cert) and options.authtype is None:
        # authenticate using SSL client cert
        session.ssl_login(options.cert, None, options.serverca, proxyuser=options.runas)
    elif options.authtype == "password" or options.user and options.authtype is None:
        # authenticate using user/password
        session.login()
    elif options.authtype == "kerberos" or has_krb_creds() and options.authtype is None:
        try:
            if options.keytab and options.principal:
                session.krb_login(principal=options.principal, keytab=options.keytab, proxyuser=options.runas)
            else:
                session.krb_login(proxyuser=options.runas)
        except socket.error as e:
            warn(_("Could not connect to Kerberos authentication service: %s") % e.args[1])
        except Exception as e:
            if krbV is not None and isinstance(e, krbV.Krb5Error):
                error(_("Kerberos authentication failed: %s (%s)") % (e.args[1], e.args[0]))
            else:
                raise
    if not options.noauth and options.authtype != "noauth" and not session.logged_in:
        error(_("Unable to log in, no authentication methods available"))
    ensure_connection(session)
    if options.debug:
        print("successfully connected to hub")
