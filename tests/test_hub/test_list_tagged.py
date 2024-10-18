import unittest

import koji
import kojihub
from unittest import mock
import copy

QP = kojihub.QueryProcessor


class TestListTagged(unittest.TestCase):
    def setUp(self):
        self.QueryProcessor = mock.patch('kojihub.kojihub.QueryProcessor',
                                         side_effect=self.getQuery).start()
        self.queries = []
        self.get_tag = mock.patch('kojihub.kojihub.get_tag').start()
        self.exports = kojihub.RootExports()
        self.context = mock.patch('kojihub.kojihub.context').start()
        self.cursor = mock.MagicMock()
        self.readTaggedBuilds = mock.patch('kojihub.kojihub.readTaggedBuilds').start()
        self.tag_name = 'test-tag'
        self.taginfo = {'id': 1, 'name': 'tag'}
        self.tagged_build = [
            {'build_id': 1, 'create_event': 1172, 'creation_event_id': 1171, 'epoch': None,
             'id': 1, 'name': 'test-pkg', 'nvr': 'test-pkg-2.52-1.fc35', 'owner_id': 1,
             'owner_name': 'kojiuser', 'package_id': 1, 'package_name': 'test-pkg',
             'release': '1.fc35', 'state': 1, 'tag_id': 1, 'tag_name': 'test-tag',
             'task_id': None, 'version': '2.52', 'volume_id': 0, 'volume_name': 'DEFAULT'}]

    def tearDown(self):
        mock.patch.stopall()

    def getQuery(self, *args, **kwargs):
        query = QP(*args, **kwargs)
        query.execute = mock.MagicMock()
        query.executeOne = mock.MagicMock()
        self.queries.append(query)
        return query

    def test_non_exist_tag_without_strict(self):
        self.get_tag.return_value = None
        self.exports.listTagged(self.tag_name, strict=False)
        self.assertEqual(len(self.queries), 0)

    def test_non_exist_tag_with_strict(self):
        error_message = "No such tagInfo: '%s'" % self.tag_name
        self.get_tag.side_effect = koji.GenericError(error_message)
        with self.assertRaises(koji.GenericError) as cm:
            self.exports.listTagged(self.tag_name)
        self.assertEqual(error_message, str(cm.exception))

    def test_list_tagged(self):
        self.get_tag.return_value = self.taginfo
        self.readTaggedBuilds.return_value = self.tagged_build
        rv = self.exports.listTagged(self.tag_name)
        self.assertEqual(rv, self.tagged_build)

    def test_list_tagged_with_extra(self):
        self.get_tag.return_value = self.taginfo
        tagged_build = copy.deepcopy(self.tagged_build)
        tagged_build[0]['extra'] = 'extra_value'
        self.readTaggedBuilds.return_value = tagged_build
        rv = self.exports.listTagged(self.tag_name, extra=True)
        self.assertEqual(rv, tagged_build)

    def test_list_tagged_with_prefix(self):
        self.get_tag.return_value = self.taginfo
        self.readTaggedBuilds.return_value = self.tagged_build
        rv = self.exports.listTagged(self.tag_name, prefix='test')
        self.assertEqual(rv, self.tagged_build)

    def test_list_tagged_with_prefix_empty_result(self):
        self.get_tag.return_value = self.taginfo
        self.readTaggedBuilds.return_value = self.tagged_build
        rv = self.exports.listTagged(self.tag_name, prefix='pkg')
        self.assertEqual(rv, [])
