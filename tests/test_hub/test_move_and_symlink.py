import mock
try:
    import unittest2 as unittest
except ImportError:
    import unittest

import kojihub

class TestMoveAndSymlink(unittest.TestCase):
    @mock.patch('koji.ensuredir')
    @mock.patch('kojihub.safer_move')
    @mock.patch('os.symlink')
    def test_valid(self, symlink, safer_move, ensuredir):
        kojihub.move_and_symlink('/dir_a/src', '/dir_b/dst', relative=False, create_dir=False)

        ensuredir.assert_not_called()
        safer_move.assert_called_once_with('/dir_a/src', '/dir_b/dst')
        symlink.assert_called_once_with('/dir_b/dst', '/dir_a/src')

    @mock.patch('koji.ensuredir')
    @mock.patch('kojihub.safer_move')
    @mock.patch('os.symlink')
    def test_valid_relative(self, symlink, safer_move, ensuredir):
        kojihub.move_and_symlink('/a/src', '/b/dst', relative=True, create_dir=False)

        safer_move.assert_called_once_with('/a/src', '/b/dst')
        symlink.assert_called_once_with('../b/dst', '/a/src')
        ensuredir.assert_not_called()

    @mock.patch('koji.ensuredir')
    @mock.patch('kojihub.safer_move')
    @mock.patch('os.symlink')
    def test_valid_create_dir(self, symlink, safer_move, ensuredir):
        kojihub.move_and_symlink('a/src', 'b/dst', relative=True, create_dir=True)

        safer_move.assert_called_once_with('a/src', 'b/dst')
        symlink.assert_called_once_with('../b/dst', 'a/src')
        ensuredir.assert_called_once_with('b')
