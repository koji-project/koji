from __future__ import absolute_import

import os.path
import shutil
import signal
import tempfile
import time
import unittest

import mock
import pytest

import koji

from . import loadkojira

kojira = loadkojira.kojira


class MyError(Exception):
    """sentinel exception"""
    pass


class MainTest(unittest.TestCase):

    def setUp(self):
        self.start_thread = mock.patch.object(kojira, 'start_thread').start()
        self.repomgr = mock.MagicMock()
        self.RepoManager = mock.patch.object(kojira, 'RepoManager', return_value=self.repomgr).start()
        self.session = mock.MagicMock()
        self.options = mock.MagicMock()
        self.options.sleeptime = 1
        self.workdir = tempfile.mkdtemp()
        self.topdir = self.workdir + '/koji'
        self.pathinfo = koji.PathInfo(self.topdir)
        mock.patch.object(kojira, 'pathinfo', create=True, new=self.pathinfo).start()
        self.logger = mock.patch.object(kojira, 'logger', create=True).start()
        self.sleep = mock.patch('time.sleep').start()
        self.signal = mock.patch('signal.signal').start()

    def tearDown(self):
        mock.patch.stopall()
        shutil.rmtree(self.workdir)

    def test_userkill1(self):
        self.sleep.side_effect = [None] * 10 + [KeyboardInterrupt()]
        kojira.main(self.options, self.session)

    def test_terminal_errors(self):
        for cls in KeyboardInterrupt, koji.AuthExpired, koji.AuthError, SystemExit:
            err = cls()
            self.sleep.side_effect = [None] * 10 + [Exception()]
            self.repomgr.updateRepos.side_effect = [None] * 5 + [err]
            kojira.main(self.options, self.session)
            self.assertEqual(len(self.repomgr.pruneLocalRepos.mock_calls), 5)
            self.repomgr.reset_mock()

    def test_nonterminal_error(self):
        err = MyError()
        self.sleep.side_effect = [None] * 10 + [KeyboardInterrupt()]
        self.repomgr.updateRepos.side_effect = [None] * 5 + [err] * 6
        kojira.main(self.options, self.session)
        self.assertEqual(len(self.repomgr.updateRepos.mock_calls), 11)
        self.assertEqual(len(self.repomgr.pruneLocalRepos.mock_calls), 5)
        self.repomgr.reset_mock()

    def test_shutdown_handler(self):
        self.signal.side_effect = [Exception('stop here')]
        with self.assertRaises(Exception):
            kojira.main(self.options, self.session)

        # grab the handler
        self.assertEqual(self.signal.mock_calls[0][1][0], signal.SIGTERM)
        handler = self.signal.mock_calls[0][1][1]

        self.signal.side_effect = None

        # make sure the handler does what it should
        with self.assertRaises(SystemExit):
            handler()


# the end
