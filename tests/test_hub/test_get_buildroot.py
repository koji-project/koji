import mock
import unittest

import koji
import kojihub


class TestGetBuildroot(unittest.TestCase):
    def setUp(self):
        self.query_buildroots = mock.patch('kojihub.query_buildroots').start()
        self.buildroot_id = 1

    def test_empty_buildroots_without_strict(self):
        self.query_buildroots.return_value = []
        rv = kojihub.get_buildroot(self.buildroot_id, strict=False)
        self.assertEqual(None, rv)

    def test_empty_buildroots_with_strict(self):
        self.query_buildroots.return_value = []
        with self.assertRaises(koji.GenericError) as cm:
            kojihub.get_buildroot(self.buildroot_id, strict=True)
        self.assertEqual("No such buildroot: %r" % self.buildroot_id, str(cm.exception))

    def test_more_buildroots(self):
        self.query_buildroots.return_value = [
            {'arch': 'x86_64', 'id': 1, 'repo_id': 1, 'repo_state': 1, 'tag_id': 2,
             'tag_name': 'f34-build-7war', 'task_id': 4},
            {'arch': 'x86_64', 'id': 1, 'repo_id': 1, 'repo_state': 1, 'tag_id': 2,
             'tag_name': 'f34-build-7war', 'task_id': 4}
        ]
        with self.assertRaises(koji.GenericError) as cm:
            kojihub.get_buildroot(self.buildroot_id)
        self.assertEqual("More that one buildroot with id: %i" % self.buildroot_id,
                         str(cm.exception))

    def test_valid(self):
        buildroot_info = {'arch': 'x86_64', 'id': 1, 'repo_id': 1, 'repo_state': 1, 'tag_id': 2,
                          'tag_name': 'f34-build-7war', 'task_id': 4}
        self.query_buildroots.return_value = [buildroot_info]
        rv = kojihub.get_buildroot(self.buildroot_id, strict=False)
        self.assertEqual(buildroot_info, rv)
