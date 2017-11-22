from __future__ import absolute_import
import json
import mock
import os
import six
import sys
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

    @mock.patch('sys.stdout', new_callable=six.StringIO)
    def test_watch_tasks_with_keyboardinterrupt(self, stdout):
        """Raise KeyboardInterrupt inner watch_tasks.
        Raising it by SIGNAL might be better"""
        pass  # TODO


if __name__ == '__main__':
    unittest.main()
