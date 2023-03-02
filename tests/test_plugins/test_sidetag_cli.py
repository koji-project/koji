from __future__ import absolute_import
import io
import mock
import six
import unittest
import os
import sys

import koji
from . import load_plugin

sidetag = load_plugin.load_plugin('cli', 'sidetag_cli')


def mock_stdout():
    def get_mock():
        if six.PY2:
            return six.StringIO()
        else:
            return io.TextIOWrapper(six.BytesIO())
    return mock.patch('sys.stdout', new_callable=get_mock)


def get_stdout_value(stdout):
    if six.PY2:
        return stdout.getvalue()
    else:
        # we have to force the TextIOWrapper to stop buffering
        return stdout.detach().getvalue()


class TestSideTagCLI(unittest.TestCase):

    def setUp(self):
        # Show long diffs in error output...
        self.maxDiff = None
        self.options = mock.MagicMock()
        self.options.debug = False
        self.options.quiet = False
        self.session = mock.MagicMock()
        self.session.getAPIVersion.return_value = koji.API_VERSION
        self.activate_session_mock = mock.patch('koji_cli.commands.activate_session').start()
        self.progname = os.path.basename(sys.argv[0]) or 'koji'

    def tearDown(self):
        mock.patch.stopall()

    @mock_stdout()
    def test_add_sidetag_help(self, stdout):
        with self.assertRaises(SystemExit) as ex:
            sidetag.handle_add_sidetag(self.options, self.session, ['--help'])
        std_output = get_stdout_value(stdout).decode('utf-8')
        expected_help = """usage: %s add-sidetag [options] <basetag>
(Specify the --help global option for a list of other help options)

positional arguments:
  basetag          name of basetag

options:
  -h, --help       show this help message and exit
  -q, --quiet      Do not print tag name
  -w, --wait       Wait until repo is ready.
  --debuginfo      Buildroot repo will contain debuginfos
  --suffix SUFFIX  Suffix from hub-supported ones
""" % self.progname
        self.assertMultiLineEqual(std_output, expected_help)
        self.assertEqual('0', str(ex.exception))

    @mock_stdout()
    def test_edit_sidetag_help(self, stdout):
        with self.assertRaises(SystemExit) as ex:
            sidetag.handle_edit_sidetag(self.options, self.session, ['--help'])
        std_output = get_stdout_value(stdout).decode('utf-8')
        expected_help = """usage: %s edit-sidetag [options] <sidetag>
(Specify the --help global option for a list of other help options)

positional arguments:
  sidetag               name of sidetag

options:
  -h, --help            show this help message and exit
  --debuginfo           Generate debuginfo repository
  --no-debuginfo
  --rpm-macro key=value
                        Set tag-specific rpm macros
  --remove-rpm-macro key
                        Remove rpm macros
""" % self.progname
        self.assertMultiLineEqual(std_output, expected_help)
        self.assertEqual('0', str(ex.exception))

    @mock_stdout()
    def test_list_sidetags_help(self, stdout):
        with self.assertRaises(SystemExit) as ex:
            sidetag.handle_list_sidetags(self.options, self.session, ['--help'])
        std_output = get_stdout_value(stdout).decode('utf-8')
        expected_help = """usage: %s list-sidetags [options]
(Specify the --help global option for a list of other help options)

options:
  -h, --help         show this help message and exit
  --basetag BASETAG  Filter on basetag
  --user USER        Filter on user
  --mine             Filter on user
""" % self.progname
        self.assertMultiLineEqual(std_output, expected_help)
        self.assertEqual('0', str(ex.exception))

    @mock_stdout()
    def test_remove_sidetag_help(self, stdout):
        with self.assertRaises(SystemExit) as ex:
            sidetag.handle_remove_sidetag(self.options, self.session, ['--help'])
        std_output = get_stdout_value(stdout).decode('utf-8')
        expected_help = """usage: %s remove-sidetag [options] <sidetag> ...
(Specify the --help global option for a list of other help options)

positional arguments:
  sidetags    name of sidetag

options:
  -h, --help  show this help message and exit
""" % self.progname
        self.assertMultiLineEqual(std_output, expected_help)
        self.assertEqual('0', str(ex.exception))
