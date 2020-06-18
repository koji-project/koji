import mock
import unittest

import kojihub

class TestListTaskOutput(unittest.TestCase):
    @mock.patch('os.path.isdir')
    @mock.patch('os.walk')
    def test_empty(self, walk, isdir):
        isdir.return_value = True
        walk.return_value = []
        result = kojihub.list_task_output(1)
        self.assertEqual(result, [])

    @mock.patch('os.path.isdir')
    @mock.patch('os.walk')
    def test_simple(self, walk, isdir):
        isdir.return_value = True
        walk.return_value = (('dir', [], ['file']),)
        result = kojihub.list_task_output(1)
        self.assertEqual(result, ['file'])

    @mock.patch('os.stat')
    @mock.patch('os.path.isdir')
    @mock.patch('os.walk')
    def test_simple_stat(self, walk, isdir, stat):
        isdir.return_value = True
        walk.return_value = (('dir', [], ['file']),)
        st_mock = mock.MagicMock()
        st_mock.st_size = 123
        st_mock.st_atime = 345
        st_mock.st_mtime = 678
        st_mock.st_ctime = 901
        stat.return_value = st_mock
        result = kojihub.list_task_output(1, stat=True)

        self.assertEqual(result, {
            'file': {
                'st_size': '123',
                'st_atime': 345,
                'st_mtime': 678,
                'st_ctime': 901,
            }
        })

    @mock.patch('kojihub.list_volumes')
    @mock.patch('os.stat')
    @mock.patch('os.path.isdir')
    @mock.patch('os.walk')
    def test_volumes(self, walk, isdir, stat, list_volumes):
        isdir.return_value = True
        walk.return_value = (('dir', [], ['file']),)
        st_mock = mock.MagicMock()
        st_mock.st_size = 123
        st_mock.st_atime = 345
        st_mock.st_mtime = 678
        st_mock.st_ctime = 901
        stat.return_value = st_mock
        list_volumes.return_value = [{'name': 'DEFAULT'}]
        result = kojihub.list_task_output(1, all_volumes=True)
        self.assertEqual(result, {'file': ['DEFAULT']})

    @mock.patch('kojihub.list_volumes')
    @mock.patch('os.stat')
    @mock.patch('os.path.isdir')
    @mock.patch('os.walk')
    def test_volumes_stat(self, walk, isdir, stat, list_volumes):
        isdir.return_value = True
        walk.return_value = (('dir', [], ['file']),)
        st_mock = mock.MagicMock()
        st_mock.st_size = 123
        st_mock.st_atime = 345
        st_mock.st_mtime = 678
        st_mock.st_ctime = 901
        stat.return_value = st_mock
        list_volumes.return_value = [{'name': 'DEFAULT'}]
        result = kojihub.list_task_output(1, stat=True, all_volumes=True)

        self.assertEqual(result, {
            'file': {
                'DEFAULT': {
                    'st_size': '123',
                    'st_atime': 345,
                    'st_mtime': 678,
                    'st_ctime': 901,
                }
            }
        })
