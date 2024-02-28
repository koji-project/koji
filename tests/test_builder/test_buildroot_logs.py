from __future__ import absolute_import
import logging
import mock
import os
import shutil
import tempfile
import unittest

import koji.daemon
import koji

from .loadkojid import kojid


class TestBuildRootLogs(unittest.TestCase):

    def setUp(self):
        self.broot = mock.MagicMock()
        self.broot.logger = logging.getLogger("koji.build.buildroot")
        self.broot.incremental_log.side_effect = self.my_incremental_log
        self.offsets = {}
        self.contents = {}
        self.session = mock.MagicMock()
        self.tempdir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tempdir)
        mock.patch.stopall()

    def my_incremental_log(self, fname, fd):
        self.offsets.setdefault(fname, []).append(fd.tell())
        self.contents.setdefault(fname, []).append(fd.read())

    def test_simple(self):
        patterns = ['%s/*.log' % self.tempdir]
        mylogs = ['%s/test-%02i.log' % (self.tempdir, i) for i in range(4)]
        for fn in mylogs:
            with open(fn, 'wt') as fo:
                fo.write('hello\n')
        notlogs = ['%s/test-%02i.rpm' % (self.tempdir, i) for i in range(4)]
        for fn in notlogs:
            with open(fn, 'wt') as fo:
                fo.write('this is not a log')

        logs = kojid.BuildRootLogs(self.broot, patterns)

        # first sync
        logs.sync_logs()
        self.assertEqual(logs.ts_logs, {})
        self.assertEqual(sorted(logs.loginfo.keys()), mylogs)
        self.assertEqual(len(self.broot.incremental_log.mock_calls), 4)

        # sync again, no file changes
        self.broot.reset_mock()
        logs.sync_logs()
        self.assertEqual(logs.ts_logs, {})
        self.assertEqual(sorted(logs.loginfo.keys()), mylogs)
        self.assertEqual(len(self.broot.incremental_log.mock_calls), 4)

        # new file
        mylogs.append('%s/test-new-file.log' % self.tempdir)
        with open(mylogs[-1], 'wt') as fo:
            fo.write('hello')
        self.broot.reset_mock()
        logs.sync_logs()
        self.assertEqual(logs.ts_logs, {})
        self.assertEqual(sorted(logs.loginfo.keys()), mylogs)
        self.assertEqual(len(self.broot.incremental_log.mock_calls), 5)

        logs.close_logs()

    def test_timestamp(self):
        patterns = ['%s/*.log' % self.tempdir]
        mylog = '%s/test.log' % (self.tempdir)
        with open(mylog, 'wt') as fo:
            fo.write('hello\n')
        workdir = '%s/work' % self.tempdir
        os.makedirs(workdir)
        self.broot.workdir = workdir

        logs = kojid.BuildRootLogs(self.broot, patterns, with_ts=True)

        # first sync
        with mock.patch('time.time', return_value=100):
            logs.sync_logs()
        self.assertEqual(sorted(logs.loginfo.keys()), [mylog])
        ts_log = '%s/test.log-ts.log' % workdir
        self.assertEqual(sorted(logs.ts_logs.keys()), [ts_log])
        self.assertEqual(len(self.broot.incremental_log.mock_calls), 2)

        # sync again with file update
        self.broot.reset_mock()
        with open(mylog, 'at') as fo:
            fo.write('hello\n')
        with mock.patch('time.time', return_value=200):
            logs.sync_logs()

        logs.close_logs()

        with open(ts_log, 'rt') as fo:
            contents = fo.read()
        self.assertEqual(contents, '100 0\n100 6\n200 12\n')


    def test_truncate(self):
        patterns = ['%s/*.log' % self.tempdir]
        mylog = '%s/test.log' % (self.tempdir)
        with open(mylog, 'wt') as fo:
            fo.write('hello\n')

        logs = kojid.BuildRootLogs(self.broot, patterns)

        # first sync
        logs.sync_logs()
        self.assertEqual(sorted(logs.loginfo.keys()), [mylog])

        # truncate and rsync again
        with open(mylog, 'wt') as fo:
            pass
        logs.sync_logs()

        # append and sync again
        with open(mylog, 'at') as fo:
            fo.write('...\n')
        logs.sync_logs()

        self.assertEqual(self.contents['test.log'], [b'hello\n', b'', b'...\n'])

    def test_log_disappears(self):
        patterns = ['%s/*.log' % self.tempdir]
        mylog = '%s/test.log' % (self.tempdir)
        with open(mylog, 'wt') as fo:
            fo.write('hello\n')

        logs = kojid.BuildRootLogs(self.broot, patterns)

        # first sync
        logs.sync_logs()
        self.assertEqual(sorted(logs.loginfo.keys()), [mylog])

        # delete and sync again
        os.unlink(mylog)
        logs.sync_logs()

        self.assertEqual(self.contents['test.log'], [b'hello\n'])

        # and again
        logs.sync_logs()
        self.assertEqual(self.contents['test.log'], [b'hello\n'])

        # re-create and sync
        with open(mylog, 'wt') as fo:
            fo.write('world\n')
        logs.sync_logs()

        self.assertEqual(self.contents['test.log'], [b'hello\n', b'world\n'])

    def test_no_workdir(self):
        patterns = ['%s/*.log' % self.tempdir]

        self.broot.workdir = None
        logs = kojid.BuildRootLogs(self.broot, patterns, with_ts=True)
        self.assertEqual(logs.with_ts, False)

    def test_name_overlap(self):
        mylog = '%s/test.log' % (self.tempdir)
        os.mkdir('%s/dup' % self.tempdir)
        mydup = '%s/dup/test.log' % (self.tempdir)
        for fn in mylog, mydup:
            with open(fn, 'wt') as fo:
                fo.write('hello\n')
        patterns = [
            '%s/*.log' % self.tempdir,
            '%s/*/*.log' % self.tempdir,
        ]

        logs = kojid.BuildRootLogs(self.broot, patterns)

        # first sync
        logs.sync_logs()
        self.assertEqual(sorted(logs.loginfo.keys()), [mydup, mylog])
        self.assertEqual(logs.loginfo[mylog]['name'], 'test.log')
        self.assertEqual(logs.loginfo[mydup]['name'], 'test.DUP00.log')

    def test_stray_ts_log(self):
        logs = kojid.BuildRootLogs(self.broot, [])
        stray = '%s/test.log-ts.log' % (self.tempdir)
        logs.add_log(stray)
        if stray not in logs.ignored:
            raise Exception('stray log not ignored')
        if stray in logs.loginfo:
            raise Exception('stray log not ignored')


