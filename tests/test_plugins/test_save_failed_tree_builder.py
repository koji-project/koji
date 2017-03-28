import mock
import os
import sys
import unittest

# alter pythonpath to not load hub plugin
sys.path = [os.path.join(os.path.dirname(__file__), '../../plugins/builder')] + sys.path
#raise(Exception(sys.path))

import koji
# inject builder data
from tests.test_builder.loadkojid import kojid
import __main__
__main__.BuildRoot = kojid.BuildRoot

from save_failed_tree import SaveFailedTreeTask

class TestSaveFailedTree(unittest.TestCase):
    def setUp(self):
        self.session = mock.MagicMock()
        self.session.host.getHost.return_value = {'id': 1}
        options = mock.MagicMock()
        options.workdir = '/tmp/nonexistentdirectory'
        options.mockdir = '/tmp/mockdir'
        options.name = 'name'
        self.t = SaveFailedTreeTask(123, 'saveFailedTree', {}, self.session, options)

    @mock.patch('os.unlink')
    @mock.patch('tarfile.open')
    def testNonExistentTask(self, tarfile, os_unlink):
        # empty tarball
        tfile = mock.MagicMock(name='tfile')
        tarfile.return_value = tfile

        self.t.handler(1)

        tarfile.assert_called_once_with(
            '/tmp/nonexistentdirectory/tasks/123/123/broots-task-1.tar.gz',
            'w:gz'
        )
        tfile.add.assert_not_called()
        tfile.close.assert_called_once_with()
        os_unlink.assert_called_once_with('/tmp/nonexistentdirectory/tasks/123/123/broots-task-1.tar.gz')

    @mock.patch('os.unlink')
    @mock.patch('tarfile.open')
    def testCorrect(self, tarfile, os_unlink):
        def getBuildroot(bid):
            tmp = {
                'tag_name': 'tag_name',
                'repo_id': 'repo_id',
            }
            if bid == 1:
                tmp['task_id'] = 1000
                tmp['arch'] = 'x86_64'
                tmp['tag_id'] = 5000
            elif bid == 2:
                tmp['task_id'] = 1001
                tmp['arch'] = 'i386'
                tmp['tag_id'] = 5001
            return tmp

        self.session.getBuildroot.side_effect = getBuildroot
        tfile = mock.MagicMock(name='tfile')
        tfile.add = mock.MagicMock()
        tarfile.return_value = tfile
        # simplified return values, only id should be used
        self.session.listBuildroots.return_value = [{'id': 1, 'host_id': 1}, {'id': 2, 'host_id': 1}]

        self.t.handler(1)

        tarfile.assert_called_once_with(
            '/tmp/nonexistentdirectory/tasks/123/123/broots-task-1.tar.gz',
            'w:gz'
        )
        self.assertEqual(tfile.add.call_args_list[0][0][0], '/tmp/mockdir/tag_name-1-repo_id/root/builddir')
        self.assertEqual(tfile.add.call_args_list[1][0][0], '/tmp/mockdir/tag_name-2-repo_id/root/builddir')
        self.assertEqual(len(tfile.add.call_args_list), 2)
        tfile.close.assert_called_once_with()
        os_unlink.assert_called_once_with('/tmp/nonexistentdirectory/tasks/123/123/broots-task-1.tar.gz')

    @mock.patch('os.unlink')
    @mock.patch('tarfile.open')
    def testWrongBuilder(self, tarfile, os_unlink):
        def getBuildroot(bid):
            tmp = {
                'tag_name': 'tag_name',
                'repo_id': 'repo_id',
            }
            if bid == 1:
                tmp['task_id'] = 1000
                tmp['arch'] = 'x86_64'
                tmp['tag_id'] = 5000
            elif bid == 2:
                tmp['task_id'] = 1001
                tmp['arch'] = 'i386'
                tmp['tag_id'] = 5001
            return tmp

        self.session.getBuildroot.side_effect = getBuildroot
        tfile = mock.MagicMock(name='tfile')
        tarfile.return_value = tfile
        # simplified return values, only id should be used
        self.session.listBuildroots.return_value = [{'id': 1, 'host_id': 2}, {'id': 2, 'host_id': 2}]

        with self.assertRaises(koji.GenericError):
            self.t.handler(1)

    def testFull(self):
        pass

    def testFailUpload(self):
        pass
