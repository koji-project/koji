from __future__ import absolute_import

import mock

from koji_cli.commands import handle_prune_signed_copies
from . import utils


class TestPruneSignedCopies(utils.CliTestCase):

    # Show long diffs in error output...
    maxDiff = None

    def setUp(self):
        self.activate_session_mock = mock.patch('koji_cli.commands.activate_session').start()

    def test_handle_prune_signed_copies_help(self):
        self.assert_help(
            handle_prune_signed_copies,
            """Usage: %s prune-signed-copies [options]
(Specify the --help global option for a list of other help options)

Options:
  -h, --help            show this help message and exit
  -n, --test            Test mode
  -v, --verbose         Be more verbose
  --days=DAYS           Timeout before clearing
  -p PACKAGE, --package=PACKAGE, --pkg=PACKAGE
                        Limit to a single package
  -b BUILD, --build=BUILD
                        Limit to a single build
  -i IGNORE_TAG, --ignore-tag=IGNORE_TAG
                        Ignore these tags when considering whether a build
                        is/was latest
  --ignore-tag-file=IGNORE_TAG_FILE
                        File to read tag ignore patterns from
  -r PROTECT_TAG, --protect-tag=PROTECT_TAG
                        Do not prune signed copies from matching tags
  --protect-tag-file=PROTECT_TAG_FILE
                        File to read tag protect patterns from
  --trashcan-tag=TRASHCAN_TAG
                        Specify trashcan tag
""" % self.progname)
