from __future__ import absolute_import
import os


# TODO - libify kojira so we don't need this hack
CLI_FILENAME = os.path.dirname(__file__) + "/../../util/kojira"
import imp
kojira = imp.load_source('kojira', CLI_FILENAME)
