import unittest

from nose.tools import raises

import koji.policy


class TestPolicyObjects(unittest.TestCase):

    @raises(NotImplementedError)
    def test_base_test(self):
        obj = koji.policy.BaseSimpleTest('something')
        obj.run({})

    def test_true_test(self):
        obj = koji.policy.TrueTest('something')
        self.assertTrue(obj.run({}))

    def test_false_test(self):
        obj = koji.policy.FalseTest('something')
        self.assertFalse(obj.run({}))

    def test_all_test(self):
        obj = koji.policy.AllTest('something')
        self.assertTrue(obj.run({}))

    def test_none_test(self):
        obj = koji.policy.NoneTest('something')
        self.assertFalse(obj.run({}))

    def test_has_test(self):
        obj = koji.policy.HasTest('some thing')
        self.assertFalse(obj.run({}))
        self.assertFalse(obj.run({'blah': 'blah'}))
        self.assertTrue(obj.run({'thing': 'blah'}))
        self.assertRaises(koji.GenericError, koji.policy.HasTest, 'something')

    def test_bool_test(self):
        obj = koji.policy.BoolTest('some thing')
        self.assertFalse(obj.run({'thing': None}))
        self.assertFalse(obj.run({'thing': []}))
        self.assertTrue(obj.run({'thing': 'yes'}))

    def test_match_test(self):
        obj = koji.policy.MatchTest('some thing else')
        self.assertFalse(obj.run({'thing': 'elseplus'}))
        obj = koji.policy.MatchTest('some thing else*')
        self.assertTrue(obj.run({'thing': 'elseplus'}))

    def test_compare_test(self):
        obj = koji.policy.CompareTest('some thing > 2')
        self.assertFalse(obj.run({'thing': 1}))
        self.assertFalse(obj.run({'thing': 2}))
        self.assertTrue(obj.run({'thing': 3}))
        # I'm not going to test every operator..

    @raises(koji.GenericError)
    def test_invalid_compare_test(self):
        koji.policy.CompareTest('some thing LOL 2')

    def test_find_simple_tests(self):
        actual = koji.policy.findSimpleTests(koji.policy.__dict__)
        expected = {
            'all': koji.policy.AllTest,
            'bool': koji.policy.BoolTest,
            'compare': koji.policy.CompareTest,
            'false': koji.policy.FalseTest,
            'has': koji.policy.HasTest,
            'match': koji.policy.MatchTest,
            'none': koji.policy.NoneTest,
            'true': koji.policy.TrueTest,
        }
        self.assertDictEqual(expected, actual)

    def test_simple_rule_set_instantiation(self):
        tests = koji.policy.findSimpleTests(koji.policy.__dict__)
        rules = ['true :: allow']
        koji.policy.SimpleRuleSet(rules, tests)

    def test_simple_rule_set_all_actions(self):
        tests = koji.policy.findSimpleTests(koji.policy.__dict__)
        rules = ['true :: allow']
        obj = koji.policy.SimpleRuleSet(rules, tests)
        result = obj.all_actions()
        self.assertEquals(result, ['allow'])

    def test_simple_rule_set_apply(self):
        tests = koji.policy.findSimpleTests(koji.policy.__dict__)
        data = {}

        rules = ['true :: allow']
        obj = koji.policy.SimpleRuleSet(rules, tests)
        action = obj.apply(data)
        self.assertEqual(action, 'allow')

        rules = ['false :: allow']
        obj = koji.policy.SimpleRuleSet(rules, tests)
        action = obj.apply(data)
        self.assertEqual(action, None)
