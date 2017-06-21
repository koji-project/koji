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
