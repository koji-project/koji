# Copyright (c) 2008-2014 Red Hat, Inc.
#
#    Koji is free software; you can redistribute it and/or
#    modify it under the terms of the GNU Lesser General Public
#    License as published by the Free Software Foundation;
#    version 2.1 of the License.
#
#    This software is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
#    Lesser General Public License for more details.
#
#    You should have received a copy of the GNU Lesser General Public
#    License along with this software; if not, write to the Free Software
#    Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301  USA
#
# Authors:
#       Mike McLean <mikem@redhat.com>

from __future__ import absolute_import

import fnmatch
import logging

import six

import koji
from koji.util import to_list


class BaseSimpleTest(object):
    """Abstract base class for simple tests"""

    # Provide the name of the test
    name = None

    def __init__(self, str):
        """Read the test parameters from string"""
        self.str = str

    def run(self, data):
        """Run the test against data provided"""
        raise NotImplementedError

    def __str__(self):
        return self.str


# The following tests are generic enough that we can place them here

class TrueTest(BaseSimpleTest):
    name = 'true'

    def run(self, data):
        return True


class FalseTest(BaseSimpleTest):
    name = 'false'

    def run(self, data):
        return False


class AllTest(TrueTest):
    name = 'all'
    # alias for true


class NoneTest(FalseTest):
    name = 'none'
    # alias for false


class HasTest(BaseSimpleTest):
    """Test if policy data contains a field"""

    name = "has"

    def __init__(self, str):
        super(HasTest, self).__init__(str)
        try:
            self.field = str.split()[1]
        except IndexError:
            raise koji.GenericError("Invalid or missing field in policy test")

    def run(self, data):
        return self.field in data


class BoolTest(BaseSimpleTest):
    """Test a field in the data as a boolean value

    This test can be used as-is, or it can be subclassed to
    test a specific field

    Syntax:
        name [field]
    """
    name = 'bool'
    field = None

    def run(self, data):
        args = self.str.split()[1:]
        if self.field is None:
            field = args[0]
        else:
            # expected when we are subclassed
            field = self.field
        if field not in data:
            return False
        return bool(data[field])


class MatchTest(BaseSimpleTest):
    """Matches a field in the data against glob patterns

    True if any of the expressions match, else False
    This test can be used as-is, or it can be subclassed to
    test a specific field

    Syntax:
        name [field] pattern1 [pattern2 ...]
    """
    name = 'match'
    field = None

    def run(self, data):
        args = self.str.split()[1:]
        if self.field is None:
            field = args[0]
            args = args[1:]
        else:
            # expected when we are subclassed
            field = self.field
        if field not in data:
            return False
        for pattern in args:
            if fnmatch.fnmatch(data[field], pattern):
                return True
        return False


class TargetTest(MatchTest):
    """Matches target in the data against glob patterns

    True if any of the expressions match, else False

    Syntax:
        target pattern1 [pattern2 ...]
    """
    name = 'target'
    field = 'target'


class CompareTest(BaseSimpleTest):
    """Simple numeric field comparison

    Supports basic numeric comparisons. The right operand must be a valid number
    This test can be used as-is, or it can be subclassed to
    test a specific field

    Syntax:
        name [field] OP number
    """

    name = 'compare'
    field = None
    allow_float = True

    operators = {
        '<': lambda a, b: a < b,
        '>': lambda a, b: a > b,
        '<=': lambda a, b: a <= b,
        '>=': lambda a, b: a >= b,
        '=': lambda a, b: a == b,
        '!=': lambda a, b: a != b,
    }

    def __init__(self, str):
        """Read the test parameters from string"""
        super(CompareTest, self).__init__(str)
        if self.field is None:
            # field OP number
            self.field, cmp, value = str.split(None, 3)[1:]
        else:
            # OP number
            cmp, value = str.split(None, 2)[1:]
        self.func = self.operators.get(cmp, None)
        if self.func is None:
            raise koji.GenericError("Invalid comparison in test.")
        try:
            self.value = int(value)
        except ValueError:
            if not self.allow_float:
                raise
            self.value = float(value)

    def run(self, data):
        if self.field not in data:
            return False
        return self.func(data[self.field], self.value)


class SimpleRuleSet(object):

    def __init__(self, rules, tests):
        self.tests = tests
        self.rules = self.parse_rules(rules)
        self.lastrule = None
        self.lastaction = None
        self.logger = logging.getLogger('koji.policy')

    def parse_rules(self, lines):
        """Parse rules into a ruleset data structure

        At the top level, the structure is a set of rules
            [rule1, rule2, ...]
        Each rule is a pair
            [tests, negate, action ]
        Tests is a list of test handlers:
            [handler1, handler2, ...]
        Action can either be a string or a chained ruleset
            "action"
            or
            [subrule1, subrule2, ...]
        Putting it all together, you get something like this:
            [[[test1, test2], negate, "action"],
             [[test], negate,
              [[[test1, test2], negate, "action"],
               [[test1, test2, test3], negate
                [[[test1, test2], negate, "action"]]]]]]
        """
        cursor = []
        self.ruleset = cursor
        stack = []
        for line in lines:
            rule = self.parse_line(line)
            if rule is None:
                # blank/etc
                continue
            tests, negate, action = rule
            if action == '{':
                # nested rules
                child = []
                cursor.append([tests, negate, child])
                stack.append(cursor)
                cursor = child
            elif action == '}':
                if not stack:
                    raise koji.GenericError("nesting error in rule set")
                cursor = stack.pop()
            else:
                cursor.append(rule)
        if stack:
            # unclosed {
            raise koji.GenericError("nesting error in rule set")

    def parse_line(self, line):
        """Parse line as a rule

        Expected format is:
        test [params] [&& test [params] ...] :: action-if-true
        test [params] [&& test [params] ...] !! action-if-false


        (syntax is !! instead of ||, because otherwise folks might think
        they can mix && and ||, which is /not/ supported)

        For complex rules:
        test [params [&& ...]] :: {
            test [params [&& ...]] :: action
            test [params [&& ...]] :: {
                ...
                }
        }

        Each closing brace must be on a line by itself
        """
        line = line.split('#', 1)[0].strip()
        if not line:
            # blank or all comment
            return None
        if line == '}':
            return None, False, '}'
            # ?? allow }} ??
        negate = False
        pos = line.rfind('::')
        if pos == -1:
            pos = line.rfind('!!')
            if pos == -1:
                raise Exception("bad policy line: %s" % line)
            negate = True
        tests = line[:pos]
        action = line[pos + 2:]
        tests = [self.get_test_handler(x) for x in tests.split('&&')]
        action = action.strip()
        # just return action = { for nested rules
        return tests, negate, action

    def get_test_handler(self, str):
        name = str.split(None, 1)[0]
        try:
            return self.tests[name](str)
        except KeyError:
            raise koji.GenericError("missing test handler: %s" % name)

    def all_actions(self):
        """report a list of all actions in the ruleset

        (only the first word of the action is considered)
        """
        def _recurse(rules, index):
            for tests, negate, action in rules:
                if isinstance(action, list):
                    _recurse(action, index)
                else:
                    name = action.split(None, 1)[0]
                    index[name] = 1
        index = {}
        _recurse(self.ruleset, index)
        return to_list(index.keys())

    def _apply(self, rules, data, top=False):
        for tests, negate, action in rules:
            if top:
                self.lastrule = []
            value = False
            for test in tests:
                check = test.run(data)
                self.logger.debug("%s -> %s", test, check)
                if not check:
                    break
            else:
                # all tests in current rule passed
                value = True
            if negate:
                value = not value
            if value:
                self.lastrule.append([tests, negate])
                if isinstance(action, list):
                    self.logger.debug("matched: entering subrule")
                    # action is a list of subrules
                    ret = self._apply(action, data)
                    if ret is not None:
                        return ret
                    # if ret is None, then none of the subrules matched,
                    # so we keep going
                else:
                    self.logger.debug("matched: action=%s", action)
                    return action
        return None

    def apply(self, data):
        self.logger.debug("policy start")
        self.lastrule = []
        self.lastaction = self._apply(self.ruleset, data, top=True)
        self.logger.debug("policy done")
        return self.lastaction

    def last_rule(self):
        if self.lastrule is None:
            return None
        ret = []
        for (tests, negate) in self.lastrule:
            line = '&&'.join([str(t) for t in tests])
            if negate:
                line += '!! '
            else:
                line += ':: '
            ret.append(line)
        ret = '... '.join(ret)
        if self.lastaction is None:
            ret += "(no match)"
        else:
            ret += self.lastaction
        return ret


def findSimpleTests(namespace):
    """Search namespace for subclasses of BaseSimpleTest

    This is a convenience function for initializing a SimpleRuleSet instance
    namespace can be a dict (e.g. globals()), or a list of dicts
    returns a dictionary of the found subclasses, indexed by name
    """
    if not isinstance(namespace, (list, tuple)):
        namespace = (namespace,)
    ret = {}
    for ns in namespace:
        for key, value in six.iteritems(ns):
            if value is BaseSimpleTest:
                # skip this abstract base class if we encounter it
                # this module contains generic tests, so it is valid to include it
                # in the namespace list
                continue
            if isinstance(value, type(BaseSimpleTest)) and issubclass(value, BaseSimpleTest):
                name = getattr(value, 'name', None)
                if not name:
                    # use the class name
                    name = key
                    # but trim 'Test' from the end
                    if name.endswith('Test') and len(name) > 4:
                        name = name[:-4]
                ret.setdefault(name, value)
                # ...so first test wins in case of name overlap
    return ret
