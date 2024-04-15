import unittest

import koji
import kojihub
import mock
import copy

QP = kojihub.QueryProcessor


class TestListTaggedArchives(unittest.TestCase):
    def setUp(self):
        self.QueryProcessor = mock.patch('kojihub.kojihub.QueryProcessor',
                                         side_effect=self.getQuery).start()
        self.queries = []
        self.get_tag = mock.patch('kojihub.kojihub.get_tag').start()
        self.exports = kojihub.RootExports()
        self.context = mock.patch('kojihub.kojihub.context').start()
        self.cursor = mock.MagicMock()
        self.readTaggedArchives = mock.patch('kojihub.kojihub.readTaggedArchives').start()
        self.tag_name = 'test-tag'
        self.taginfo = {'id': 1, 'name': 'tag'}
        self.tagged_archives = [
            [{'btype': 'maven',
              'btype_id': 2,
              'build_id': 1,
              'checksum': '75a8f47a6626fa1934b3ca5b2c51eb4d2c3bf7c88c621d5327af0a64e08797f6',
              'checksum_type': 2,
              'filename': 'test-1.4.7.pom',
              'id': 1,
              'type_id': 3}],
            [{'build_id': 1,
              'epoch': 7,
              'id': 1,
              'name': 'kojitest-rpm',
              'nvr': 'kojitest-rpm-1.1-11',
              'owner_id': 1,
              'owner_name': 'kojiadmin',
              'package_id': 1,
              'package_name': 'kojitest-rpm',
              'release': '11',
              'state': 1,
              'tag_id': self.taginfo['id'],
              'tag_name': self.tag_name,
              'task_id': 3,
              'version': '1.1',
              'volume_id': 0,
              'volume_name': 'DEFAULT'}]
        ]

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
        self.exports.listTaggedArchives(self.tag_name, strict=False)
        self.assertEqual(len(self.queries), 0)

    def test_non_exist_tag_with_strict(self):
        error_message = "No such tagInfo: '%s'" % self.tag_name
        self.get_tag.side_effect = koji.GenericError(error_message)
        with self.assertRaises(koji.GenericError) as cm:
            self.exports.listTaggedArchives(self.tag_name)
        self.assertEqual(error_message, str(cm.exception))

    def test_list_tagged_archives_default(self):
        self.get_tag.return_value = self.taginfo
        tagged_archives = copy.deepcopy(self.tagged_archives)
        tagged_archives[0][0]['extra'] = 'extra_value'
        self.readTaggedArchives.return_value = tagged_archives
        rv = self.exports.listTaggedArchives(self.tag_name)
        self.assertEqual(rv, tagged_archives)

    def test_list_tagged_archives_without_extra(self):
        self.get_tag.return_value = self.taginfo
        self.readTaggedArchives.return_value = self.tagged_archives
        rv = self.exports.listTaggedArchives(self.tag_name, extra=False)
        self.assertEqual(rv, self.tagged_archives)
