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

        # test skipped entry less than delay
        start = 10000
        task = {'id': 100}
        self.tm.skipped_tasks = {task['id']: start}
        self.time.return_value = start + 100
        self.assertEqual(self.tm.checkAvailDelay(task), True)

        # and greater than delay
        self.time.return_value = start + 200
        self.tm.skipped_tasks = {task['id']: start}
        self.assertEqual(self.tm.checkAvailDelay(task), False)

        # and no entry
        self.time.return_value = start
        self.tm.skipped_tasks = {}
        self.assertEqual(self.tm.checkAvailDelay(task), True)

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
