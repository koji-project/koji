import mock
import unittest

import koji
import kojihub


class TestUpsertProcessor(unittest.TestCase):
    def setUp(self):
        self.context_db = mock.patch('kojihub.db.context').start()

    def tearDown(self):
        mock.patch.stopall()

    def test_required_args(self):
        with self.assertRaises(ValueError) as e:
            proc = kojihub.UpsertProcessor('sometable')
            self.assertEqual(e.msg, 'either keys or skip_dup must be set')

    def test_skip_dup(self):
        proc = kojihub.UpsertProcessor('sometable', data={'foo': 'bar'}, skip_dup=True)
        actual = str(proc)
        expected = 'INSERT INTO sometable (foo) VALUES (%(foo)s) ON CONFLICT DO NOTHING'
        self.assertEqual(actual, expected)

    def test_key(self):
        proc = kojihub.UpsertProcessor('sometable', data={'id': 1, 'foo': 'bar'}, keys=['id'])
        actual = str(proc)
        expected = 'INSERT INTO sometable (foo, id) VALUES (%(foo)s, %(id)s) ON CONFLICT (id) DO UPDATE SET foo = %(foo)s'
        self.assertEqual(actual, expected)

    def test_keys(self):
        proc = kojihub.UpsertProcessor('sometable', data={'id': 1, 'package': 'koji', 'foo': 'bar'}, keys=['id', 'package'])
        actual = str(proc)
        expected = 'INSERT INTO sometable (foo, id, package) VALUES (%(foo)s, %(id)s, %(package)s) ' \
                   'ON CONFLICT (id,package) DO UPDATE SET foo = %(foo)s'
        self.assertEqual(actual, expected)

