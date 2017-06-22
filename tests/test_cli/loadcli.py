from __future__ import absolute_import
import os
#import sys

# We have to do this craziness because 'import koji' is ambiguous.  Is it the
# koji module, or the koji cli module.  Jump through hoops accordingly.
# https://stackoverflow.com/questions/67631/how-to-import-a-module-given-the-full-path
CLI_FILENAME = os.path.dirname(__file__) + "/../../cli/koji"
'''
if sys.version_info[0] >= 3:
    import importlib.util
    spec = importlib.util.spec_from_file_location("koji_cli", CLI_FILENAME)
    cli = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(cli)
else:
'''

import imp
cli = imp.load_source('koji_cli_fake', CLI_FILENAME)
