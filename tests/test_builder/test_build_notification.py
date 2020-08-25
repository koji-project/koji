from __future__ import absolute_import

import json
import locale
import os
import tempfile
import time

import mock
import six

import koji
import koji.util
from .loadkojid import kojid

try:
    import unittest2 as unittest
except ImportError:
    import unittest



class MyClientSession(koji.ClientSession):

    def __init__(self, *a, **kw):
        super(MyClientSession, self).__init__(*a, **kw)
        self._testcalls = {}

    def load_calls(self, name):
        fn = os.path.join(os.path.dirname(__file__), 'data/calls', name,'calls.json')
        with open(fn) as fp:
            data = json.load(fp)
        for call in data:
            key = self._munge([call['method'], call['args'], call['kwargs']])
            self._testcalls[key] = call

    def _callMethod(self, name, args, kwargs=None, retry=True):
        if self.multicall:
            raise Exception('multicall not supported')
        key = self._munge([name, args, kwargs])
        if key in self._testcalls:
            return self._testcalls[key]['result']
        else:
            return mock.MagicMock()

    def _munge(self, data):
        def callback(value):
            if isinstance(value, list):
                return tuple(value)
            elif isinstance(value, dict):
                keys = sorted(value.keys())
                return tuple([(k, value[k]) for k in keys])
            else:
                return value
        walker = koji.util.DataWalker(data, callback)
        return walker.walk()


class TestBuildNotification(unittest.TestCase):

    def setUp(self):
        self.maxDiff = None
        self.original_timezone = os.environ.get('TZ')
        os.environ['TZ'] = 'US/Eastern'
        time.tzset()
        self.tempdir = tempfile.mkdtemp()
        self.SMTP = mock.patch('smtplib.SMTP').start()
        self.session = mock.MagicMock()
        self.options = mock.MagicMock()
        self.options.topdir = self.tempdir
        self.options.workdir = self.tempdir

    def tearDown(self):
        if self.original_timezone is None:
            del os.environ['TZ']
        else:
            os.environ['TZ'] = self.original_timezone
        time.tzset()
        mock.patch.stopall()

    def test_build_notification(self):
        # force locale to compare 'message' value
        locale.setlocale(locale.LC_ALL, ('en_US', 'UTF-8'))
        # task_info['id'], method, params, self.session, self.options
        task_id = 999
        fn = os.path.join(os.path.dirname(__file__), 'data/calls', 'build_notif_1', 'params.json')
        with open(fn) as fp:
            kwargs = json.load(fp)
        self.session = MyClientSession('https://koji.example.com/kojihub')
        self.session.load_calls('build_notif_1')
        self.options.from_addr = "koji@example.com"
        server = mock.MagicMock()
        self.SMTP.return_value = server

        # run it
        handler = kojid.BuildNotificationTask(
                    task_id,
                    'buildNotification',
                    koji.encode_args(**kwargs),
                    self.session,
                    self.options)
        ret = handler.run()

        self.assertEqual(ret, "sent notification of build 612609 to: user@example.com")

        # check sendmail args
        from_addr, recipients, message = server.sendmail.call_args[0]
        self.assertEqual(from_addr, "koji@example.com")
        self.assertEqual(recipients, ["user@example.com"])
        fn = os.path.join(os.path.dirname(__file__), 'data/calls', 'build_notif_1', 'message.txt')
        with open(fn, 'rb') as fp:
            msg_expect = fp.read()
        if six.PY2:
            msg_expect = msg_expect.decode()
        self.assertMultiLineEqual(message.decode(), msg_expect.decode())
        locale.resetlocale()
