import os
import sys

# http://stackoverflow.com/questions/67631/how-to-import-a-module-given-the-full-path
KOJID_FILENAME = os.path.dirname(__file__) + "/../../builder/kojid"
if sys.version_info[0] >= 3:
    import importlib.util
    spec = importlib.util.spec_from_file_location("koji_kojid", KOJID_FILENAME)
    kojid = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(kojid)
else:
    import imp
    kojid = imp.load_source('koji_kojid', KOJID_FILENAME)
