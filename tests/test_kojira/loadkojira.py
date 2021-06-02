from __future__ import absolute_import
import os
import sys

try:
    import importlib
    import importlib.machinery
except ImportError:
    import imp
    importlib = None

# TODO - libify kojira so we don't need this hack
KOJIRA_MOD = "kojira_"
KOJIRA_FILENAME = os.path.dirname(__file__) + "/../../util/kojira"

if importlib:
    importlib.machinery.SOURCE_SUFFIXES.append('')
    spec = importlib.util.spec_from_file_location(KOJIRA_MOD, KOJIRA_FILENAME)
    kojira = importlib.util.module_from_spec(spec)
    sys.modules[KOJIRA_MOD] = kojira
    spec.loader.exec_module(kojira)
    importlib.machinery.SOURCE_SUFFIXES.pop()
else:
    kojira = imp.load_source(KOJIRA_MOD, KOJIRA_FILENAME)
