import os
import imp

# We have to do this craziness because 'import koji' is ambiguous.  Is it the
# koji module, or the koji cli module.  Jump through hoops accordingly.
# https://stackoverflow.com/questions/67631/how-to-import-a-module-given-the-full-path
INDEX_FILENAME = os.path.dirname(__file__) + "/../../www/kojiweb/index.py"

webidx = imp.load_source('index_fake', INDEX_FILENAME)
