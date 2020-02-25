from __future__ import absolute_import
import json
import mock
import os
import six
import sys
try:
    import unittest2 as unittest
except ImportError:
    import unittest

try:
    import libcomps
except ImportError:
    libcomps = None
try:
    import yum.comps as yumcomps
except ImportError:
    yumcomps = None

from nose.plugins.skip import SkipTest

import koji_cli.commands
from koji_cli.commands import handle_import_comps, _import_comps,\
                              _import_comps_alt
from . import utils

class TestImportComps(utils.CliTestCase):
    # Show long diffs in error output...
    maxDiff = None

    @mock.patch('sys.stdout', new_callable=six.StringIO)
    @mock.patch('koji_cli.commands.libcomps')
    @mock.patch('koji_cli.commands.activate_session')
    @mock.patch('koji_cli.commands._import_comps')
    @mock.patch('koji_cli.commands._import_comps_alt')
    def test_handle_import_comps_libcomps(
            self,
            mock_import_comps_alt,
            mock_import_comps,
            mock_activate_session,
            libcomps,
            stdout):
        filename = './data/comps-example.xml'
        tag = 'tag'
        tag_info = {'name': tag, 'id': 1}
        force = None
        args = [filename, tag]
        kwargs = {'force': force}
        options = mock.MagicMock()

        # Mock out the xmlrpc server
        session = mock.MagicMock()
        session.getTag.return_value = tag_info

        # Run it and check immediate output
        # args: ./data/comps-example.xml, tag
        # expected: success
        rv = handle_import_comps(options, session, args)
        actual = stdout.getvalue()
        expected = ''
        self.assertMultiLineEqual(actual, expected)

        # Finally, assert that things were called as we expected.
        mock_activate_session.assert_called_once_with(session, options)
        session.getTag.assert_called_once_with(tag)
        mock_import_comps.assert_called_once_with(
            session, filename, tag, kwargs)
        mock_import_comps_alt.assert_not_called()
        self.assertNotEqual(rv, 1)

    @mock.patch('sys.stdout', new_callable=six.StringIO)
    @mock.patch('koji_cli.commands.libcomps', new=None)
    @mock.patch('koji_cli.commands.yumcomps', create=True)
    @mock.patch('koji_cli.commands.activate_session')
    @mock.patch('koji_cli.commands._import_comps')
    @mock.patch('koji_cli.commands._import_comps_alt')
    def test_handle_import_comps_yumcomps(
            self,
            mock_import_comps_alt,
            mock_import_comps,
            mock_activate_session,
            yumcomps,
            stdout):
        filename = './data/comps-example.xml'
        tag = 'tag'
        tag_info = {'name': tag, 'id': 1}
        force = True
        args = ['--force', filename, tag]
        local_options = {'force': force}
        options = mock.MagicMock()

        # Mock out the xmlrpc server
        session = mock.MagicMock()
        session.getTag.return_value = tag_info

        # Run it and check immediate output
        # args: --force, ./data/comps-example.xml, tag
        # expected: success
        rv = handle_import_comps(options, session, args)
        actual = stdout.getvalue()
        expected = ''
        self.assertMultiLineEqual(actual, expected)

        # Finally, assert that things were called as we expected.
        mock_activate_session.assert_called_once_with(session, options)
        session.getTag.assert_called_once_with(tag)
        mock_import_comps.assert_not_called()
        mock_import_comps_alt.assert_called_once_with(
            session, filename, tag, local_options)
        self.assertNotEqual(rv, 1)

    @mock.patch('sys.stderr', new_callable=six.StringIO)
    @mock.patch('koji_cli.commands.libcomps', new=None)
    @mock.patch('koji_cli.commands.yumcomps', new=None, create=True)
    @mock.patch('koji_cli.commands.activate_session')
    @mock.patch('koji_cli.commands._import_comps')
    @mock.patch('koji_cli.commands._import_comps_alt')
    def test_handle_import_comps_comps_na(
            self,
            mock_import_comps_alt,
            mock_import_comps,
            mock_activate_session,
            stderr):
        filename = './data/comps-example.xml'
        tag = 'tag'
        tag_info = {'name': tag, 'id': 1}
        args = ['--force', filename, tag]
        options = mock.MagicMock()

        # Mock out the xmlrpc server
        session = mock.MagicMock()
        session.getTag.return_value = tag_info

        # Run it and check immediate output
        # args: --force, ./data/comps-example.xml, tag
        # expected: failed, no comps available
        with self.assertRaises(SystemExit) as ex:
            handle_import_comps(options, session, args)
        self.assertExitCode(ex, 1)
        actual = stderr.getvalue()
        expected = 'comps module not available\n'
        self.assertMultiLineEqual(actual, expected)

        # Finally, assert that things were called as we expected.
        mock_activate_session.assert_called_once_with(session, options)
        session.getTag.assert_called_once_with(tag)
        mock_import_comps.assert_not_called()
        mock_import_comps_alt.assert_not_called()

    @mock.patch('sys.stderr', new_callable=six.StringIO)
    @mock.patch('koji_cli.commands.activate_session')
    @mock.patch('koji_cli.commands._import_comps')
    @mock.patch('koji_cli.commands._import_comps_alt')
    def test_handle_import_comps_tag_not_exists(
            self,
            mock_import_comps_alt,
            mock_import_comps,
            mock_activate_session,
            stderr):
        filename = './data/comps-example.xml'
        tag = 'tag'
        tag_info = None
        args = [filename, tag]
        options = mock.MagicMock()

        # Mock out the xmlrpc server
        session = mock.MagicMock()
        session.getTag.return_value = tag_info

        # Run it and check immediate output
        # args: ./data/comps-example.xml, tag
        # expected: failed: tag does not exist
        with self.assertRaises(SystemExit) as ex:
            handle_import_comps(options, session, args)
        self.assertExitCode(ex, 1)
        actual = stderr.getvalue()
        expected = 'No such tag: tag\n'
        self.assertMultiLineEqual(actual, expected)

        # Finally, assert that things were called as we expected.
        mock_activate_session.assert_called_once_with(session, options)
        session.getTag.assert_called_once_with(tag)
        mock_import_comps.assert_not_called()
        mock_import_comps_alt.assert_not_called()

    @mock.patch('sys.stdout', new_callable=six.StringIO)
    @mock.patch('sys.stderr', new_callable=six.StringIO)
    @mock.patch('koji_cli.commands.activate_session')
    @mock.patch('koji_cli.commands._import_comps')
    @mock.patch('koji_cli.commands._import_comps_alt')
    def test_handle_import_comps_help(
            self,
            mock_import_comps_alt, mock_import_comps,
            mock_activate_session,
            stderr,
            stdout):
        args = []
        progname = os.path.basename(sys.argv[0]) or 'koji'
        options = mock.MagicMock()

        # Mock out the xmlrpc server
        session = mock.MagicMock()

        # Run it and check immediate output
        with self.assertRaises(SystemExit) as ex:
            handle_import_comps(options, session, args)
        self.assertExitCode(ex, 2)
        actual_stdout = stdout.getvalue()
        actual_stderr = stderr.getvalue()
        expected_stdout = ''
        expected_stderr = """Usage: %s import-comps [options] <file> <tag>
(Specify the --help global option for a list of other help options)

%s: error: Incorrect number of arguments
""" % (progname, progname)
        self.assertMultiLineEqual(actual_stdout, expected_stdout)
        self.assertMultiLineEqual(actual_stderr, expected_stderr)

        # Finally, assert that things were called as we expected.
        mock_activate_session.assert_not_called()
        session.getTag.assert_not_called()
        session.getTagGroups.assert_not_called()
        session.groupListAdd.assert_not_called()

    @mock.patch('sys.stdout', new_callable=six.StringIO)
    def test_import_comps_libcomps(self, stdout):
        if libcomps is None:
            raise SkipTest('no libcomps')
        comps_file = os.path.dirname(__file__) + '/data/comps-example.xml'
        stdout_file = os.path.dirname(
            __file__) + '/data/comps-example.libcomps.out'
        calls_file = os.path.dirname(
            __file__) + '/data/comps-example.libcomps.calls'
        self._test_import_comps(
            _import_comps,
            comps_file,
            stdout_file,
            calls_file,
            stdout)

    @mock.patch('sys.stdout', new_callable=six.StringIO)
    def test_import_comps_sample_libcomps(self, stdout):
        if libcomps is None:
            raise SkipTest('no libcomps')
        comps_file = os.path.dirname(__file__) + '/data/comps-sample.xml'
        stdout_file = os.path.dirname(
            __file__) + '/data/comps-sample.libcomps.out'
        calls_file = os.path.dirname(
            __file__) + '/data/comps-sample.libcomps.calls'
        self._test_import_comps(
            _import_comps,
            comps_file,
            stdout_file,
            calls_file,
            stdout)

    @mock.patch('sys.stdout', new_callable=six.StringIO)
    @mock.patch('koji_cli.commands.libcomps', new=None)
    @mock.patch('koji_cli.commands.yumcomps', create=True, new=yumcomps)
    def test_import_comps_yumcomps(self, stdout):
        if yumcomps is None:
            raise SkipTest('no yum.comps')
        comps_file = os.path.dirname(__file__) + '/data/comps-example.xml'
        stdout_file = os.path.dirname(
            __file__) + '/data/comps-example.yumcomps.out'
        calls_file = os.path.dirname(
            __file__) + '/data/comps-example.yumcomps.calls'
        self._test_import_comps(
            _import_comps_alt,
            comps_file,
            stdout_file,
            calls_file,
            stdout)

    @mock.patch('sys.stdout', new_callable=six.StringIO)
    @mock.patch('koji_cli.commands.libcomps', new=None)
    @mock.patch('koji_cli.commands.yumcomps', create=True, new=yumcomps)
    def test_import_comps_sample_yumcomps(self, stdout):
        if yumcomps is None:
            raise SkipTest('no yum.comps')
        comps_file = os.path.dirname(__file__) + '/data/comps-sample.xml'
        stdout_file = os.path.dirname(
            __file__) + '/data/comps-sample.yumcomps.out'
        calls_file = os.path.dirname(
            __file__) + '/data/comps-sample.yumcomps.calls'
        self._test_import_comps(
            _import_comps_alt,
            comps_file,
            stdout_file,
            calls_file,
            stdout)

    def _test_import_comps(
            self,
            method,
            comps_file,
            stdout_file,
            calls_file,
            stdout):
        tag = 'tag'
        options = mock.MagicMock()
        options.force = None

        # Mock out the xmlrpc server
        session = mock.MagicMock()

        # Run it and check immediate output
        # args: comps.xml, tag
        # expected: success
        rv = method.__call__(session, comps_file, tag, options)
        expected = ''
        with open(stdout_file, 'rb') as f:
            expected = f.read().decode('ascii')
        self.assertMultiLineEqual(stdout.getvalue(), expected)

        # compare mock_calls stored as json
        expected = []
        for c in json.load(open(calls_file, 'rt')):
            expected.append(getattr(mock.call, c[0]).__call__(*c[1], **c[2]))

        if hasattr(session, 'assertHasCalls'):
            session.assertHasCalls(expected)
        else:
            session.assert_has_calls(expected)
        self.assertNotEqual(rv, 1)


def _generate_out_calls(method, comps_file, stdout_file, calls_file):
    tag = 'tag'
    force = None
    options = {'force': force}

    # Mock out the xmlrpc server
    session = mock.MagicMock()

    with open(stdout_file, 'wb') as f:
        # redirect stdout to stdout_file
        orig_stdout = sys.stdout
        sys.stdout = f
        # args: comps.xml, tag
        # expected: success
        method.__call__(session, comps_file, tag, options)
        sys.stdout = orig_stdout
    with open(calls_file, 'wb') as f:
        f.write(str(session.mock_calls).encode('ascii') + '\n')


def generate_out_calls():
    """Generate .out and .calls files for tests.
    These files should be carefully check to make sure they're excepted"""
    path = os.path.dirname(__file__)

    comps_file = path + '/data/comps-example.xml'
    stdout_file = path + '/data/comps-example.libcomps.out'
    calls_file = path + '/data/comps-example.libcomps.calls'
    _generate_out_calls(_import_comps, comps_file, stdout_file, calls_file)

    comps_file = path + '/data/comps-sample.xml'
    stdout_file = path + '/data/comps-sample.libcomps.out'
    calls_file = path + '/data/comps-sample.libcomps.calls'
    _generate_out_calls(_import_comps, comps_file, stdout_file, calls_file)

    koji_cli.commands.yumcomps = yumcomps

    comps_file = path + '/data/comps-example.xml'
    stdout_file = path + '/data/comps-example.yumcomps.out'
    calls_file = path + '/data/comps-example.yumcomps.calls'
    _generate_out_calls(
        _import_comps_alt,
        comps_file,
        stdout_file,
        calls_file)

    comps_file = path + '/data/comps-sample.xml'
    stdout_file = path + '/data/comps-sample.yumcomps.out'
    calls_file = path + '/data/comps-sample.yumcomps.calls'
    _generate_out_calls(
        _import_comps_alt,
        comps_file,
        stdout_file,
        calls_file)


if __name__ == '__main__':
    unittest.main()
