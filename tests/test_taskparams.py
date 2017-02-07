#!/usr/bin/python

"""Test argspec functions"""

import koji.tasks
import unittest


class ParseTaskParamsCase(unittest.TestCase):
    """Main test case container"""

    def test_parse_task_params(self):
        """Test parse_task_params"""

        # Start simple
        ret = koji.tasks.parse_task_params('sleep', [4])
        self.assertEqual(ret, {'n':4})
        with self.assertRaises(koji.ParameterError):
            koji.tasks.parse_task_params('sleep', [4, 5])


if __name__ == '__main__':
    unittest.main()
