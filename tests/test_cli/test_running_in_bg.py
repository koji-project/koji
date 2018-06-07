from __future__ import absolute_import
import mock
try:
    import unittest2 as unittest
except ImportError:
    import unittest

from koji_cli.lib import _running_in_bg

class TestRunningInBg(unittest.TestCase):

    @mock.patch('koji_cli.lib.os')
    def test_running_in_bg(self, os_mock):
        os_mock.isatty.return_value = False
        self.assertTrue(_running_in_bg())
        os_mock.isatty.return_value = True
        os_mock.getpgrp.return_value = 0
        os_mock.tcgetpgrp.return_value = 1
        self.assertTrue(_running_in_bg())
        os_mock.tcgetpgrp.return_value = 0
        self.assertFalse(_running_in_bg())

        os_mock.reset_mock()
        os_mock.tcgetpgrp.side_effect = OSError
        self.assertTrue(_running_in_bg())
        os_mock.isatty.assert_called()
        os_mock.getpgrp.assert_called()
        os_mock.tcgetpgrp.assert_called()

        os_mock.reset_mock()
        os_mock.getpgrp.side_effect = OSError
        self.assertTrue(_running_in_bg())
        os_mock.isatty.assert_called()
        os_mock.getpgrp.assert_called()
        os_mock.tcgetpgrp.assert_not_called()

        os_mock.reset_mock()
        os_mock.isatty.side_effect = OSError
        self.assertTrue(_running_in_bg())
        os_mock.isatty.assert_called()
        os_mock.getpgrp.assert_not_called()
        os_mock.tcgetpgrp.assert_not_called()


if __name__ == '__main__':
    unittest.main()
