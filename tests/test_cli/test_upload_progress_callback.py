import unittest
import mock
import sys
import StringIO as stringio

import loadcli

cli = loadcli.cli


class TestUploadProgressCallBack(unittest.TestCase):

    maxDiff = None

    def test_format_size(self):
        self.assertEqual(cli._format_size(2000000000), '1.86 GiB')
        self.assertEqual(cli._format_size(1073741824), '1.00 GiB')
        self.assertEqual(cli._format_size(3000000), '2.86 MiB')
        self.assertEqual(cli._format_size(1048576), '1.00 MiB')
        self.assertEqual(cli._format_size(4000), '3.91 KiB')
        self.assertEqual(cli._format_size(1024), '1.00 KiB')
        self.assertEqual(cli._format_size(500), '500.00 B')

    def test_format_secs(self):
        self.assertEqual(cli._format_secs(0), '00:00:00')
        self.assertEqual(cli._format_secs(60), '00:01:00')
        self.assertEqual(cli._format_secs(3600), '01:00:00')
        self.assertEqual(cli._format_secs(7283294), '2023:08:14')
        self.assertEqual(cli._format_secs(1234), '00:20:34')
        self.assertEqual(cli._format_secs(4321), '01:12:01')
        self.assertEqual(cli._format_secs(4321.567), '01:12:01')

    @mock.patch('sys.stdout', new_callable=stringio.StringIO)
    def test_progress_callback(self, stdout):
        cli._progress_callback(12300, 234000, 5670, 80, 900)
        cli._progress_callback(45600, 234000, 5670, 0, 900)
        cli._progress_callback(234000, 234000, 5670, 80, 900)
        self.assertMultiLineEqual(
            stdout.getvalue(),
            '[=                                   ]  05% 00:15:00  12.01 KiB    70.88 B/sec\r'
            '[=======                             ]  19% 00:15:00  44.53 KiB        - B/sec\r'
            '[====================================] 100% 00:15:00 228.52 KiB   260.00 B/sec\r')


if __name__ == '__main__':
    unittest.main()
