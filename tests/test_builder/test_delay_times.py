from __future__ import absolute_import
import mock
try:
    import unittest2 as unittest
except ImportError:
    import unittest

import koji.daemon
import koji


class TestDelayTimes(unittest.TestCase):

    def setUp(self):
        self.options = mock.MagicMock()
        self.session = mock.MagicMock()
        self.tm = koji.daemon.TaskManager(self.options, self.session)
        self.time = mock.patch('time.time').start()

    def tearDown(self):
        mock.patch.stopall()

    def test_check_avail_delay(self):
        self.options.task_avail_delay = 180  # same as default

        # highest capacity, no skip entry
        start = 10000
        task = {'id': 100}
        self.tm.skipped_tasks = {}
        self.time.return_value = start
        bin_avail = [10.0, 9.0, 8.0, 7.0]
        our_avail = 10.0
        chk = self.tm.checkAvailDelay(task, bin_avail, our_avail)
        self.assertEqual(chk, False)

        # not highest, no skip entry
        our_avail = 9.0
        self.tm.skipped_tasks = {}
        chk = self.tm.checkAvailDelay(task, bin_avail, our_avail)
        self.assertEqual(chk, True)

        # last, but past full delay
        self.tm.skipped_tasks = {task['id']: start}
        our_avail = 7.0
        self.options.task_avail_delay = 500
        self.time.return_value = start + 500
        chk = self.tm.checkAvailDelay(task, bin_avail, our_avail)
        self.assertEqual(chk, False)

        # last, but less than delay
        self.tm.skipped_tasks = {task['id']: start}
        our_avail = 7.0
        self.time.return_value = start + 499
        chk = self.tm.checkAvailDelay(task, bin_avail, our_avail)
        self.assertEqual(chk, True)

        # median, but less than scaled delay
        self.tm.skipped_tasks = {task['id']: start}
        bin_avail = [10.0, 9.0, 8.0, 7.0, 6.0]
        our_avail = 8.0
        # rank = 2/4 = 0.5, so adjusted delay is 250
        self.time.return_value = start + 249
        chk = self.tm.checkAvailDelay(task, bin_avail, our_avail)
        self.assertEqual(chk, True)

        # median, but past scaled delay
        self.tm.skipped_tasks = {task['id']: start}
        bin_avail = [10.0, 9.0, 8.0, 7.0, 6.0]
        our_avail = 8.0
        # rank = 2/4 = 0.5, so adjusted delay is 250
        self.time.return_value = start + 251
        chk = self.tm.checkAvailDelay(task, bin_avail, our_avail)
        self.assertEqual(chk, False)

        # only one in bin
        self.tm.skipped_tasks = {}
        bin_avail = [5.0]
        our_avail = 5.0
        self.time.return_value = start
        chk = self.tm.checkAvailDelay(task, bin_avail, our_avail)
        self.assertEqual(chk, False)


    def test_clean_delay_times(self):
        self.options.task_avail_delay = 180  # same as default

        # test no skipped entries
        start = 10000
        self.time.return_value = start + 100
        self.tm.skipped_tasks = {}
        self.tm.cleanDelayTimes()
        self.assertEqual(self.tm.skipped_tasks, {})

        # test all skipped entries
        self.time.return_value = start + 5000
        skipped = {}
        for i in range(25):
            skipped[i] = start + i
            # all older than 180 in age
        self.tm.skipped_tasks = skipped
        self.tm.cleanDelayTimes()
        self.assertEqual(self.tm.skipped_tasks, {})

        # test mixed entries
        skipped = {100: start + 5000}
        expected = skipped.copy()
        for i in range(25):
            skipped[i] = start + i
            # all older than 180 in age
        self.tm.skipped_tasks = skipped
        self.tm.cleanDelayTimes()
        self.assertEqual(self.tm.skipped_tasks, expected)
