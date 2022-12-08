import unittest

import mock

import koji
import kojihub

from koji.util import joinpath


class TestGetChangelogEntries(unittest.TestCase):

    def setUp(self):
        self.exports = kojihub.RootExports()
        self.get_build = mock.patch('kojihub.kojihub.get_build').start()
        self.context = mock.patch('kojihub.kojihub.context').start()
        self.cursor = mock.MagicMock()
        self.os_path_exists = mock.patch('os.path.exists').start()

    def test_non_exist_build(self):
        build_id = 1
        self.cursor.fetchone.return_value = None
        self.context.cnx.cursor.return_value = self.cursor
        self.get_build.return_value = None
        with self.assertRaises(koji.GenericError) as cm:
            self.exports.getChangelogEntries(buildID=build_id, strict=True)
        self.assertEqual(f"No such build: {build_id}", str(cm.exception))

    def test_taskid_invalid_path(self):
        filepath = '../test/path'
        with self.assertRaises(koji.GenericError) as cm:
            self.exports.getChangelogEntries(taskID=99, filepath=filepath)
        self.assertEqual(f"Invalid filepath: {filepath}", str(cm.exception))

    def test_taskid_without_filepath(self):
        with self.assertRaises(koji.GenericError) as cm:
            self.exports.getChangelogEntries(taskID=99)
        self.assertEqual("filepath must be specified with taskID", str(cm.exception))

    def test_before_invalid_type(self):
        before = {'before': '1133456'}
        filepath = 'test/path'
        self.os_path_exists.return_value = True
        with self.assertRaises(koji.GenericError) as cm:
            self.exports.getChangelogEntries(taskID=99, before=before, filepath=filepath)
        self.assertEqual(f"Invalid type for before: {type(before)}", str(cm.exception))

    def test_after_invalid_type(self):
        after = {'after': '1133456'}
        filepath = 'test/path'
        self.os_path_exists.return_value = True
        with self.assertRaises(koji.GenericError) as cm:
            self.exports.getChangelogEntries(taskID=99, after=after, filepath=filepath)
        self.assertEqual(f"Invalid type for after: {type(after)}", str(cm.exception))

    def test_srpm_path_not_exist(self):
        filepath = 'test/path'
        task_id = 99
        srpm_path = joinpath(koji.pathinfo.work(),
                             koji.pathinfo.taskrelpath(task_id),
                             filepath)
        self.os_path_exists.return_value = False
        with self.assertRaises(koji.GenericError) as cm:
            self.exports.getChangelogEntries(taskID=task_id, filepath=filepath, strict=True)
        self.assertEqual(f"SRPM {srpm_path} doesn't exist", str(cm.exception))
