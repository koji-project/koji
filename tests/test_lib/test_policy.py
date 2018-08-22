from __future__ import absolute_import
try:
    import unittest2 as unittest
except ImportError:
    import unittest

from nose.tools import raises

import koji.policy


class MyBoolTest(koji.policy.BoolTest):
    name = 'bool_check'
    field = 'bool_field'


class MyMatchTest(koji.policy.MatchTest):
    name = 'match_check'
    field = 'match_field'


class myvarTest(koji.policy.CompareTest):
    name = None
    field = 'myvar'
    allow_float = False


class TestBasicTests(unittest.TestCase):

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
        self.assertFalse(obj.run({}))
        self.assertTrue(obj.run({'thing': 'yes'}))

    def test_match_test(self):
        obj = koji.policy.MatchTest('some thing else')
        self.assertFalse(obj.run({'thing': 'elseplus'}))
        obj = koji.policy.MatchTest('some thing else*')
        self.assertTrue(obj.run({'thing': 'elseplus'}))
        self.assertFalse(obj.run({}))

    def test_target_test(self):
        obj = koji.policy.TargetTest('target valid')
        self.assertTrue(obj.run({'target': 'valid'}))
        self.assertFalse(obj.run({'target': 'else'}))
        obj = koji.policy.TargetTest('target valid else*')
        self.assertTrue(obj.run({'target': 'valid'}))
        self.assertTrue(obj.run({'target': 'elseplus'}))

    def test_compare_test(self):
        obj = koji.policy.CompareTest('compare thing > 2')
        self.assertFalse(obj.run({'thing': 1}))
        self.assertFalse(obj.run({'thing': 2}))
        self.assertTrue(obj.run({'thing': 3}))
        self.assertFalse(obj.run({}))

        obj = koji.policy.CompareTest('compare thing < 1.5')
        self.assertFalse(obj.run({'thing': 3.2}))
        self.assertTrue(obj.run({'thing': 1.0}))
        self.assertFalse(obj.run({}))

        obj = koji.policy.CompareTest('compare thing = 42')
        self.assertFalse(obj.run({'thing': 54}))
        self.assertTrue(obj.run({'thing': 42}))
        self.assertFalse(obj.run({}))

        obj = koji.policy.CompareTest('compare thing != 99')
        self.assertFalse(obj.run({'thing': 99}))
        self.assertTrue(obj.run({'thing': 100}))
        self.assertFalse(obj.run({}))

        obj = koji.policy.CompareTest('compare thing >= 2')
        self.assertFalse(obj.run({'thing': 1}))
        self.assertTrue(obj.run({'thing': 2}))
        self.assertTrue(obj.run({'thing': 3}))
        self.assertFalse(obj.run({}))

        obj = koji.policy.CompareTest('compare thing <= 5')
        self.assertFalse(obj.run({'thing': 23}))
        self.assertTrue(obj.run({'thing': 5}))
        self.assertTrue(obj.run({'thing': 0}))
        self.assertFalse(obj.run({}))

    @raises(koji.GenericError)
    def test_invalid_compare_test(self):
        koji.policy.CompareTest('some thing LOL 2')


class TestDiscovery(unittest.TestCase):

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
            'target': koji.policy.TargetTest,
            'true': koji.policy.TrueTest,
        }
        self.assertDictEqual(expected, actual)


class TestRuleHandling(unittest.TestCase):

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

    def test_custom_rules(self):
        tests = koji.policy.findSimpleTests([globals(), koji.policy.__dict__])

        rules = ['bool_check :: True', 'all :: False']
        for val in True, False:
            data = {'bool_field' : val}
            obj = koji.policy.SimpleRuleSet(rules, tests)
            action = obj.apply(data)
            self.assertEqual(action, str(val))

        rules = ['match_check foo* :: foo', 'match_check * :: bar']
        data = {'match_field' : 'foo1234'}
        obj = koji.policy.SimpleRuleSet(rules, tests)
        action = obj.apply(data)
        self.assertEqual(action, 'foo')

        data = {'match_field' : 'not foo'}
        obj = koji.policy.SimpleRuleSet(rules, tests)
        action = obj.apply(data)
        self.assertEqual(action, 'bar')

        data = {'myvar': 37}
        rules = ['myvar = 37 :: get back here']
        obj = koji.policy.SimpleRuleSet(rules, tests)
        action = obj.apply(data)
        self.assertEqual(action, 'get back here')

        rules = ['myvar = 2.718281828 :: euler']
        with self.assertRaises(ValueError):
            obj = koji.policy.SimpleRuleSet(rules, tests)

    def test_last_rule(self):
        tests = koji.policy.findSimpleTests(koji.policy.__dict__)
        data = {}

        # no match
        rules = ['none :: allow']
        obj = koji.policy.SimpleRuleSet(rules, tests)
        self.assertEquals(obj.last_rule(), None)
        action = obj.apply(data)
        self.assertEquals(obj.last_rule(), '(no match)')

        # simple rule
        rules = ['all :: allow']
        obj = koji.policy.SimpleRuleSet(rules, tests)
        action = obj.apply(data)
        self.assertEquals(obj.last_rule(), rules[0])

        # negate rule
        rules = ['none !! allow']
        obj = koji.policy.SimpleRuleSet(rules, tests)
        action = obj.apply(data)
        self.assertEquals(obj.last_rule(), rules[0])

        # nested rule
        policy = '''
all :: {
    all :: {
        all :: allow
    }
}
'''
        rules = policy.splitlines()
        obj = koji.policy.SimpleRuleSet(rules, tests)
        action = obj.apply(data)
        expected = 'all :: ... all :: ... all :: allow'
        self.assertEquals(obj.last_rule(), expected)

    def test_unclosed_brace(self):
        tests = koji.policy.findSimpleTests(koji.policy.__dict__)
        data = {}

        lines = ['true :: {']
        with self.assertRaises(koji.GenericError):
            obj = koji.policy.SimpleRuleSet(lines, tests)

    def test_unmatched_brace(self):
        tests = koji.policy.findSimpleTests(koji.policy.__dict__)
        data = {}

        lines = ['true :: }']
        with self.assertRaises(koji.GenericError):
            obj = koji.policy.SimpleRuleSet(lines, tests)

    def test_no_action(self):
        tests = koji.policy.findSimpleTests(koji.policy.__dict__)
        data = {}

        lines = ['true && true']
        with self.assertRaises(Exception):
            obj = koji.policy.SimpleRuleSet(lines, tests)

    def test_missing_handler(self):
        tests = koji.policy.findSimpleTests(koji.policy.__dict__)
        data = {}

        lines = ['NOSUCHHANDLER && true :: allow']
        with self.assertRaises(koji.GenericError):
            obj = koji.policy.SimpleRuleSet(lines, tests)

    def test_complex_policy(self):
        tests = koji.policy.findSimpleTests(koji.policy.__dict__)
        data = {}

        policy = '''
# This is a comment in the test policy

#^blank line
# commented test && true :: some result

# First some rules that should never match
false :: ERROR
none :: ERROR

true !! ERROR
all !! ERROR

false && true && true :: ERROR
none && true && true :: ERROR

has NOSUCHFIELD :: ERROR

# nesting
has DEPTH :: {
    match DEPTH 1 :: 1
    all :: {
        match DEPTH 2 :: 2
        all :: {
            match DEPTH 3 :: 3
            all :: {
                match DEPTH 4 :: 4
                all :: END
            }
        }
    }
}
'''

        lines = policy.splitlines()

        for depth in ['1', '2', '3', '4']:
            data = {'DEPTH': depth}
            obj = koji.policy.SimpleRuleSet(lines, tests)
            action = obj.apply(data)
            self.assertEqual(action, depth)

        data = {'DEPTH': '99'}
        obj = koji.policy.SimpleRuleSet(lines, tests)
        action = obj.apply(data)
        self.assertEqual(action, 'END')

        actions = set(obj.all_actions())
        self.assertEquals(actions, set(['1', '2', '3', '4', 'ERROR', 'END']))
