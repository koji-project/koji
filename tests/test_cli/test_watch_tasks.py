from __future__ import absolute_import
import json
import mock
import os
import six
import sys
try:
    import unittest2 as unittest
except ImportError:
    import unittest

from mock import call
from six.moves import range

from koji_cli.lib import watch_tasks
from .fakeclient import FakeClientSession, RecordingClientSession


class TestWatchTasks(unittest.TestCase):

    def setUp(self):
        self.options = mock.MagicMock()
        self.session = FakeClientSession('SERVER', {})
        self.recording = False
        self.record_file = None
        self.args = mock.MagicMock()

    def tearDown(self):
        mock.patch.stopall()
        if self.recording:
            # save recorded calls
            if self.record_file:
                with open(self.record_file, 'w') as fp:
                    json.dump(self.session.get_calls(), fp, indent=4)
            else:
                json.dump(self.session.get_calls(), sys.stderr, indent=4)
            self.recording = False
            self.record_file = None

    def setup_record(self, filename=None):
        self.session = RecordingClientSession('http://localhost/kojihub', {})
        self.recording = True
        self.record_file = filename

    # Show long diffs in error output...
    maxDiff = None

    @mock.patch('sys.stdout', new_callable=six.StringIO)
    def test_watch_tasks_no_tasklist(self, stdout):
        returned = watch_tasks(self.session, [], poll_interval=0)
        actual = stdout.getvalue()
        expected = ""
        self.assertIsNone(returned)
        self.assertEqual(actual, expected)

    @mock.patch('sys.stdout', new_callable=six.StringIO)
    def test_watch_tasks(self, stdout):
        # self.setup_record('foo.json')
        cfile = os.path.dirname(__file__) + '/data/calls/watchtasks1.json'
        with open(cfile) as fp:
            cdata = json.load(fp)
        self.session.load_calls(cdata)
        rv = watch_tasks(self.session, [1188], quiet=False, poll_interval=0)
        self.assertEqual(rv, 0)
        expected = (
'''Watching tasks (this may be safely interrupted)...
1188 build (f24, /users/mikem/fake.git:adaf62586b4b4a23b24394da5586abd7cd9f679e): closed
  1189 buildSRPMFromSCM (/users/mikem/fake.git:adaf62586b4b4a23b24394da5586abd7cd9f679e): closed
  1190 buildArch (fake-1.1-21.src.rpm, noarch): closed

1188 build (f24, /users/mikem/fake.git:adaf62586b4b4a23b24394da5586abd7cd9f679e) completed successfully
''')
        self.assertMultiLineEqual(stdout.getvalue(), expected)

    @mock.patch('time.sleep')
    @mock.patch('sys.stdout', new_callable=six.StringIO)
    def test_watch_tasks_fail(self, stdout, sleep):
        # self.setup_record('foo.json')
        cfile = os.path.dirname(__file__) + '/data/calls/watchtasks2.json'
        with open(cfile) as fp:
            cdata = json.load(fp)
        self.session.load_calls(cdata)
        rv = watch_tasks(self.session, [1208], quiet=False, poll_interval=5)
        self.assertEqual(rv, 1)
        expected = ('''Watching tasks (this may be safely interrupted)...
1208 build (f24, /users/mikem/fake.git:master): free
1208 build (f24, /users/mikem/fake.git:master): free -> open (builder-01)
  1209 buildSRPMFromSCM (/users/mikem/fake.git:master): free
  1209 buildSRPMFromSCM (/users/mikem/fake.git:master): free -> open (builder-01)
1208 build (f24, /users/mikem/fake.git:master): open (builder-01) -> FAILED: GenericError: Build already exists (id=425, state=COMPLETE): {'name': 'fake', 'task_id': 1208, 'extra': None, 'pkg_id': 298, 'epoch': 7, 'completion_time': None, 'state': 0, 'version': '1.1', 'source': None, 'volume_id': 0, 'owner': 1, 'release': '22', 'start_time': 'NOW'}
  0 free  1 open  0 done  1 failed
  1209 buildSRPMFromSCM (/users/mikem/fake.git:master): open (builder-01) -> closed
  0 free  0 open  1 done  1 failed

1208 build (f24, /users/mikem/fake.git:master) failed
''')
        self.assertMultiLineEqual(stdout.getvalue(), expected)

    @mock.patch('time.sleep')
    @mock.patch('sys.stdout', new_callable=six.StringIO)
    def test_watch_tasks_with_keyboardinterrupt(self, stdout, sleep):
        """Raise KeyboardInterrupt inner watch_tasks.
        Raising it by SIGNAL might be better"""
        cfile = os.path.dirname(__file__) + '/data/calls/watchtasks2.json'
        with open(cfile) as fp:
            cdata = json.load(fp)
        self.session.load_calls(cdata)
        sleep.side_effect = [None] * 10  + [KeyboardInterrupt]
        with self.assertRaises(KeyboardInterrupt):
            # watch_tasks catches and re-raises it to display a message
            watch_tasks(self.session, [1208], quiet=False, poll_interval=5)
        expected = ('''Watching tasks (this may be safely interrupted)...
1208 build (f24, /users/mikem/fake.git:master): free
1208 build (f24, /users/mikem/fake.git:master): free -> open (builder-01)
  1209 buildSRPMFromSCM (/users/mikem/fake.git:master): free
  1209 buildSRPMFromSCM (/users/mikem/fake.git:master): free -> open (builder-01)
Tasks still running. You can continue to watch with the '%s watch-task' command.
Running Tasks:
1208 build (f24, /users/mikem/fake.git:master): open (builder-01)
  1209 buildSRPMFromSCM (/users/mikem/fake.git:master): open (builder-01)
''' % (os.path.basename(sys.argv[0]) or 'koji'))
        self.assertMultiLineEqual(stdout.getvalue(), expected)

    @mock.patch('time.sleep')
    @mock.patch('sys.stdout', new_callable=six.StringIO)
    def test_watch_tasks_with_keyboardinterrupt_handler(self, stdout, sleep):
        """Raise KeyboardInterrupt inner watch_tasks with a ki_handler"""
        cfile = os.path.dirname(__file__) + '/data/calls/watchtasks2.json'
        with open(cfile) as fp:
            cdata = json.load(fp)
        self.session.load_calls(cdata)
        sleep.side_effect = [None] * 10 + [KeyboardInterrupt]

        def customized_handler(progname, tasks, quiet):
            print('some output')

        with self.assertRaises(KeyboardInterrupt):
            # watch_tasks catches and re-raises it to display a message
            watch_tasks(self.session, [1208], quiet=False, poll_interval=5,
                        ki_handler=customized_handler)
        expected = ('''Watching tasks (this may be safely interrupted)...
1208 build (f24, /users/mikem/fake.git:master): free
1208 build (f24, /users/mikem/fake.git:master): free -> open (builder-01)
  1209 buildSRPMFromSCM (/users/mikem/fake.git:master): free
  1209 buildSRPMFromSCM (/users/mikem/fake.git:master): free -> open (builder-01)
some output
''')
        self.assertMultiLineEqual(stdout.getvalue(), expected)


if __name__ == '__main__':
    unittest.main()
