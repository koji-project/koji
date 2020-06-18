import mock
import unittest

import koji
import kojihub

QP = kojihub.QueryProcessor

class TestGetTaskChildren(unittest.TestCase):
    def setUp(self):
        self.exports = kojihub.RootExports()
        self.QueryProcessor = mock.patch('kojihub.QueryProcessor',
                side_effect=self.getQuery).start()
        self.queries = []

    def getQuery(self, *args, **kwargs):
        query = QP(*args, **kwargs)
        query.execute = mock.MagicMock()
        query.executeOne = mock.MagicMock()
        query.singleValue = mock.MagicMock()
        self.queries.append(query)
        return query

    def tearDown(self):
        mock.patch.stopall()

    def test_get_task_children_non_existing(self):
        q = self.getQuery()
        q.execute.return_value = []
        self.QueryProcessor.side_effect = [q]

        r = self.exports.getTaskChildren("bogus_item")

        self.assertEqual(r, [])

    def test_get_task_children_non_existing_strict(self):
        # get task info
        q = self.getQuery()
        q.executeOne.side_effect = koji.GenericError
        self.QueryProcessor.side_effect = [q]

        with self.assertRaises(koji.GenericError):
            self.exports.getTaskChildren("bogus_item", strict=True)

    def test_get_task_children(self):
        children = [{'id': 1}]
        q = self.getQuery()
        q.execute.return_value = children
        self.QueryProcessor.side_effect = [q]

        r = self.exports.getTaskChildren("bogus_item")

        self.assertEqual(r, children)
