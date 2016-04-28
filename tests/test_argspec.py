#!/usr/bin/python

"""Test argspec functions"""

import koji.tasks
import unittest

class ArgspecCase(unittest.TestCase):
    """Main test case container"""

    def test_apply_argspec(self):
        """Test the parse_NVR method"""

        # Single param
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


if __name__ == '__main__':
    unittest.main()
