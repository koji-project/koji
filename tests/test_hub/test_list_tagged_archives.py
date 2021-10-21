import unittest

import koji
import kojihub
import mock

QP = kojihub.QueryProcessor


class TestListTaggedArchives(unittest.TestCase):
    def setUp(self):
        self.QueryProcessor = mock.patch('kojihub.QueryProcessor',
                                         side_effect=self.getQuery).start()
        self.queries = []
        self.get_tag = mock.patch('kojihub.get_tag').start()
        self.exports = kojihub.RootExports()
        self.context = mock.patch('kojihub.context').start()
        self.cursor = mock.MagicMock()

    def getQuery(self, *args, **kwargs):
        query = QP(*args, **kwargs)
        query.execute = mock.MagicMock()
        query.executeOne = mock.MagicMock()
        self.queries.append(query)
        return query

    def test_non_exist_tag_without_strict(self):
        self.get_tag.return_value = None
        self.exports.listTagged('non-existing-tag', strict=False)
        self.assertEqual(len(self.queries), 0)

    def test_non_exist_tag_with_strict(self):
        tag_name = 'non-existing-tag'
        error_message = "No such tagInfo: '%s'" % tag_name
        self.get_tag.side_effect = koji.GenericError(error_message)
        with self.assertRaises(koji.GenericError) as cm:
            self.exports.listTagged(tag_name)
        self.assertEqual(error_message, str(cm.exception))
