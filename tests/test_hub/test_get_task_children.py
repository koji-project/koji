import mock

import koji
import kojihub
from .utils import DBQueryTestCase

QP = kojihub.QueryProcessor


class TestGetTaskChildren(DBQueryTestCase):
    def setUp(self):
        super(TestGetTaskChildren, self).setUp()
        self.exports = kojihub.RootExports()

    def tearDown(self):
        mock.patch.stopall()

    def test_get_task_children_non_existing(self):
        self.qp_execute_return_value = []

        r = self.exports.getTaskChildren(1000)

        self.assertEqual(r, [])

    def test_get_task_children_non_existing_strict(self):
        # get task info
        self.qp_execute_one_side_effect = koji.GenericError

        with self.assertRaises(koji.GenericError):
            self.exports.getTaskChildren(1000, strict=True)

    def test_get_task_children(self):
        children = [{'id': 1}]
        self.qp_execute_return_value = children

        r = self.exports.getTaskChildren(1000)

        self.assertEqual(r, children)
