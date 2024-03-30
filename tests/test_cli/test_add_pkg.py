from __future__ import absolute_import

import unittest

import mock
import six
import koji
from mock import call

from koji_cli.commands import handle_add_pkg
from . import utils


class TestAddPkg(utils.CliTestCase):

    def setUp(self):
        # Show long diffs in error output...
        self.options = mock.MagicMock()
        self.options.quiet = True
        self.options.debug = False
        self.session = mock.MagicMock()
        self.session.getAPIVersion.return_value = koji.API_VERSION
        self.activate_session_mock = mock.patch('koji_cli.commands.activate_session').start()
        self.error_format = """Usage: %s add-pkg [options] --owner <owner> <tag> <package> [<package> ...]
(Specify the --help global option for a list of other help options)

%s: error: {message}
""" % (self.progname, self.progname)

    def tearDown(self):
        mock.patch.stopall()

    @mock.patch('sys.stdout', new_callable=six.StringIO)
    def test_handle_add_pkg(self, stdout):
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

        self.session.getUser.return_value = owner_info
        self.session.getTag.return_value = dsttag
        self.session.listPackages.return_value = [
            {'package_name': 'other_package', 'package_id': 2}]
        # Run it and check immediate output
        # args: --owner, --extra-arches='arch1,arch2 arch3, arch4', tag, package
        # expected: success
        rv = handle_add_pkg(self.options, self.session, args)
        actual = stdout.getvalue()
        expected = 'Adding 1 packages to tag tag\n'
        self.assertMultiLineEqual(actual, expected)
        # Finally, assert that things were called as we expected.
        self.activate_session_mock.assert_called_once_with(self.session, self.options)
        self.session.getUser.assert_called_once_with(owner)
        self.session.getTag.assert_called_once_with(tag)
        self.session.listPackages.assert_called_once_with(tagID=dsttag['id'], with_owners=False)
        self.session.packageListAdd.assert_called_once_with(
            tag, package, owner, **kwargs)
        self.session.multiCall.assert_called_once_with(strict=True)
        self.assertNotEqual(rv, 1)

    @mock.patch('sys.stdout', new_callable=six.StringIO)
    def test_handle_add_pkg_multi_pkg(self, stdout):
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

        self.session.getUser.return_value = owner_info
        self.session.getTag.return_value = dsttag
        self.session.listPackages.return_value = [
            {'package_name': 'package2', 'package_id': 2}]
        # Run it and check immediate output
        # args: --owner, --extra-arches='arch1,arch2 arch3, arch4',
        #       tag, package1, package2, package3
        # expected: success
        rv = handle_add_pkg(self.options, self.session, args)
        actual = stdout.getvalue()
        expected = 'Package package2 already exists in tag tag\nAdding 2 packages to tag tag\n'
        self.assertMultiLineEqual(actual, expected)
        # Finally, assert that things were called as we expected.
        self.activate_session_mock.assert_called_once_with(self.session, self.options)
        self.assertEqual(self.session.mock_calls,
                         [call.getUser(owner),
                          call.getTag(tag),
                          call.listPackages(tagID=dsttag['id'], with_owners=False),
                          call.packageListAdd(tag, packages[0], owner, **kwargs),
                          call.packageListAdd(tag, packages[2], owner, **kwargs),
                          call.multiCall(strict=True)])
        self.assertNotEqual(rv, 1)

    def test_handle_add_pkg_owner_no_exists(self):
        tag = 'tag'
        packages = ['package1', 'package2', 'package3']
        owner = 'owner'
        owner_info = None
        extra_arches = 'arch1,arch2 arch3, arch4'
        arguments = [
            '--owner=' + owner,
            '--extra-arches=' + extra_arches,
            tag] + packages

        self.session.getUser.return_value = owner_info
        # Run it and check immediate output
        # args: --owner, --extra-arches='arch1,arch2 arch3, arch4',
        #       tag, package1, package2, package3
        # expected: failed: owner does not exist
        self.assert_system_exit(
            handle_add_pkg,
            self.options, self.session, arguments,
            stdout='',
            stderr='No such user: %s\n' % owner,
            exit_code=1,
            activate_session=None)
        # Finally, assert that things were called as we expected.
        self.activate_session_mock.assert_not_called()
        self.assertEqual(self.session.mock_calls, [call.getUser(owner)])

    def test_handle_add_pkg_tag_no_exists(self):
        tag = 'tag'
        dsttag = None
        packages = ['package1', 'package2', 'package3']
        owner = 'owner'
        owner_info = mock.ANY
        extra_arches = 'arch1,arch2 arch3, arch4'
        arguments = ['--owner=' + owner, '--extra-arches=' + extra_arches, tag] + packages

        self.session.getUser.return_value = owner_info
        self.session.getTag.return_value = dsttag
        # Run it and check immediate output
        # args: --owner, --extra-arches='arch1,arch2 arch3, arch4',
        #       tag, package1, package2, package3
        # expected: failed: tag does not exist
        self.assert_system_exit(
            handle_add_pkg,
            self.options, self.session, arguments,
            stdout='',
            stderr='No such tag: %s\n' % tag,
            exit_code=1,
            activate_session=None)

        # Finally, assert that things were called as we expected.
        self.activate_session_mock.assert_called_once_with(self.session, self.options)
        self.assertEqual(self.session.mock_calls, [call.getUser(owner), call.getTag(tag)])

    def test_handle_add_pkg_no_owner(self):
        tag = 'tag'
        packages = ['package1', 'package2', 'package3']
        extra_arches = 'arch1,arch2 arch3, arch4'
        arguments = ['--extra-arches=' + extra_arches, tag] + packages

        # Run it and check immediate output
        self.assert_system_exit(
            handle_add_pkg,
            self.options, self.session, arguments,
            stdout='',
            stderr=self.format_error_message('Please specify an owner for the package(s)'),
            exit_code=2,
            activate_session=None)

        # Finally, assert that things were called as we expected.
        self.activate_session_mock.assert_not_called()
        self.session.getUser.assert_not_called()
        self.session.getTag.assert_not_called()
        self.session.listPackages.assert_not_called()
        self.session.packageListAdd.assert_not_called()

    def test_handle_add_pkg_no_arg(self):
        arguments = []

        # Run it and check immediate output
        self.assert_system_exit(
            handle_add_pkg,
            self.options, self.session, arguments,
            stdout='',
            stderr=self.format_error_message('Please specify a tag and at least one package'),
            exit_code=2,
            activate_session=None)

        # Finally, assert that things were called as we expected.
        self.activate_session_mock.assert_not_called()
        self.session.getUser.assert_not_called()
        self.session.getTag.assert_not_called()
        self.session.listPackages.assert_not_called()
        self.session.packageListAdd.assert_not_called()

    @mock.patch('sys.stdout', new_callable=six.StringIO)
    def test_handle_add_pkg_parameter_error(self, stdout):
        tag = 'tag'
        dsttag = {'name': tag, 'id': 1}
        package = 'package'
        owner = 'testuser'
        args = ['--owner', owner, tag, package]

        self.session.getTag.return_value = dsttag
        self.session.listPackages.side_effect = [koji.ParameterError, []]
        # Run it and check immediate output
        # args: tag, package
        # expected: success
        rv = handle_add_pkg(self.options, self.session, args)
        actual = stdout.getvalue()
        expected = 'Adding 1 packages to tag tag\n'
        self.assertMultiLineEqual(actual, expected)
        # Finally, assert that things were called as we expected.
        self.activate_session_mock.assert_called_once_with(self.session, self.options)
        self.session.getTag.assert_called_once_with(tag)
        self.session.listPackages.assert_has_calls([
            call(tagID=dsttag['id'], with_owners=False),
            call(tagID=dsttag['id'])
        ])
        self.session.packageListAdd.assert_called_once_with(
            tag, package, owner, block=False, force=None)
        self.session.multiCall.assert_called_once_with(strict=True)
        self.assertFalse(rv)

    def test_handle_add_pkg_help(self):
        self.assert_help(
            handle_add_pkg,
            """Usage: %s add-pkg [options] --owner <owner> <tag> <package> [<package> ...]
(Specify the --help global option for a list of other help options)

Options:
  -h, --help            show this help message and exit
  --force               Override blocks if necessary
  --owner=OWNER         Specify owner
  --extra-arches=EXTRA_ARCHES
                        Specify extra arches
""" % self.progname)


if __name__ == '__main__':
    unittest.main()
