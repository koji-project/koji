from __future__ import absolute_import
import inspect
import mock
import sys
import unittest
import koji
import koji.tasks

from .loadkojid import kojid


class TestParseTaskParams(unittest.TestCase):
    """Main test case container"""

    def test_parse_task_params(self):
        """Test parse_task_params"""

        # simple case
        ret = koji.tasks.parse_task_params('sleep', [4])
        self.assertEqual(ret, {'n': 4})

        # bad args
        with self.assertRaises(koji.ParameterError):
            koji.tasks.parse_task_params('sleep', [4, 5])

        # bad method
        with self.assertRaises(TypeError):
            koji.tasks.parse_task_params('MISSINGMETHOD', [1, 2, 3])

        # new style
        params = {'__method__': 'hello', 'n': 1}
        ret = koji.tasks.parse_task_params('hello', [params])
        del params['__method__']
        self.assertEqual(ret, params)
        self.assertIsNot(ret, params)
        # ^data should be copied

    def test_legacy_data(self):
        # set up a fake TaskManager to get our handlers
        options = mock.MagicMock()
        session = mock.MagicMock()
        tm = koji.daemon.TaskManager(options, session)
        tm.findHandlers(vars(kojid))
        tm.findHandlers(vars(koji.tasks))

        missing = []
        for method in koji.tasks.LEGACY_SIGNATURES:
            h_class = tm.handlers.get(method)
            if not h_class:
                missing.append(method)
                continue
            if sys.version_info > (3,):
                spec = inspect.getfullargspec(h_class.handler)
                # unbound method, so strip "self"
                spec.args.pop(0)
                spec = spec[:-3]
            else:
                spec = inspect.getargspec(h_class.handler)
                # unbound method, so strip "self"
                spec.args.pop(0)

            # for the methods we have, at least one of the signatures should
            # match
            self.assertIn(list(spec), koji.tasks.LEGACY_SIGNATURES[method])

        external = ['runroot', 'saveFailedTree', 'vmExec', 'winbuild']
        missing = [m for m in missing if m not in external]
        if missing:
            raise Exception('Unable to test legacy signatures. Missing: '
                            '%r' % missing)
