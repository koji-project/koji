#!/usr/bin/python

"""Test argspec functions"""

import koji.tasks
import unittest

class ArgspecCase(unittest.TestCase):
    """Main test case container"""

    def test_apply_argspec(self):
        """Test the parse_NVR method"""

        # Start simple
        argspec = (['n'], None, None, None)
        self.assertRaises(koji.ParameterError, koji.tasks.apply_argspec,
            argspec, (), None )
        self.assertRaises(koji.ParameterError, koji.tasks.apply_argspec,
            argspec, (1,2), None )
        ret = koji.tasks.apply_argspec(argspec, (1,), None)
        self.assertEqual(ret, {'n':1})
        ret = koji.tasks.apply_argspec(argspec, (), {'n':1})
        self.assertEqual(ret, {'n':1})
        self.assertRaises(koji.ParameterError, koji.tasks.apply_argspec,
            argspec, (1,), {'n':1} )
        self.assertRaises(koji.ParameterError, koji.tasks.apply_argspec,
            argspec, (1,), {'m':1} )
        self.assertRaises(koji.ParameterError, koji.tasks.apply_argspec,
            argspec, (), {'m':1} )

        # using *args
        argspec = (['a', 'b'], 'args', None, None)
        self.assertRaises(koji.ParameterError, koji.tasks.apply_argspec,
            argspec, (), None )
        self.assertRaises(koji.ParameterError, koji.tasks.apply_argspec,
            argspec, (1,), None )
        ret = koji.tasks.apply_argspec(argspec, (1,2), None)
        self.assertEqual(ret, {'a':1, 'b':2, 'args': ()})
        ret = koji.tasks.apply_argspec(argspec, (1,2,3), None)
        self.assertEqual(ret, {'a':1, 'b':2, 'args': (3,)})
        self.assertRaises(koji.ParameterError, koji.tasks.apply_argspec,
            argspec, (1,2), {'a':5} )
        self.assertRaises(koji.ParameterError, koji.tasks.apply_argspec,
            argspec, (1,2), {'x':5} )
        ret = koji.tasks.apply_argspec(argspec, (1,), {'b':2})
        self.assertEqual(ret, {'a':1, 'b':2, 'args': ()})
        self.assertRaises(koji.ParameterError, koji.tasks.apply_argspec,
            argspec, (1,), {'b':2, 'c':3} )

        # using **kwargs
        argspec = (['a', 'b'], None, 'kwargs', None)
        self.assertRaises(koji.ParameterError, koji.tasks.apply_argspec,
            argspec, (), None )
        self.assertRaises(koji.ParameterError, koji.tasks.apply_argspec,
            argspec, (), {} )
        ret = koji.tasks.apply_argspec(argspec, (), {'a':1, 'b':2})
        self.assertEqual(ret, {'a':1, 'b':2, 'kwargs':{}})
        ret = koji.tasks.apply_argspec(argspec, (), {'a':1, 'b':2, 'c':3})
        self.assertEqual(ret, {'a':1, 'b':2, 'kwargs':{'c':3}})
        ret = koji.tasks.apply_argspec(argspec, (1,2), {'c':3})
        self.assertEqual(ret, {'a':1, 'b':2, 'kwargs':{'c':3}})
        ret = koji.tasks.apply_argspec(argspec, (1,), {'b': 2, 'c':3})
        self.assertEqual(ret, {'a':1, 'b':2, 'kwargs':{'c':3}})
        self.assertRaises(koji.ParameterError, koji.tasks.apply_argspec,
            argspec, (1,2), {'b':2} )

        # with defaults
        argspec = (['a', 'b'], None, None, [1,2])
        ret = koji.tasks.apply_argspec(argspec, (), {})
        self.assertEqual(ret, {'a':1, 'b':2})
        argspec = (['a', 'b'], None, None, [2])
        ret = koji.tasks.apply_argspec(argspec, (1,), {})
        self.assertEqual(ret, {'a':1, 'b':2})


if __name__ == '__main__':
    unittest.main()
