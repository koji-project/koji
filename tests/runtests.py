#!/usr/bin/python

"""Wrapper script for running unit tests"""

__version__ = "$Revision: 1.1 $"

import sys
import os
import os.path
import unittest

testDir = os.path.dirname(sys.argv[0])

sys.path.insert(0, os.path.abspath('%s/..' % testDir))

allTests = unittest.TestSuite()
for root, dirs, files in os.walk(testDir):
    common_path = os.path.commonprefix([os.path.abspath(testDir),
                                        os.path.abspath(root)])
    root_path = os.path.abspath(root).replace(common_path, '').lstrip('/').replace('/', '.')

    for test_file in [item for item in files
                      if item.startswith("test_") and item.endswith(".py")]:
        if len(sys.argv) == 1 or test_file in sys.argv[1:]:
            print "adding %s..." % test_file
            test_file = test_file[:-3]
            if root_path:
                test_file = "%s.%s" % (root_path, test_file)
            suite = unittest.defaultTestLoader.loadTestsFromName(test_file)
            allTests.addTests(suite._tests)

unittest.TextTestRunner(verbosity=2).run(allTests)
