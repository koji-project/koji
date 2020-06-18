import mock

import unittest

import kojihub


class TestSavepoint(unittest.TestCase):

    def setUp(self):
        self.dml = mock.patch('kojihub._dml').start()

    def tearDown(self):
        mock.patch.stopall()

    def test_savepoint(self):
        sp = kojihub.Savepoint('some_name')
        self.assertEqual(sp.name, 'some_name')
        self.dml.assert_called_once_with('SAVEPOINT some_name', {})

        self.dml.reset_mock()
        sp.rollback()
        self.dml.assert_called_once_with('ROLLBACK TO SAVEPOINT some_name', {})
