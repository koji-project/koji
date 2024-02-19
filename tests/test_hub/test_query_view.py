import mock
import unittest

import koji
import kojihub.db
import kojihub.scheduler


class TestQueryView(unittest.TestCase):
    def setUp(self):
        # using a convenient view from scheduler
        self.viewclass = kojihub.scheduler.TaskRefusalsQuery

    def tearDown(self):
        mock.patch.stopall()

    def test_no_joins_needed(self):
        view = self.viewclass(fields=['id', 'task_id'])
        self.assertEqual(set(view.query.aliases), set(['id', 'task_id']))
        self.assertEqual(view.query.joins, [])
        self.assertEqual(view.query.clauses, [])

    def test_one_join_needed(self):
        # the additional fields require joining task table
        view = self.viewclass(fields=['id', 'task_id', 'method', 'state'])
        self.assertEqual(set(view.query.aliases), set(['id', 'task_id', 'method', 'state']))
        self.assertEqual(view.query.joins, ['task ON scheduler_task_refusals.task_id = task.id'])
        self.assertEqual(view.query.clauses, [])

    def test_implicit_equal(self):
        view = self.viewclass(fields=['id', 'task_id'], clauses=[['id', 23]])
        self.assertEqual(view.query.values, {'v_id_0': 23})
        self.assertEqual(view.query.clauses, ['scheduler_task_refusals.id = %(v_id_0)s'])

    def test_implicit_in(self):
        view = self.viewclass(fields=['id', 'task_id'], clauses=[['id', [42, 137]]])
        self.assertEqual(view.query.values, {'v_id_0': [42, 137]})
        self.assertEqual(view.query.clauses, ['scheduler_task_refusals.id IN %(v_id_0)s'])

    def test_explicit_op(self):
        view = self.viewclass(fields=['id', 'task_id'], clauses=[['id', '<', 5]])
        self.assertEqual(view.query.values, {'v_id_0': 5})
        self.assertEqual(view.query.clauses, ['scheduler_task_refusals.id < %(v_id_0)s'])

    def test_invalid_op(self):
        with self.assertRaises(koji.ParameterError) as e:
            view = self.viewclass(fields=['id', 'task_id'], clauses=[['id', '==', 5]])
            view.get_query()

    def test_invalid_clause(self):
        with self.assertRaises(koji.ParameterError) as e:
            view = self.viewclass(fields=['id', 'task_id'], clauses=[['id', 'NOT', 'EQUAL', 5]])
            view.get_query()

    def test_invalid_field(self):
        with self.assertRaises(koji.ParameterError) as e:
            view = self.viewclass(fields=['id', 'task_id', 'nosuchfield'])
            view.get_query()

    def test_default_fields(self):
        view = self.viewclass()
        self.assertEqual(set(view.query.aliases), set(self.viewclass.default_fields))

    def test_all_fields(self):
        view = self.viewclass(fields='*')
        self.assertEqual(set(view.query.aliases), set(self.viewclass.fieldmap.keys()))
