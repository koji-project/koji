from __future__ import absolute_import
import copy
import datetime
import mock
from six.moves import range
try:
    import unittest2 as unittest
except ImportError:
    import unittest

import koji
import koji.util
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

    @koji.plugin.convert_datetime
    def datetime_callback(self, cbtype, *args, **kwargs):
        self.callbacks.append([cbtype, args, kwargs])

    @koji.plugin.convert_datetime
    def datetime_callback2(self, cbtype, *args, **kwargs):
        self.callbacks.append([cbtype, args, kwargs])

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
        getLogger.return_value.warning.assert_called_once()

    def test_datetime_callback(self):
        dt1 = datetime.datetime.now()
        dt2 = datetime.datetime(2001,1,1)
        args = (dt1,"2",["three"], {4: dt2},)
        kwargs = {'foo': [dt1, dt2]}
        cbtype = 'preTag'
        koji.plugin.register_callback(cbtype, self.datetime_callback)
        koji.plugin.run_callbacks(cbtype, *args, **kwargs)
        args2 = koji.util.encode_datetime_recurse(args)
        kwargs2 = koji.util.encode_datetime_recurse(kwargs)
        self.assertEqual(len(self.callbacks), 1)
        self.assertEqual(self.callbacks[0], [cbtype, args2, kwargs2])

    def test_multiple_datetime_callback(self):
        dt1 = datetime.datetime.now()
        dt2 = datetime.datetime(2001,1,1)
        args = (dt1,"2",["three"], {4: dt2},)
        kwargs = {'foo': [dt1, dt2]}
        cbtype = 'preTag'
        koji.plugin.register_callback(cbtype, self.datetime_callback)
        koji.plugin.register_callback(cbtype, self.datetime_callback2)
        koji.plugin.run_callbacks(cbtype, *args, **kwargs)
        args2 = koji.util.encode_datetime_recurse(args)
        kwargs2 = koji.util.encode_datetime_recurse(kwargs)
        self.assertEqual(len(self.callbacks), 2)
        self.assertEqual(self.callbacks[0], [cbtype, args2, kwargs2])
        self.assertEqual(self.callbacks[1], [cbtype, args2, kwargs2])
        # verify that caching worked
        # unfortunately, args and kwargs get unpacked and repacked, so we have
        # to dig down
        cb_args1 = self.callbacks[0][1]
        cb_args2 = self.callbacks[1][1]
        for i in range(len(cb_args1)):
            if cb_args1[i] is not cb_args2[i]:
                raise Exception("converted args not cached")
        cb_kwargs1 = self.callbacks[0][2]
        cb_kwargs2 = self.callbacks[1][2]
        for k in cb_kwargs1:
            if cb_kwargs1[k] is not cb_kwargs2[k]:
                raise Exception("converted kwargs not cached")

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


class TestPluginTracker(unittest.TestCase):

    def setUp(self):
        self.find_module = mock.patch('imp.find_module').start()
        self.modfile = mock.MagicMock()
        self.modpath = mock.MagicMock()
        self.moddesc = mock.MagicMock()
        self.find_module.return_value = (self.modfile, self.modpath,
                self.moddesc)
        self.load_module = mock.patch('imp.load_module').start()

    def tearDown(self):
        mock.patch.stopall()

    def test_tracked_plugin(self):
        tracker = koji.plugin.PluginTracker(path='/MODPATH')
        self.load_module.return_value = 'MODULE!'
        tracker.load('hello')
        self.assertEqual(tracker.get('hello'), 'MODULE!')
        self.find_module.assert_called_once_with('hello', ['/MODPATH'])

    def test_plugin_reload(self):
        tracker = koji.plugin.PluginTracker(path='/MODPATH')
        self.load_module.return_value = 'MODULE!'
        tracker.load('hello')
        self.assertEqual(tracker.get('hello'), 'MODULE!')

        # should not reload if we don't ask
        self.load_module.return_value = 'DUPLICATE!'
        tracker.load('hello')
        self.assertEqual(tracker.get('hello'), 'MODULE!')

        # should reload if we do ask
        tracker.load('hello', reload=True)
        self.assertEqual(tracker.get('hello'), 'DUPLICATE!')

        # should throw exception if not reloading and duplicate in sys.modules
        module_mock = mock.MagicMock()
        with mock.patch.dict('sys.modules', _koji_plugin__dup_module=module_mock):
            with self.assertRaises(koji.PluginError):
                tracker.load('dup_module')

    def test_no_plugin_path(self):
        tracker = koji.plugin.PluginTracker()
        with self.assertRaises(koji.PluginError):
            tracker.load('hello')
        self.load_module.assert_not_called()
        self.assertEqual(tracker.get('hello'), None)

    def test_plugin_path_list(self):
        tracker = koji.plugin.PluginTracker(path='/MODPATH')
        self.load_module.return_value = 'MODULE!'
        tracker.load('hello', path=['/PATH1', '/PATH2'])
        self.assertEqual(tracker.get('hello'), 'MODULE!')
        self.find_module.assert_called_once_with('hello', ['/PATH1', '/PATH2'])

        self.find_module.reset_mock()
        tracker.load('hey', path='/PATH1')
        self.assertEqual(tracker.get('hey'), 'MODULE!')
        self.find_module.assert_called_once_with('hey', ['/PATH1'])

    @mock.patch('logging.getLogger')
    def test_bad_plugin(self, getLogger):
        tracker = koji.plugin.PluginTracker(path='/MODPATH')
        self.load_module.side_effect = TestError
        with self.assertRaises(TestError):
            tracker.load('hello')
        self.assertEqual(tracker.get('hello'), None)
        getLogger.assert_called_once()
        getLogger.return_value.error.assert_called_once()
