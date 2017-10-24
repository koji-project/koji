#!/usr/bin/python

"""Test argspec functions"""

import inspect
import os.path
import sys
import unittest

import koji.tasks


# jump through hoops to import kojid
KOJID_FILENAME = os.path.dirname(__file__) + "/../builder/kojid"
if sys.version_info[0] >= 3:
    import importlib.util
    spec = importlib.util.spec_from_file_location("kojid", KOJID_FILENAME)
    kojid = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(kojid)
else:
    import imp
    kojid = imp.load_source('koji_kojid', KOJID_FILENAME)


class ParseTaskParamsCase(unittest.TestCase):
    """Main test case container"""

    def test_parse_task_params(self):
        """Test parse_task_params"""

        # simple case
        ret = koji.tasks.parse_task_params('sleep', [4])
        self.assertEqual(ret, {'n':4})

        # bad args
        with self.assertRaises(koji.ParameterError):
            koji.tasks.parse_task_params('sleep', [4, 5])

        # bad method
        with self.assertRaises(TypeError):
            koji.tasks.parse_task_params('MISSINGMETHOD', [1,2,3])

        # new style
        params = {'__method__': 'hello', 'n': 1}
        ret = koji.tasks.parse_task_params('hello', [params])
        del params['__method__']
        self.assertEqual(ret, params)
        self.assertIsNot(ret, params)
        # ^data should be copied


    def test_legacy_data(self):
        for method in koji.tasks.LEGACY_SIGNATURES:
            for mod in kojid, koji.tasks:
                h_class = getattr(mod, method, None)
                if h_class:
                    break
            else:
                continue

            spec = inspect.getargspec(h_class.handler)
            # unbound method, so strip "self"
            spec.args.pop(0)

            # for the methods we have, at least one of the signatures should
            # match
            self.assertIn(argspec, koji.tasks.LEGACY_SIGNATURES[method])


if __name__ == '__main__':
    unittest.main()
