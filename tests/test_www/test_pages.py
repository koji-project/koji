from __future__ import absolute_import
import inspect
import json
try:
    from unittest import mock
except ImportError:
    import mock
import os
import six
import sys
import unittest

from six.moves import StringIO

import koji
from koji_cli.lib import watch_tasks
from koji_cli.commands import anon_handle_watch_task
from koji.util import dslice
from ..test_cli.fakeclient import FakeClientSession, RecordingClientSession, encode_data
from .loadwebindex import webidx
from kojiweb.util import FieldStorageCompat


class TestPages(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        # recording session used across tests in recording mode
        cls.cfile = os.path.dirname(__file__) + f'/data/pages_calls.json'
        cls.cfile2 = os.path.dirname(__file__) + f'/data/pages_calls_updates.json'
        cls.recording = False
        cls.updating = False
        cls.rsession = RecordingClientSession('http://localhost/kojihub', {})

    @classmethod
    def tearDownClass(cls):
        if cls.recording:
            # save recorded calls
            cls.rsession.dump(cls.cfile)
        elif cls.updating:
            cls.rsession.dump(cls.cfile2)

    def setUp(self):
        self.environ = {
            'koji.options': {
                'SiteName': 'test',
                'KojiFilesURL': 'http://server.local/files',
                'KojiHubURL': 'http://server.local/kojihub',
                'KojiGreeting': 'Welcome to Koji Web',
                'LoginDisabled': True,
                'Tasks': [],
                'ToplevelTasks': [],
                'ParentTasks': [],
                'MBS_WEB_URL': None,
            },
            'koji.currentUser': None,
            'SCRIPT_FILENAME': webidx.__file__,  # close enough
            'SCRIPT_NAME': '',
            'SERVER_PORT': '80',
            'SERVER_NAME': 'server.local',
            'wsgi.url_scheme': 'http',
            'koji.headers': [],
        }
        self.get_server = mock.patch.object(webidx, "_getServer").start()
        self._assertLogin = mock.patch.object(webidx, "_assertLogin").start()
        self.server = None  # set up setup_server

        # mock time so that call args are reproduced
        self.time = mock.patch('time.time').start()
        self.time.return_value = 1735707600.0

        def __get_server(env):
            return self.server

        self.get_server.side_effect = __get_server
        self.setup_server()

    def setup_server(self):
        if self.recording:
            self.server = self.rsession
        else:
            self.server = FakeClientSession('SERVER', {})
            self.server.load(self.cfile)
            if self.updating:
                self.server._missing_rsession = self.rsession
        return self.server

    def tearDown(self):
        mock.patch.stopall()

    # Show long diffs in error output...
    maxDiff = None

    CALLS = [
        ['index', ''],
        ['packages', ''],
        ['packages', 'prefix=m&order=package_name&inherited=1&blocked=1'],
        ['packages', 'start=50&order=package_name&inherited=1&blocked=1'],
        ['builds', ''],
        ['builds', 'start=50&order=-build_id'],
        ['builds', 'prefix=d&order=-build_id'],
        ['builds', 'state=4&prefix=d&order=-build_id'],
        ['builds', 'type=image&prefix=d&order=-build_id'],
        ['tasks', ''],
        ['tasks', 'state=all&view=tree&order=-id&method=all'],
        ['tasks', 'state=failed&view=tree&order=-id&method=all'],
        ['tasks', 'view=flat&state=failed&order=-id&method=all'],
        ['tasks', 'method=buildArch&view=flat&state=failed&order=-id'],
        ['tasks', 'owner=mikem&view=flat&state=failed&order=-id&method=buildArch'],
        ['tags', ''],
        ['tags', 'start=50&order=name'],
        ['buildtargets', ''],
        ['buildtargets', 'order=-id'],
        ['users', ''],
        ['users', 'prefix=m&order=name'],
        ['hosts', ''],
        ['hosts', 'ready=yes&channel=all&state=all&order=name&arch=all'],
        ['hosts', 'channel=appliance&ready=all&state=all&order=name&arch=all'],
        ['hosts', 'arch=x86_64&channel=appliance&ready=all&state=all&order=name'],
        ['reports', ''],
        ['packagesbyuser', ''],
        ['buildsbyuser', ''],
        ['rpmsbyhost', ''],
        ['tasksbyuser', ''],
        ['tasksbyhost', ''],
        ['buildsbystatus', ''],
        ['buildsbytarget', ''],
        ['clusterhealth', ''],
        ['search', ''],
        ['search', 'terms=k*&type=package&match=glob'],
        ['api', ''],
        ['userinfo', 'userID=1'],
        ['activesession', ''],
        ['archiveinfo', 'archiveID=202'],
        ['buildinfo', 'buildID=628'],
        ['rpminfo', 'rpmID=6608'],
        ['buildrootinfo', 'buildrootID=966'],
        ['buildinfo', 'buildID=574'],
        ['buildrootinfo', 'buildrootID=934'],
        ['repoinfo', 'repoID=2580'],
        ['buildroots', 'repoID=2580'],
        ['buildroots', 'state=3&repoID=2580&order=id'],
        ['buildtargetedit', 'targetID=107&a='],
        ['buildtargetinfo', 'targetID=107'],
        ['taskinfo', 'taskID=14330'],
        ['channelinfo', 'channelID=1'],
        #['channelinfo', 'channelID=MISSING'],
        ['taginfo', 'tagID=798'],
        ['externalrepoinfo', 'extrepoID=1'],
        ['fileinfo', 'rpmID=6608&filename=/etc/koji.conf'],
        ['hostinfo', 'hostID=1'],
        ['hostedit', 'hostID=1&a='],
        ['notificationcreate', 'a='],
        ['notificationedit', 'notificationID=1&a='],
        ['packageinfo', 'packageID=306'],
        ['recentbuilds', ''],
        ['recentbuilds', 'package=1'],
        ['repoinfo', 'repoID=88'],
        ['rpminfo', 'rpmID=6608'],
        ['rpmlist', 'buildrootID=657&type=component'],
        ['taginfo', 'tagID=2'],
        ['tagedit', 'tagID=2&a='],
        ['tagparent', 'tagID=2&parentID=1&action=edit&a='],
        ['taginfo', 'tagID=2090'],
        ['userinfo', 'userID=1'],
        ['taskinfo', 'taskID=1'],
        ['archivelist', 'buildrootID=363&type=built'],
        ['buildinfo', 'buildID=422'],
        ['archiveinfo', 'archiveID=130'],
        ['archivelist', 'buildrootID=345&type=built'],
        ['buildinfo', 'buildID=612'],
        ['buildroots', ''],
        ['buildroots', 'start=50&order=id'],
        #['builds', 'start=50&order=id'],
    ]

    def prep_handler(self, method, query):
        """Takes method name and query string, returns handler and data"""
        # based loosely on publisher prep_handler
        self.environ['QUERY_STRING'] = query
        self.environ['koji.method'] = method
        self.environ['SCRIPT_NAME'] = method
        handler = getattr(webidx, method)
        fs = FieldStorageCompat(self.environ)
        self.environ['koji.form'] = fs
        # even though we have curated urls, we need to filter args for some cases, e.g. search
        args, varargs, varkw, defaults, kwonlyargs, kwonlydefaults, ann = \
            inspect.getfullargspec(handler)
        if not varkw:
            data = dslice(fs.data, args, strict=False)
        else:
            data = fs.data.copy()
        return handler, data

    def test_web_handlers(self):
        """Test a bunch of web handlers"""
        for method, query in self.CALLS:
            handler, data = self.prep_handler(method, query)

            result = handler(self.environ, **data)

            # result should be a string containing the rendered template
            self.assertIsInstance(result, str)
            # none of these should return the error template
            self.assertNotIn(r'<h4>Error</h4>', result)
            # all except recentbuilds (rss) should render the header and footer
            if method != 'recentbuilds':
                self.assertIn(r'<div id="header">', result)
                self.assertIn(r'<div id="mainNav">', result)
                self.assertIn(r'<p id="footer">', result)


# the end
