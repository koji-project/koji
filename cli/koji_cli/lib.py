# coding=utf-8
from __future__ import absolute_import, division

import hashlib
import optparse
import os
import random
import socket
import string
import sys
import time
from contextlib import closing
from copy import copy

import requests
import six
import dateutil.parser
from six.moves import range

import koji
# import parse_arches to current namespace for backward compatibility
from koji import parse_arches
from koji.util import md5_constructor, to_list


# for compatibility with plugins based on older version of lib
# Use optparse imports directly in new code.
# Nevertheless, TimeOption can be used from here.
OptionParser = optparse.OptionParser


def _check_time_option(option, opt, value):
    """Converts str timestamp or date/time to float timestamp"""
    try:
        ts = float(value)
        return ts
    except ValueError:
        pass
    try:
        dt = dateutil.parser.parse(value)
        ts = time.mktime(dt.timetuple())
        return ts
    except Exception:
        raise optparse.OptionValueError(
            _("option %s: invalid time specification: %r") % (opt, value))


class TimeOption(optparse.Option):
    """OptionParser extension for timestamp/datetime values"""
    TYPES = optparse.Option.TYPES + ("time",)
    TYPE_CHECKER = copy(optparse.Option.TYPE_CHECKER)
    TYPE_CHECKER['time'] = _check_time_option

    @classmethod
    def get_help(self):
        return _("time is specified as timestamp or date/time in any "
                 "format which can be parsed by dateutil.parser. e.g. "
                 "\"2020-12-31 12:35\" or \"December 31st 12:35\"")


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
    # handle lists/dicts?
    return arg


categories = {
    'admin': 'admin commands',
    'build': 'build commands',
    'search': 'search commands',
    'download': 'download commands',
    'monitor': 'monitor commands',
    'info': 'info commands',
    'bind': 'bind commands',
    'misc': 'miscellaneous commands',
}


def get_epilog_str(progname=None):
    if progname is None:
        progname = os.path.basename(sys.argv[0]) or 'koji'
    categories_ordered = ', '.join(sorted(['all'] + to_list(categories.keys())))
    epilog_str = '''
Try "%(progname)s --help" for help about global options
Try "%(progname)s help" to get all available commands
Try "%(progname)s <command> --help" for help about the options of a particular command
Try "%(progname)s help <category>" to get commands under a particular category
Available categories are: %(categories)s
''' % ({'progname': progname, 'categories': categories_ordered})
    return _(epilog_str)


def get_usage_str(usage):
    return usage + _("\n(Specify the --help global option for a list of other help options)")


def ensure_connection(session, options=None):
    try:
        ret = session.getAPIVersion()
    except requests.exceptions.ConnectionError as ex:
        warn(_("Error: Unable to connect to server"))
        if options and getattr(options, 'debug', False):
            error(str(ex))
        else:
            error()
    if ret != koji.API_VERSION:
        warn(_("WARNING: The server is at API version %d and "
               "the client is at %d" % (ret, koji.API_VERSION)))


def print_task_headers():
    """Print the column headers"""
    print("ID       Pri  Owner                State    Arch       Name")


def print_task(task, depth=0):
    """Print a task"""
    task = task.copy()
    task['state'] = koji.TASK_STATES.get(task['state'], 'BADSTATE')
    fmt = "%(id)-8s %(priority)-4s %(owner_name)-20s %(state)-8s %(arch)-10s "
    if depth:
        indent = "  " * (depth - 1) + " +"
    else:
        indent = ''
    label = koji.taskLabel(task)
    print(''.join([fmt % task, indent, label]))


def print_task_recurse(task, depth=0):
    """Print a task and its children"""
    print_task(task, depth)
    for child in task.get('children', ()):
        print_task_recurse(child, depth + 1)


class TaskWatcher(object):

    def __init__(self, task_id, session, level=0, quiet=False, topurl=None):
        self.id = task_id
        self.session = session
        self.info = None
        self.level = level
        self.quiet = quiet
        self.topurl = topurl

    # XXX - a bunch of this stuff needs to adapt to different tasks

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
        except (six.moves.xmlrpc_client.Fault, koji.GenericError) as e:
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
            # compare and note status changes
            laststate = last['state']
            if laststate != state:
                if not self.quiet:
                    print("%s: %s -> %s" % (self.str(), self.display_state(last),
                                            self.display_state(self.info)))
                return True
            return False
        else:
            # First time we're seeing this task, so just show the current state
            if not self.quiet:
                print("%s: %s" % (self.str(), self.display_state(self.info, level=self.level)))
            return False

    def is_done(self):
        if self.info is None:
            return False
        state = koji.TASK_STATES[self.info['state']]
        return (state in ['CLOSED', 'CANCELED', 'FAILED'])

    def is_success(self):
        if self.info is None:
            return False
        state = koji.TASK_STATES[self.info['state']]
        return (state == 'CLOSED')

    def display_state(self, info, level=0):
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
            s = 'FAILED: %s' % self.get_failure()

            if self.topurl:
                # add relevant logs if there are any
                output = list_task_output_all_volumes(self.session, self.id)
                files = []
                for filename, volumes in six.iteritems(output):
                    files += [(filename, volume) for volume in volumes]

                files = [file_volume for file_volume in files if file_volume[0].endswith('log')]

                pi = koji.PathInfo(topdir=self.topurl)
                # indent more than current level
                level += 1
                logs = ['  ' * level + os.path.join(pi.task(self.id, f[1]), f[0]) for f in files]
                if logs:
                    s += '\n' + '  ' * level + 'Relevant logs:\n'
                    s += '\n'.join(logs)
            return s
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


def watch_tasks(session, tasklist, quiet=False, poll_interval=60, ki_handler=None, topurl=None):
    if not tasklist:
        return
    if not quiet:
        print("Watching tasks (this may be safely interrupted)...")
    if ki_handler is None:
        def ki_handler(progname, tasks, quiet):
            if not quiet:
                tlist = ['%s: %s' % (t.str(), t.display_state(t.info, level=t.level))
                         for t in tasks.values() if not t.is_done()]
                print(
                    "Tasks still running. You can continue to watch with the"
                    " '%s watch-task' command.\n"
                    "Running Tasks:\n%s" % (progname, '\n'.join(tlist)))
    sys.stdout.flush()
    rv = 0
    try:
        tasks = {}
        for task_id in tasklist:
            tasks[task_id] = TaskWatcher(task_id, session, quiet=quiet, topurl=topurl)
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
                    if child_id not in tasks.keys():
                        tasks[child_id] = TaskWatcher(child_id, session, task.level + 1,
                                                      quiet=quiet, topurl=topurl)
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
        sys.stdout.buffer.flush()


def watch_logs(session, tasklist, opts, poll_interval):
    print("Watching logs (this may be safely interrupted)...")

    def _isDone(session, taskId):
        info = session.getTaskInfo(taskId)
        if info is None:
            print("No such task id: %i" % taskId)
            sys.exit(1)
        state = koji.TASK_STATES[info['state']]
        return (state in ['CLOSED', 'CANCELED', 'FAILED'])

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

                    contents = session.downloadTaskOutput(task_id, log, taskoffsets[(log, volume)],
                                                          16384, volume=volume)
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
    except koji.ParameterError as e:
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


def _format_size(size):
    if (size / 1073741824 >= 1):
        return "%0.2f GiB" % (size / 1073741824.0)
    if (size / 1048576 >= 1):
        return "%0.2f MiB" % (size / 1048576.0)
    if (size / 1024 >= 1):
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
        percent_done = float(uploaded) / float(total)
    percent_done_str = "%02d%%" % (percent_done * 100)
    data_done = _format_size(uploaded)
    elapsed = _format_secs(total_time)

    speed = "- B/sec"
    if (time):
        if (uploaded != total):
            speed = _format_size(float(piece) / float(time)) + "/sec"
        else:
            speed = _format_size(float(total) / float(total_time)) + "/sec"

    # write formated string and flush
    sys.stdout.write("[% -36s] % 4s % 8s % 10s % 14s\r" % ('=' * (int(percent_done * 36)),
                                                           percent_done_str, elapsed, data_done,
                                                           speed))
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


def download_file(url, relpath, quiet=False, noprogress=False, size=None,
                  num=None, filesize=None):
    """Download files from remote

    :param str url: URL to be downloaded
    :param str relpath: where to save it
    :param bool quiet: no/verbose
    :param bool noprogress: print progress bar
    :param int size: total number of files being downloaded (printed in verbose
                     mode)
    :param int num: download index (printed in verbose mode)
    :param int filesize: expected file size, used for appending to file, no
                         other checks are performed, caller is responsible for
                         checking, that resulting file is valid."""

    if '/' in relpath:
        koji.ensuredir(os.path.dirname(relpath))
    if not quiet:
        if size and num:
            print(_("Downloading [%d/%d]: %s") % (num, size, relpath))
        else:
            print(_("Downloading: %s") % relpath)

    pos = 0
    headers = {}
    if filesize:
        # append the file
        f = open(relpath, 'ab')
        pos = f.tell()
        if pos:
            if filesize == pos:
                if not quiet:
                    print(_("File %s already downloaded, skipping" % relpath))
                return
            if not quiet:
                print(_("Appending to existing file %s" % relpath))
            headers['Range'] = ('bytes=%d-' % pos)
    else:
        # rewrite
        f = open(relpath, 'wb')

    try:
        # closing needs to be used for requests < 2.18.0
        with closing(requests.get(url, headers=headers, stream=True)) as response:
            if response.status_code in (200, 416):  # full content provided or reaching behind EOF
                # rewrite in such case
                f.close()
                f = open(relpath, 'wb')
            response.raise_for_status()
            length = filesize or int(response.headers.get('content-length') or 0)
            for chunk in response.iter_content(chunk_size=1024**2):
                pos += len(chunk)
                f.write(chunk)
                if not (quiet or noprogress):
                    _download_progress(length, pos, filesize)
            if not length and not (quiet or noprogress):
                _download_progress(pos, pos, filesize)
    finally:
        f.close()
        if pos == 0:
            # nothing was downloaded, e.g file not found
            os.unlink(relpath)

    if not (quiet or noprogress):
        print('')


def download_rpm(build, rpm, topurl, sigkey=None, quiet=False, noprogress=False):
    "Wrapper around download_file, do additional checks for rpm files"
    pi = koji.PathInfo(topdir=topurl)
    if sigkey:
        fname = pi.signed(rpm, sigkey)
        filesize = None
    else:
        fname = pi.rpm(rpm)
        filesize = rpm['size']
    url = os.path.join(pi.build(build), fname)
    path = os.path.basename(fname)

    download_file(url, path, quiet=quiet, noprogress=noprogress, filesize=filesize)

    # size - we have stored size only for unsigned copies
    if not sigkey:
        size = os.path.getsize(path)
        if size != rpm['size']:
            os.unlink(path)
            error("Downloaded rpm %s size %d does not match db size %d, deleting" %
                  (path, size, rpm['size']))

    # basic sanity
    try:
        koji.check_rpm_file(path)
    except koji.GenericError as ex:
        os.unlink(path)
        warn(str(ex))
        error("Downloaded rpm %s is not valid rpm file, deleting" % path)

    # payload hash
    sigmd5 = koji.get_header_fields(path, ['sigmd5'])['sigmd5']
    if rpm['payloadhash'] != koji.hex_string(sigmd5):
        os.unlink(path)
        error("Downloaded rpm %s doesn't match db, deleting" % path)


def download_archive(build, archive, topurl, quiet=False, noprogress=False):
    "Wrapper around download_file, do additional checks for archive files"

    pi = koji.PathInfo(topdir=topurl)
    if archive['btype'] == 'maven':
        url = os.path.join(pi.mavenbuild(build), pi.mavenfile(archive))
        path = pi.mavenfile(archive)
    elif archive['btype'] == 'win':
        url = os.path.join(pi.winbuild(build), pi.winfile(archive))
        path = pi.winfile(archive)
    elif archive['btype'] == 'image':
        url = os.path.join(pi.imagebuild(build), archive['filename'])
        path = archive['filename']
    else:
        # non-legacy types are more systematic
        directory = pi.typedir(build, archive['btype'])
        url = os.path.join(directory, archive['filename'])
        path = archive['filename']

    download_file(url, path, quiet=quiet, noprogress=noprogress, filesize=archive['size'])

    # check size
    if os.path.getsize(path) != archive['size']:
        os.unlink(path)
        error("Downloaded rpm %s size does not match db size, deleting" % path)

    # check checksum/checksum_type
    if archive['checksum_type'] == koji.CHECKSUM_TYPES['md5']:
        hash = md5_constructor()
    elif archive['checksum_type'] == koji.CHECKSUM_TYPES['sha1']:
        hash = hashlib.sha1()
    elif archive['checksum_type'] == koji.CHECKSUM_TYPES['sha256']:
        hash = hashlib.sha256()
    else:
        # shouldn't happen
        error("Unknown checksum type: %s" % archive['checksum_type'])
    with open(path, "rb") as f:
        while True:
            chunk = f.read(1024**2)
            hash.update(chunk)
            if not chunk:
                break
    if hash.hexdigest() != archive['checksum']:
        os.unlink(path)
        error("Downloaded archive %s doesn't match checksum, deleting" % path)


def _download_progress(download_t, download_d, size=None):
    if download_t == 0:
        percent_done = 0.0
        percent_done_str = "???%"
    else:
        percent_done = float(download_d) / float(download_t)
        percent_done_str = "%3d%%" % (percent_done * 100)
    if size:
        data_all = _format_size(size)
    data_done = _format_size(download_d)

    if size:
        data_size = "%s / %s" % (data_done, data_all)
    else:
        data_size = data_done
    sys.stdout.write("[% -36s] % 4s % 10s\r" % ('=' * (int(percent_done * 36)), percent_done_str,
                                                data_size))
    sys.stdout.flush()


def error(msg=None, code=1):
    if msg:
        sys.stderr.write(msg + "\n")
        sys.stderr.flush()
    sys.exit(code)


def warn(msg):
    sys.stderr.write(msg + "\n")
    sys.stderr.flush()


def activate_session(session, options):
    """Test and login the session is applicable"""
    if isinstance(options, dict):
        options = optparse.Values(options)
    noauth = options.authtype == "noauth" or getattr(options, 'noauth', False)
    runas = getattr(options, 'runas', None)
    if noauth:
        # skip authentication
        pass
    elif options.authtype == "ssl" or os.path.isfile(options.cert) and options.authtype is None:
        # authenticate using SSL client cert
        session.ssl_login(options.cert, None, options.serverca, proxyuser=runas)
    elif options.authtype == "password" \
            or getattr(options, 'user', None) \
            and options.authtype is None:
        # authenticate using user/password
        session.login()
    elif options.authtype == "kerberos" or options.authtype is None:
        try:
            if getattr(options, 'keytab', None) and getattr(options, 'principal', None):
                session.gssapi_login(principal=options.principal, keytab=options.keytab,
                                     proxyuser=runas)
            else:
                session.gssapi_login(proxyuser=runas)
        except socket.error as e:
            warn(_("Could not connect to Kerberos authentication service: %s") % e.args[1])
    if not noauth and not session.logged_in:
        error(_("Unable to log in, no authentication methods available"))
    ensure_connection(session)
    if getattr(options, 'debug', None):
        print("successfully connected to hub")


def _list_tasks(options, session):
    "Retrieve a list of tasks"

    callopts = {
        'decode': True,
    }
    if not getattr(options, 'all', False):
        callopts['state'] = [koji.TASK_STATES[s] for s in ('FREE', 'OPEN', 'ASSIGNED')]

    if getattr(options, 'after', False):
        callopts['startedAfter'] = options.after
    if getattr(options, 'before', False):
        callopts['startedBefore'] = options.before

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

    qopts = {'order': 'priority,create_time'}
    tasklist = session.listTasks(callopts, qopts)
    tasks = dict([(x['id'], x) for x in tasklist])

    # thread the tasks
    for t in tasklist:
        if t['parent'] is not None:
            parent = tasks.get(t['parent'])
            if parent:
                parent.setdefault('children', [])
                parent['children'].append(t)
                t['sub'] = True

    return tasklist


def format_inheritance_flags(parent):
    """Return a human readable string of inheritance flags"""
    flags = ''
    for code, expr in (
            ('M', parent['maxdepth'] is not None),
            ('F', parent['pkg_filter']),
            ('I', parent['intransitive']),
            ('N', parent['noconfig']),):
        if expr:
            flags += code
        else:
            flags += '.'
    return flags


def truncate_string(s, length=47):
    """Return a truncated string when string length is longer than given length."""
    if s:
        s = s.replace('\n', ' ')
        if len(s) > length:
            return s[:length] + '...'
        else:
            return s
    else:
        return ''
