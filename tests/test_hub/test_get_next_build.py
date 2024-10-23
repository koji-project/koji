from unittest import mock
import unittest
import koji
import kojihub

from psycopg2._psycopg import IntegrityError


class TestGetNextBuild(unittest.TestCase):

    def setUp(self):
        self.get_next_release = mock.patch('kojihub.kojihub.get_next_release').start()
        self.new_build = mock.patch('kojihub.kojihub.new_build').start()
        self._dml = mock.patch('kojihub.kojihub._dml').start()
        self.binfo = {'name': 'name', 'version': 'version'}

    def tearDown(self):
        mock.patch.stopall()

    def test_get_next_build_simple(self):
        # typical case
        self.get_next_release.return_value = '2.mydist'
        self.new_build.return_value = 'mybuild'
        result = kojihub.get_next_build(self.binfo)
        self.assertEqual(result, 'mybuild')
        self.new_build.assert_called_once()
        # release value should be passed to new_build
        self.assertEqual(self.new_build.call_args[0][0]['release'], '2.mydist')

    def test_get_next_build_have_release(self):
        # if a release is passed, get_next_release should not be called
        self.binfo['release'] = '42'
        result = kojihub.get_next_build(self.binfo)
        self.new_build.assert_called_once()
        self.get_next_release.assert_not_called()
        # release value should be passed to new_build
        self.assertEqual(self.new_build.call_args[0][0]['release'], '42')

    def test_get_next_build_retry(self):
        # set up new_build to fail a few times
        nb_callnum = 0
        def my_new_build(data, strict=False):
            nonlocal nb_callnum
            nb_callnum += 1
            if nb_callnum < 3:
                raise IntegrityError('fake error')
            return 'mybuild'
        self.new_build.side_effect = my_new_build

        self.get_next_release.return_value = '2.mydist'

        result = kojihub.get_next_build(self.binfo)
        self.assertEqual(result, 'mybuild')
        self.assertEqual(len(self.new_build.mock_calls), 3)
        self.assertEqual(len(self.get_next_release.mock_calls), 3)
        # incr arg should have incremented on successive tries
        self.assertEqual(self.get_next_release.mock_calls[1][1][1], 2)
        self.assertEqual(self.get_next_release.mock_calls[2][1][1], 3)

    def test_get_next_build_fail(self):
        # set up new_build to fail forever
        self.new_build.side_effect = IntegrityError('fake error')
        self.get_next_release.return_value = '2.mydist'

        with self.assertRaises(koji.GenericError):
            result = kojihub.get_next_build(self.binfo)

        # there should have been ten tries
        self.assertEqual(len(self.new_build.mock_calls), 8)
        self.assertEqual(len(self.get_next_release.mock_calls), 9)
        # incr arg should have incremented on successive tries
        for i in range(1, 9):
            self.assertEqual(self.get_next_release.mock_calls[i][1][1], i+1)
