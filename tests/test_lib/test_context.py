from __future__ import absolute_import
import six
import time
import random
from six.moves import range
try:
    import unittest2 as unittest
except ImportError:
    import unittest

from koji.context import context


class TestContext(unittest.TestCase):

    def test_context(self):
        context.foo = 1

        def test():
            foo = random.random()
            context.foo = foo
            time.sleep(0.5 + random.random())
            print(context)
            self.assertEqual(context.foo, foo)
            context._threadclear()
            self.assertFalse(hasattr(context, 'foo'))

        for x in range(1, 10):
            six.moves._thread.start_new_thread(test, ())

        time.sleep(0.5)
        for i in range(10):
            time.sleep(0.2 + random.random())
            self.assertEqual(context.foo, 1)

        context.foo = 2
        context.bar = 3
        self.assertEqual(context.foo, 2)
        self.assertEqual(context.bar, 3)
        context._threadclear()
        self.assertFalse(hasattr(context, 'foo'))
        self.assertFalse(hasattr(context, 'bar'))
