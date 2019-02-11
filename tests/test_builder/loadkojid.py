from __future__ import absolute_import
import os
import sys

# http://stackoverflow.com/questions/67631/how-to-import-a-module-given-the-full-path
KOJID_FILENAME = os.path.dirname(__file__) + "/../../builder/kojid"
if sys.version_info[0] >= 3:
    import importlib.util
    import importlib.machinery
    loader = importlib.machinery.SourceFileLoader('koji_kojid', KOJID_FILENAME)
    spec = importlib.util.spec_from_file_location("koji_kojid", loader=loader)
    kojid = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(kojid)
else:
    import imp
    kojid = imp.load_source('koji_kojid', KOJID_FILENAME)
