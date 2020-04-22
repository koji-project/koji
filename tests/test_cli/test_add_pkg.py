from __future__ import absolute_import

import mock
import os
import six
import sys
try:
    import unittest2 as unittest
except ImportError:
    import unittest

from mock import call

from koji_cli.commands import handle_add_pkg
from . import utils


class TestAddPkg(utils.CliTestCase):

    # Show long diffs in error output...
    maxDiff = None

    @mock.patch('sys.stdout', new_callable=six.StringIO)
    @mock.patch('koji_cli.commands.activate_session')
    def test_handle_add_pkg(self, activate_session_mock, stdout):
        tag = 'tag'
        dsttag = {'name': tag, 'id': 1}
        package = 'package'
        owner = 'owner'
        owner_info = mock.ANY
        extra_arches = 'arch1,arch2 arch3, arch4'
        args = [
            '--owner=' +
            owner,
            '--extra-arches=' +
            extra_arches,
            tag,
            package]
        kwargs = {'force': None,
                  'block': False,
                  'extra_arches': 'arch1 arch2 arch3 arch4'}
        options = mock.MagicMock()

        # Mock out the xmlrpc server
        session = mock.MagicMock()

        session.getUser.return_value = owner_info
        session.getTag.return_value = dsttag
        session.listPackages.return_value = [
            {'package_name': 'other_package', 'package_id': 2}]
        # Run it and check immediate output
        # args: --owner, --extra-arches='arch1,arch2 arch3, arch4', tag, package
        # expected: success
        rv = handle_add_pkg(options, session, args)
        actual = stdout.getvalue()
        expected = 'Adding 1 packages to tag tag\n'
        self.assertMultiLineEqual(actual, expected)
        # Finally, assert that things were called as we expected.
        activate_session_mock.assert_called_once_with(session, options)
        session.getUser.assert_called_once_with(owner)
        session.getTag.assert_called_once_with(tag)
        session.listPackages.assert_called_once_with(tagID=dsttag['id'])
        session.packageListAdd.assert_called_once_with(
            tag, package, owner, **kwargs)
        session.multiCall.assert_called_once_with(strict=True)
        self.assertNotEqual(rv, 1)

    @mock.patch('sys.stdout', new_callable=six.StringIO)
    @mock.patch('koji_cli.commands.activate_session')
    def test_handle_add_pkg_multi_pkg(self, activate_session_mock, stdout):
        tag = 'tag'
        dsttag = {'name': tag, 'id': 1}
        packages = ['package1', 'package2', 'package3']
        owner = 'owner'
        owner_info = mock.ANY
        extra_arches = 'arch1,arch2 arch3, arch4'
        args = [
            '--owner=' + owner,
            '--extra-arches=' + extra_arches,
            tag] + packages
        kwargs = {'force': None,
                  'block': False,
                  'extra_arches': 'arch1 arch2 arch3 arch4'}
        options = mock.MagicMock()

        # Mock out the xmlrpc server
        session = mock.MagicMock()

        session.getUser.return_value = owner_info
        session.getTag.return_value = dsttag
        session.listPackages.return_value = [
            {'package_name': 'package2', 'package_id': 2}]
        # Run it and check immediate output
        # args: --owner, --extra-arches='arch1,arch2 arch3, arch4',
        #       tag, package1, package2, package3
        # expected: success
        rv = handle_add_pkg(options, session, args)
        actual = stdout.getvalue()
        expected = 'Package package2 already exists in tag tag\nAdding 2 packages to tag tag\n'
        self.assertMultiLineEqual(actual, expected)
        # Finally, assert that things were called as we expected.
        activate_session_mock.assert_called_once_with(session, options)
        self.assertEqual(session.mock_calls,
                         [call.getUser(owner),
                          call.getTag(tag),
                          call.listPackages(tagID=dsttag['id']),
                          call.packageListAdd(tag, packages[0], owner, **kwargs),
                          call.packageListAdd(tag, packages[2], owner, **kwargs),
                          call.multiCall(strict=True)])
        self.assertNotEqual(rv, 1)

    @mock.patch('sys.stderr', new_callable=six.StringIO)
    @mock.patch('koji_cli.commands.activate_session')
    def test_handle_add_pkg_owner_no_exists(
            self, activate_session_mock, stderr):
        tag = 'tag'
        packages = ['package1', 'package2', 'package3']
        owner = 'owner'
        owner_info = None
        extra_arches = 'arch1,arch2 arch3, arch4'
        args = [
            '--owner=' + owner,
            '--extra-arches=' + extra_arches,
            tag] + packages
        options = mock.MagicMock()

        # Mock out the xmlrpc server
        session = mock.MagicMock()

        session.getUser.return_value = owner_info
        # Run it and check immediate output
        # args: --owner, --extra-arches='arch1,arch2 arch3, arch4',
        #       tag, package1, package2, package3
        # expected: failed: owner does not exist
        with self.assertRaises(SystemExit) as ex:
            handle_add_pkg(options, session, args)
        self.assertExitCode(ex, 1)
        actual = stderr.getvalue()
        expected = 'User owner does not exist\n'
        self.assertMultiLineEqual(actual, expected)
        # Finally, assert that things were called as we expected.
        activate_session_mock.assert_not_called()
        self.assertEqual(session.mock_calls,
                         [call.getUser(owner)])

    @mock.patch('sys.stdout', new_callable=six.StringIO)
    @mock.patch('koji_cli.commands.activate_session')
    def test_handle_add_pkg_tag_no_exists(self, activate_session_mock, stdout):
        tag = 'tag'
        dsttag = None
        packages = ['package1', 'package2', 'package3']
        owner = 'owner'
        owner_info = mock.ANY
        extra_arches = 'arch1,arch2 arch3, arch4'
        args = [
            '--owner=' + owner,
            '--extra-arches=' + extra_arches,
            tag] + packages
        options = mock.MagicMock()

        # Mock out the xmlrpc server
        session = mock.MagicMock()

        session.getUser.return_value = owner_info
        session.getTag.return_value = dsttag
        # Run it and check immediate output
        # args: --owner, --extra-arches='arch1,arch2 arch3, arch4',
        #       tag, package1, package2, package3
        # expected: failed: tag does not exist
        with self.assertRaises(SystemExit) as ex:
            handle_add_pkg(options, session, args)
        self.assertExitCode(ex, 1)
        actual = stdout.getvalue()
        expected = 'No such tag: tag\n'
        self.assertMultiLineEqual(actual, expected)
        # Finally, assert that things were called as we expected.
        activate_session_mock.assert_called_once_with(session, options)
        self.assertEqual(session.mock_calls,
                         [call.getUser(owner),
                          call.getTag(tag)])

    @mock.patch('sys.stdout', new_callable=six.StringIO)
    @mock.patch('sys.stderr', new_callable=six.StringIO)
    @mock.patch('koji_cli.commands.activate_session')
    def test_handle_add_pkg_no_owner(
            self, activate_session_mock, stderr, stdout):
        tag = 'tag'
        packages = ['package1', 'package2', 'package3']
        extra_arches = 'arch1,arch2 arch3, arch4'
        args = ['--extra-arches=' + extra_arches, tag] + packages
        options = mock.MagicMock()

        progname = os.path.basename(sys.argv[0]) or 'koji'

        # Mock out the xmlrpc server
        session = mock.MagicMock()

        # Run it and check immediate output
        with self.assertRaises(SystemExit) as ex:
            handle_add_pkg(options, session, args)
        self.assertExitCode(ex, 2)
        actual_stdout = stdout.getvalue()
        actual_stderr = stderr.getvalue()
        expected_stdout = ''
        expected_stderr = """Usage: %s add-pkg [options] --owner <owner> <tag> <package> [<package> ...]
(Specify the --help global option for a list of other help options)

%s: error: Please specify an owner for the package(s)
""" % (progname, progname)
        self.assertMultiLineEqual(actual_stdout, expected_stdout)
        self.assertMultiLineEqual(actual_stderr, expected_stderr)

        # Finally, assert that things were called as we expected.
        activate_session_mock.assert_not_called()
        session.getUser.assert_not_called()
        session.getTag.assert_not_called()
        session.listPackages.assert_not_called()
        session.packageListAdd.assert_not_called()

    @mock.patch('sys.stdout', new_callable=six.StringIO)
    @mock.patch('sys.stderr', new_callable=six.StringIO)
    @mock.patch('koji_cli.commands.activate_session')
    def test_handle_add_pkg_no_arg(
            self, activate_session_mock, stderr, stdout):
        args = []
        options = mock.MagicMock()
        progname = os.path.basename(sys.argv[0]) or 'koji'

        # Mock out the xmlrpc server
        session = mock.MagicMock()

        # Run it and check immediate output
        with self.assertRaises(SystemExit) as ex:
            handle_add_pkg(options, session, args)
        self.assertExitCode(ex, 2)
        actual_stdout = stdout.getvalue()
        actual_stderr = stderr.getvalue()
        expected_stdout = ''
        expected_stderr = """Usage: %s add-pkg [options] --owner <owner> <tag> <package> [<package> ...]
(Specify the --help global option for a list of other help options)

%s: error: Please specify a tag and at least one package
""" % (progname, progname)
        self.assertMultiLineEqual(actual_stdout, expected_stdout)
        self.assertMultiLineEqual(actual_stderr, expected_stderr)

        # Finally, assert that things were called as we expected.
        activate_session_mock.assert_not_called()
        session.getUser.assert_not_called()
        session.getTag.assert_not_called()
        session.listPackages.assert_not_called()
        session.packageListAdd.assert_not_called()


if __name__ == '__main__':
    unittest.main()
