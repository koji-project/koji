from __future__ import absolute_import

import unittest

import mock
import six
from mock import call

from koji_cli.commands import handle_remove_pkg

import koji
from . import utils


class TestRemovePkg(utils.CliTestCase):

    def setUp(self):
        # Show long diffs in error output...
        self.maxDiff = None
        self.options = mock.MagicMock()
        self.options.debug = False
        self.session = mock.MagicMock()
        self.session.getAPIVersion.return_value = koji.API_VERSION
        self.activate_session_mock = mock.patch('koji_cli.commands.activate_session').start()
        self.error_format = """Usage: %s remove-pkg [options] <tag> <package> [<package> ...]
(Specify the --help global option for a list of other help options)

%s: error: {message}
""" % (self.progname, self.progname)

    def tearDown(self):
        mock.patch.stopall()

    @mock.patch('sys.stderr', new_callable=six.StringIO)
    def test_handle_remove_pkg(self, stderr):
        tag = 'tag'
        dsttag = {'name': tag, 'id': 1}
        package = 'package'
        args = [tag, package]
        kwargs = {'force': None}

        self.session.getTag.return_value = dsttag
        self.session.listPackages.return_value = [
            {'package_name': package, 'package_id': 1}]
        # Run it and check immediate output
        # args: tag, package
        # expected: success
        handle_remove_pkg(self.options, self.session, args)
        actual = stderr.getvalue()
        expected = ''
        self.assertMultiLineEqual(actual, expected)
        # Finally, assert that things were called as we expected.
        self.activate_session_mock.assert_called_once_with(self.session, self.options)
        self.session.getTag.assert_called_once_with(tag)
        self.session.listPackages.assert_called_once_with(tagID=dsttag['id'], with_owners=False)
        self.session.packageListRemove.assert_called_once_with(
            tag, package, **kwargs)
        self.session.multiCall.assert_called_once_with(strict=True)

    @mock.patch('sys.stderr', new_callable=six.StringIO)
    def test_handle_remove_pkg_parameter_error(self, stderr):
        tag = 'tag'
        dsttag = {'name': tag, 'id': 1}
        package = 'package'
        args = [tag, package]
        kwargs = {'force': None}

        self.session.getTag.return_value = dsttag
        self.session.listPackages.side_effect = [koji.ParameterError,
                                                 [{'package_name': package, 'package_id': 1}]]
        # Run it and check immediate output
        # args: tag, package
        # expected: success
        handle_remove_pkg(self.options, self.session, args)
        actual = stderr.getvalue()
        expected = ''
        self.assertMultiLineEqual(actual, expected)
        # Finally, assert that things were called as we expected.
        self.activate_session_mock.assert_called_once_with(self.session, self.options)
        self.session.getTag.assert_called_once_with(tag)
        self.session.listPackages.assert_has_calls([
            call(tagID=dsttag['id'], with_owners=False),
            call(tagID=dsttag['id'])
        ])
        self.session.packageListRemove.assert_called_once_with(
            tag, package, **kwargs)
        self.session.multiCall.assert_called_once_with(strict=True)

    @mock.patch('sys.stdout', new_callable=six.StringIO)
    def test_handle_remove_pkg_multi_pkg(self, stdout):
        tag = 'tag'
        dsttag = {'name': tag, 'id': 1}
        packages = ['package1', 'package2', 'package3']
        args = [tag] + packages
        kwargs = {'force': None}

        self.session.getTag.return_value = dsttag
        self.session.listPackages.return_value = [
            {'package_name': 'package1', 'package_id': 1},
            {'package_name': 'package2', 'package_id': 2},
            {'package_name': 'package3', 'package_id': 3},
            {'package_name': 'other_package', 'package_id': 4}
        ]
        # Run it and check immediate output
        # args: tag, package1, package2, package3
        # expected: success
        rv = handle_remove_pkg(self.options, self.session, args)
        actual = stdout.getvalue()
        expected = ''
        self.assertMultiLineEqual(actual, expected)
        # Finally, assert that things were called as we expected.
        self.activate_session_mock.assert_called_once_with(self.session, self.options)
        self.assertEqual(
            self.session.mock_calls, [
                call.getTag(tag),
                call.listPackages(tagID=dsttag['id'], with_owners=False),
                call.packageListRemove(tag, packages[0], **kwargs),
                call.packageListRemove(tag, packages[1], **kwargs),
                call.packageListRemove(tag, packages[2], **kwargs),
                call.multiCall(strict=True)
            ]
        )
        self.assertNotEqual(rv, 1)

    @mock.patch('sys.stdout', new_callable=six.StringIO)
    def test_handle_remove_pkg_force(self, stdout):
        tag = 'tag'
        dsttag = {'name': tag, 'id': 1}
        packages = ['package1', 'package2', 'package3']
        args = ['--force', tag] + packages
        kwargs = {'force': True}

        self.session.getTag.return_value = dsttag
        self.session.listPackages.return_value = [
            {'package_name': 'package1', 'package_id': 1},
            {'package_name': 'package2', 'package_id': 2},
            {'package_name': 'package3', 'package_id': 3},
            {'package_name': 'other_package', 'package_id': 4}
        ]
        # Run it and check immediate output
        # args: --force, tag, package1, package2, package3
        # expected: success
        rv = handle_remove_pkg(self.options, self.session, args)
        actual = stdout.getvalue()
        expected = ''
        self.assertMultiLineEqual(actual, expected)
        # Finally, assert that things were called as we expected.
        self.activate_session_mock.assert_called_once_with(self.session, self.options)
        self.assertEqual(
            self.session.mock_calls, [
                call.getTag(tag),
                call.listPackages(tagID=dsttag['id'], with_owners=False),
                call.packageListRemove(tag, packages[0], **kwargs),
                call.packageListRemove(tag, packages[1], **kwargs),
                call.packageListRemove(tag, packages[2], **kwargs),
                call.multiCall(strict=True)
            ]
        )
        self.assertNotEqual(rv, 1)

    def test_handle_remove_pkg_no_package(self):
        tag = 'tag'
        dsttag = {'name': tag, 'id': 1}
        packages = ['package1', 'package2', 'package3']
        arguments = [tag] + packages

        self.session.getTag.return_value = dsttag
        self.session.listPackages.return_value = [
            {'package_name': 'package1', 'package_id': 1},
            {'package_name': 'package3', 'package_id': 3},
            {'package_name': 'other_package', 'package_id': 4}]
        # Run it and check immediate output
        # args: tag, package1, package2, package3
        # expected: failed: can not find package2 under tag
        self.assert_system_exit(
            handle_remove_pkg,
            self.options, self.session, arguments,
            stderr='Package package2 is not in tag tag\n',
            stdout='',
            activate_session=None,
            exit_code=1)
        # Finally, assert that things were called as we expected.
        self.activate_session_mock.assert_called_once_with(self.session, self.options)
        self.session.getTag.assert_called_once_with(tag)
        self.session.listPackages.assert_called_once_with(tagID=dsttag['id'], with_owners=False)
        self.session.packageListRemove.assert_not_called()
        self.session.multiCall.assert_not_called()

    def test_handle_remove_pkg_tag_no_exists(self):
        tag = 'tag'
        dsttag = None
        packages = ['package1', 'package2', 'package3']
        arguments = [tag] + packages

        self.session.getTag.return_value = dsttag
        # Run it and check immediate output
        # args: tag, package1, package2, package3
        # expected: failed: tag does not exist
        self.assert_system_exit(
            handle_remove_pkg,
            self.options, self.session, arguments,
            stderr='No such tag: %s\n' % tag,
            stdout='',
            activate_session=None,
            exit_code=1)
        # Finally, assert that things were called as we expected.
        self.activate_session_mock.assert_called_once_with(self.session, self.options)
        self.session.getTag.assert_called_once_with(tag)
        self.session.listPackages.assert_not_called()
        self.session.packageListRemove.assert_not_called()

    def test_handle_remove_pkg_without_args(self):
        arguments = []
        # Run it and check immediate output
        self.assert_system_exit(
            handle_remove_pkg,
            self.options, self.session, arguments,
            stderr=self.format_error_message('Please specify a tag and at least one package'),
            stdout='',
            activate_session=None,
            exit_code=2)

        # Finally, assert that things were called as we expected.
        self.activate_session_mock.assert_not_called()
        self.session.getTag.assert_not_called()
        self.session.listPackages.assert_not_called()
        self.session.packageListRemove.assert_not_called()

    def test_handle_remove_pkg_help(self):
        self.assert_help(
            handle_remove_pkg,
            """Usage: %s remove-pkg [options] <tag> <package> [<package> ...]
(Specify the --help global option for a list of other help options)

Options:
  -h, --help  show this help message and exit
  --force     Override blocks if necessary
""" % self.progname)


if __name__ == '__main__':
    unittest.main()
