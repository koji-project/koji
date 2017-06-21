import copy
import mock
import unittest

import koji
import koji.plugin


class TestCallbackDecorators(unittest.TestCase):

    def test_callback_decorator(self):
        def myfunc(a, b, c=None):
            return [a,b,c]
        callbacks = ('preImport', 'postImport')
        newfunc = koji.plugin.callback(*callbacks)(myfunc)
        self.assertEqual(newfunc.callbacks, callbacks)
        self.assertEqual(newfunc(1, 2), [1, 2, None])
        self.assertEqual(newfunc(1, 2, 3), [1, 2, 3])

    def test_ignore_error_decorator(self):
        def myfunc(a, b, c=None):
            return [a,b,c]
        newfunc = koji.plugin.ignore_error(myfunc)
        self.assertEqual(newfunc.failure_is_an_option, True)
        self.assertEqual(newfunc(1, 2), [1, 2, None])
        self.assertEqual(newfunc(1, 2, 3), [1, 2, 3])

    def test_export_decorator(self):
        def myfunc(a, b, c=None):
            return [a,b,c]
        newfunc = koji.plugin.export(myfunc)
        self.assertEqual(newfunc.exported, True)
        self.assertEqual(newfunc(1, 2), [1, 2, None])
        self.assertEqual(newfunc(1, 2, 3), [1, 2, 3])

    def test_export_cli_decorator(self):
        def myfunc(a, b, c=None):
            return [a,b,c]
        newfunc = koji.plugin.export_cli(myfunc)
        self.assertEqual(newfunc.exported_cli, True)
        self.assertEqual(newfunc(1, 2), [1, 2, None])
        self.assertEqual(newfunc(1, 2, 3), [1, 2, 3])

    def test_export_as_decorator(self):
        def myfunc(a, b, c=None):
            return [a,b,c]
        alias = "ALIAS"
        newfunc = koji.plugin.export_as(alias)(myfunc)
        self.assertEqual(newfunc.exported, True)
        self.assertEqual(newfunc.export_alias, alias)
        self.assertEqual(newfunc(1, 2), [1, 2, None])
        self.assertEqual(newfunc(1, 2, 3), [1, 2, 3])

    def test_export_in_decorator_with_alias(self):
        def myfunc(a, b, c=None):
            return [a,b,c]
        newfunc = koji.plugin.export_in('MODULE', 'ALIAS')(myfunc)
        self.assertEqual(newfunc.exported, True)
        self.assertEqual(newfunc.export_alias, 'MODULE.ALIAS')
        self.assertEqual(newfunc.export_module, 'MODULE')
        self.assertEqual(newfunc(1, 2), [1, 2, None])
        self.assertEqual(newfunc(1, 2, 3), [1, 2, 3])

    def test_export_in_decorator_no_alias(self):
        def myfunc(a, b, c=None):
            return [a,b,c]
        newfunc = koji.plugin.export_in('MODULE')(myfunc)
        self.assertEqual(newfunc.exported, True)
        self.assertEqual(newfunc.export_alias, 'MODULE.myfunc')
        self.assertEqual(newfunc.export_module, 'MODULE')
        self.assertEqual(newfunc(1, 2), [1, 2, None])
        self.assertEqual(newfunc(1, 2, 3), [1, 2, 3])


class TestError(Exception):
    """Raised by a test callback defined below"""
    pass


class TestCallbacks(unittest.TestCase):

    def setUp(self):
        self.orig_callbacks = koji.plugin.callbacks
        koji.plugin.callbacks = copy.deepcopy(koji.plugin.callbacks)
        self.callbacks = []

    def tearDown(self):
        koji.plugin.callbacks = self.orig_callbacks

    def callback(self, cbtype, *args, **kwargs):
        self.callbacks.append([cbtype, args, kwargs])

    def error_callback(self, cbtype, *args, **kwargs):
        raise TestError

    @koji.plugin.ignore_error
    def safe_error_callback(self, cbtype, *args, **kwargs):
        self.callbacks.append([cbtype, args, kwargs])
        raise TestError

    def test_simple_callback(self):
        args = ('hello',)
        kwargs = {'world': 1}
        cbtype = 'preTag'
        koji.plugin.register_callback(cbtype, self.callback)
        koji.plugin.run_callbacks(cbtype, *args, **kwargs)
        self.assertEqual(len(self.callbacks), 1)
        self.assertEqual(self.callbacks[0], [cbtype, args, kwargs])

    def test_error_callback(self):
        args = ('hello',)
        kwargs = {'world': 1}
        cbtype = 'preTag'
        koji.plugin.register_callback(cbtype, self.error_callback)
        with self.assertRaises(koji.CallbackError):
            koji.plugin.run_callbacks(cbtype, *args, **kwargs)

    @mock.patch('logging.getLogger')
    def test_safe_error_callback(self, getLogger):
        args = ('hello',)
        kwargs = {'world': 1}
        cbtype = 'preTag'
        koji.plugin.register_callback(cbtype, self.safe_error_callback)
        koji.plugin.run_callbacks(cbtype, *args, **kwargs)
        self.assertEqual(len(self.callbacks), 1)
        self.assertEqual(self.callbacks[0], [cbtype, args, kwargs])
        getLogger.assert_called_once()
        getLogger.return_value.warn.assert_called_once()

    def test_bad_callback(self):
        args = ('hello',)
        kwargs = {'world': 1}
        with self.assertRaises(koji.PluginError):
            koji.plugin.register_callback('badtype', self.callback)
        with self.assertRaises(koji.PluginError):
            koji.plugin.register_callback('preImport', "not a function")
        self.assertEqual(koji.plugin.callbacks, self.orig_callbacks)
        with self.assertRaises(koji.PluginError):
            koji.plugin.run_callbacks('badtype', *args, **kwargs)

