import os
import sys

try:
    import importlib
    import importlib.machinery
except ImportError:
    import imp
    importlib = None

INDEX_MOD = "index_fake"
INDEX_FILENAME = os.path.dirname(__file__) + "/../../www/kojiweb/index.py"

if importlib:
    spec = importlib.util.spec_from_file_location(INDEX_MOD, INDEX_FILENAME)
    webidx = importlib.util.module_from_spec(spec)
    sys.modules[INDEX_MOD] = webidx
    spec.loader.exec_module(webidx)
else:
    cli = imp.load_source(INDEX_MOD, INDEX_FILENAME)
