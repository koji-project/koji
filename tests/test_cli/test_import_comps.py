import unittest


import StringIO as stringio

import os

import sys

import mock

import loadcli

import yum.comps as yumcomps

cli = loadcli.cli


class TestImportComps(unittest.TestCase):

    # Show long diffs in error output...
    maxDiff = None

    @mock.patch('sys.stdout', new_callable=stringio.StringIO)
    @mock.patch('koji_cli.libcomps')
    @mock.patch('koji_cli.activate_session')
    @mock.patch('koji_cli._import_comps')
    @mock.patch('koji_cli._import_comps_alt')
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
        rv = cli.handle_import_comps(options, session, args)
        actual = stdout.getvalue()
        expected = ''
        self.assertMultiLineEqual(actual, expected)

        # Finally, assert that things were called as we expected.
        mock_activate_session.assert_called_once_with(session)
        session.getTag.assert_called_once_with(tag)
        mock_import_comps.assert_called_once_with(
            session, filename, tag, kwargs)
        mock_import_comps_alt.assert_not_called()
        self.assertNotEqual(rv, 1)

    @mock.patch('sys.stdout', new_callable=stringio.StringIO)
    @mock.patch('koji_cli.libcomps', new=None)
    @mock.patch('koji_cli.yumcomps', create=True)
    @mock.patch('koji_cli.activate_session')
    @mock.patch('koji_cli._import_comps')
    @mock.patch('koji_cli._import_comps_alt')
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
        rv = cli.handle_import_comps(options, session, args)
        actual = stdout.getvalue()
        expected = ''
        self.assertMultiLineEqual(actual, expected)

        # Finally, assert that things were called as we expected.
        mock_activate_session.assert_called_once_with(session)
        session.getTag.assert_called_once_with(tag)
        mock_import_comps.assert_not_called()
        mock_import_comps_alt.assert_called_once_with(
            session, filename, tag, local_options)
        self.assertNotEqual(rv, 1)

    @mock.patch('sys.stdout', new_callable=stringio.StringIO)
    @mock.patch('koji_cli.libcomps', new=None)
    @mock.patch('koji_cli.yumcomps', new=None, create=True)
    @mock.patch('koji_cli.activate_session')
    @mock.patch('koji_cli._import_comps')
    @mock.patch('koji_cli._import_comps_alt')
    def test_handle_import_comps_comps_na(
            self,
            mock_import_comps_alt,
            mock_import_comps,
            mock_activate_session,
            stdout):
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
        rv = cli.handle_import_comps(options, session, args)
        actual = stdout.getvalue()
        expected = 'comps module not available\n'
        self.assertMultiLineEqual(actual, expected)

        # Finally, assert that things were called as we expected.
        mock_activate_session.assert_called_once_with(session)
        session.getTag.assert_called_once_with(tag)
        mock_import_comps.assert_not_called()
        mock_import_comps_alt.assert_not_called()
        self.assertEqual(rv, 1)

    @mock.patch('sys.stdout', new_callable=stringio.StringIO)
    @mock.patch('koji_cli.activate_session')
    @mock.patch('koji_cli._import_comps')
    @mock.patch('koji_cli._import_comps_alt')
    def test_handle_import_comps_tag_not_exists(
            self,
            mock_import_comps_alt,
            mock_import_comps,
            mock_activate_session,
            stdout):
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
        rv = cli.handle_import_comps(options, session, args)
        actual = stdout.getvalue()
        expected = 'No such tag: tag\n'
        self.assertMultiLineEqual(actual, expected)

        # Finally, assert that things were called as we expected.
        mock_activate_session.assert_called_once_with(session)
        session.getTag.assert_called_once_with(tag)
        mock_import_comps.assert_not_called()
        mock_import_comps_alt.assert_not_called()
        self.assertEqual(rv, 1)

    @mock.patch('sys.stdout', new_callable=stringio.StringIO)
    @mock.patch('sys.stderr', new_callable=stringio.StringIO)
    @mock.patch('koji_cli.activate_session')
    @mock.patch('koji_cli._import_comps')
    @mock.patch('koji_cli._import_comps_alt')
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
        with self.assertRaises(SystemExit) as cm:
            rv = cli.handle_import_comps(options, session, args)
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
        self.assertEqual(cm.exception.code, 2)

    @unittest.skip("unnecessary to execute everytime")
    @mock.patch('sys.stdout', new_callable=stringio.StringIO)
    def test_import_comps_libcomps(self, stdout):
        comps_file = os.path.dirname(__file__) + '/data/comps-example.xml'
        stdout_file = os.path.dirname(
            __file__) + '/data/comps-example.libcomps.out'
        calls_file = os.path.dirname(
            __file__) + '/data/comps-example.libcomps.calls'
        self._test_import_comps(
            cli._import_comps,
            comps_file,
            stdout_file,
            calls_file,
            stdout)

    @mock.patch('sys.stdout', new_callable=stringio.StringIO)
    def test_import_comps_sample_libcomps(self, stdout):
        comps_file = os.path.dirname(__file__) + '/data/comps-sample.xml'
        stdout_file = os.path.dirname(
            __file__) + '/data/comps-sample.libcomps.out'
        calls_file = os.path.dirname(
            __file__) + '/data/comps-sample.libcomps.calls'
        self._test_import_comps(
            cli._import_comps,
            comps_file,
            stdout_file,
            calls_file,
            stdout)

    @unittest.skip("unnecessary to execute everytime")
    @mock.patch('sys.stdout', new_callable=stringio.StringIO)
    @mock.patch('koji_cli.libcomps', new=None)
    @mock.patch('koji_cli.yumcomps', create=True, new=yumcomps)
    def test_import_comps_yumcomps(self, stdout):
        comps_file = os.path.dirname(__file__) + '/data/comps-example.xml'
        stdout_file = os.path.dirname(
            __file__) + '/data/comps-example.yumcomps.out'
        calls_file = os.path.dirname(
            __file__) + '/data/comps-example.yumcomps.calls'
        self._test_import_comps(
            cli._import_comps_alt,
            comps_file,
            stdout_file,
            calls_file,
            stdout)

    @mock.patch('sys.stdout', new_callable=stringio.StringIO)
    @mock.patch('koji_cli.libcomps', new=None)
    @mock.patch('koji_cli.yumcomps', create=True, new=yumcomps)
    def test_import_comps_sample_yumcomps(self, stdout):
        comps_file = os.path.dirname(__file__) + '/data/comps-sample.xml'
        stdout_file = os.path.dirname(
            __file__) + '/data/comps-sample.yumcomps.out'
        calls_file = os.path.dirname(
            __file__) + '/data/comps-sample.yumcomps.calls'
        self._test_import_comps(
            cli._import_comps_alt,
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
        force = None
        options = {'force': force}

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
        # compare mock_calls by literal string
        with open(calls_file, 'rb') as f:
            expected = f.read().decode('ascii')
        self.assertMultiLineEqual(str(session.mock_calls) + '\n', expected)
        self.assertNotEqual(rv, 1)


if __name__ == '__main__':
    unittest.main()
