from __future__ import absolute_import
try:
    import unittest2 as unittest
except ImportError:
    import unittest

import koji.util

class TestApplyArgspec(unittest.TestCase):

    def test_apply_argspec(self):
        # Start simple: def func(n)
        argspec = (['n'], None, None, None)
        badargs = [
                # [args, kwargs]
                [(), None],
                [(1, 2), None],
                [(1,), {'n': 1}],
                [(1,), {'m': 1}],
                [(), {'m': 1}],
            ]
        for args, kwargs in badargs:
            with self.assertRaises(koji.ParameterError):
                koji.util.apply_argspec(argspec, args, kwargs)

        ret = koji.util.apply_argspec(argspec, (1,), None)
        self.assertEqual(ret, {'n': 1})

        ret = koji.util.apply_argspec(argspec, (), {'n': 1})
        self.assertEqual(ret, {'n': 1})

        # Using *args; def func(a, b, *args)
        argspec = (['a', 'b'], 'args', None, None)
        badargs = [
                [(), None],
                [(1,), None],
                [(1,2), {'a': 5}],
                [(1,2), {'x': 5}],
                [(1,), {'b': 2, 'c': 3}],
            ]
        for args, kwargs in badargs:
            with self.assertRaises(koji.ParameterError):
                koji.util.apply_argspec(argspec, args, kwargs)

        ret = koji.util.apply_argspec(argspec, (1,2), None)
        self.assertEqual(ret, {'a':1, 'b':2, 'args': ()})

        ret = koji.util.apply_argspec(argspec, (1,2,3), None)
        self.assertEqual(ret, {'a':1, 'b':2, 'args': (3,)})

        ret = koji.util.apply_argspec(argspec, (1,), {'b':2})
        self.assertEqual(ret, {'a':1, 'b':2, 'args': ()})

        # Using **kwargs: def func(a, b, **kwargs)
        argspec = (['a', 'b'], None, 'kwargs', None)
        badargs = [
                [(), None],
                [(), {}],
                [(1, 2), {'a': 2}],
                [(1, 2), {'b': 2}],
                [(1,), {'a': 1, 'b': 2}],
            ]
        for args, kwargs in badargs:
            with self.assertRaises(koji.ParameterError):
                koji.util.apply_argspec(argspec, (), None)

        ret = koji.util.apply_argspec(argspec, (), {'a':1, 'b':2})
        self.assertEqual(ret, {'a':1, 'b':2, 'kwargs':{}})

        ret = koji.util.apply_argspec(argspec, (), {'a':1, 'b':2, 'c':3})
        self.assertEqual(ret, {'a':1, 'b':2, 'kwargs':{'c':3}})

        ret = koji.util.apply_argspec(argspec, (1,2), {'c':3})
        self.assertEqual(ret, {'a':1, 'b':2, 'kwargs':{'c':3}})

        ret = koji.util.apply_argspec(argspec, (1,), {'b': 2, 'c':3})
        self.assertEqual(ret, {'a':1, 'b':2, 'kwargs':{'c':3}})

        # With defaults: def func(a=1, b=2)
        argspec = (['a', 'b'], None, None, [1,2])
        badargs = [
                [(1,2,3), None],
                [(1,2), {'a': 5}],
                [(1,2), {'b': 5}],
                [(1,2), {'x': 5}],
                [(), {'x': 5}],
                [(1,), {'b': 2, 'c': 3}],
            ]
        for args, kwargs in badargs:
            with self.assertRaises(koji.ParameterError):
                koji.util.apply_argspec(argspec, args, kwargs)

        ret = koji.util.apply_argspec(argspec, (), {})
        self.assertEqual(ret, {'a':1, 'b':2})

        # Partial defaults: def func(a, b=2)
        argspec = (['a', 'b'], None, None, [2])
        badargs = [
                [(1,2,3), None],
                [(1,2), {'a': 5}],
                [(1,2), {'b': 5}],
                [(1,2), {'x': 5}],
                [(), {'x': 5}],
                [(1,), {'b': 2, 'c': 3}],
            ]
        for args, kwargs in badargs:
            with self.assertRaises(koji.ParameterError):
                koji.util.apply_argspec(argspec, args, kwargs)

        ret = koji.util.apply_argspec(argspec, (1,), {})
        self.assertEqual(ret, {'a':1, 'b':2})
