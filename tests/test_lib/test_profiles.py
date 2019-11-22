from __future__ import absolute_import
import koji
import sys
import threading
import traceback
import mock
from six.moves import range

try:
    import unittest2 as unittest
except ImportError:
    import unittest

class ProfilesTestCase(unittest.TestCase):

    def test_profile_threading(self):
        """ Test that profiles thread safe"""
        # see: https://pagure.io/koji/issue/58 and https://pagure.io/pungi/issue/253
        # loop a few times to increase chances of hitting race conditions
        for i in range(256):
            errors = {}
            threads = [threading.Thread(target=stress, args=(errors, _)) for _ in range(100)]
            for t in threads:
                t.start()
            for t in threads:
                t.join(30)
            for n in errors:
                err = errors[n]
                if err is not None:
                    print(err)
                    assert False


def stress(errors, n):
    errors[n] = "Failed to start"
    try:
        config = mock.Mock(topdir='topdir')
        koji.get_profile_module('koji', config=config)
    except Exception:
        # if we don't catch this, nose seems to ignore the test
        errors[n] = ''.join(traceback.format_exception(*sys.exc_info()))
        return
    else:
        errors[n] = None



