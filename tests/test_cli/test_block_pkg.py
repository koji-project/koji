from __future__ import absolute_import
try:
    from unittest import mock
    from unittest.mock import call
except ImportError:
    import mock
    from mock import call

import six

from koji_cli.commands import handle_block_pkg
import koji
from . import utils


class TestBlockPkg(utils.CliTestCase):

    def setUp(self):
        # Show long diffs in error output...
        self.maxDiff = None
        self.options = mock.MagicMock()
        self.options.debug = False
        self.session = mock.MagicMock()
        self.session.getAPIVersion.return_value = koji.API_VERSION
        self.activate_session_mock = mock.patch('koji_cli.commands.activate_session').start()
        self.error_format = """Usage: %s block-pkg [options] <tag> <package> [<package> ...]
(Specify the --help global option for a list of other help options)

%s: error: {message}
""" % (self.progname, self.progname)

    def tearDown(self):
        mock.patch.stopall()

    @mock.patch('sys.stdout', new_callable=six.StringIO)
    def test_handle_block_pkg(self, stdout):
        tag = 'tag'
        dsttag = {'name': tag, 'id': 1}
        package = 'package'
        args = [tag, package, '--force']

        self.session.getTag.return_value = dsttag
        self.session.listPackages.return_value = [
            {'package_name': package, 'package_id': 1}]
        # Run it and check immediate output
        # args: tag, package
        # expected: success
        rv = handle_block_pkg(self.options, self.session, args)
        actual = stdout.getvalue()
        expected = ''
        self.assertMultiLineEqual(actual, expected)
        # Finally, assert that things were called as we expected.
        self.activate_session_mock.assert_called_once_with(self.session, self.options)
        self.session.getTag.assert_called_once_with(tag)
        self.session.listPackages.assert_called_once_with(
            tagID=dsttag['id'], inherited=True, with_owners=False)
        self.session.packageListBlock.assert_called_once_with(
            tag, package, force=True)
        self.session.multiCall.assert_called_once_with(strict=True)
        self.assertFalse(rv)

    @mock.patch('sys.stdout', new_callable=six.StringIO)
    def test_handle_block_pkg_parameter_error(self, stdout):
        tag = 'tag'
        dsttag = {'name': tag, 'id': 1}
        package = 'package'
        args = [tag, package, '--force']

        self.session.getTag.return_value = dsttag
        self.session.listPackages.side_effect = [koji.ParameterError,
                                                 [{'package_name': package, 'package_id': 1}]]
        # Run it and check immediate output
        # args: tag, package
        # expected: success
        rv = handle_block_pkg(self.options, self.session, args)
        actual = stdout.getvalue()
        expected = ''
        self.assertMultiLineEqual(actual, expected)
        # Finally, assert that things were called as we expected.
        self.activate_session_mock.assert_called_once_with(self.session, self.options)
        self.session.getTag.assert_called_once_with(tag)
        self.session.listPackages.assert_has_calls([
            call(tagID=dsttag['id'], inherited=True, with_owners=False),
            call(tagID=dsttag['id'], inherited=True)
        ])
        self.session.packageListBlock.assert_called_once_with(
            tag, package, force=True)
        self.session.multiCall.assert_called_once_with(strict=True)
        self.assertFalse(rv)

    @mock.patch('sys.stdout', new_callable=six.StringIO)
    def test_handle_block_pkg_multi_pkg(self, stdout):
        tag = 'tag'
        dsttag = {'name': tag, 'id': 1}
        packages = ['package1', 'package2', 'package3']
        args = [tag] + packages

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
        rv = handle_block_pkg(self.options, self.session, args)
        actual = stdout.getvalue()
        expected = ''
        self.assertMultiLineEqual(actual, expected)
        # Finally, assert that things were called as we expected.
        self.activate_session_mock.assert_called_once_with(self.session, self.options)
        self.assertEqual(
            self.session.mock_calls, [
                call.getTag(tag),
                call.listPackages(tagID=dsttag['id'], inherited=True, with_owners=False),
                call.packageListBlock(tag, packages[0]),
                call.packageListBlock(tag, packages[1]),
                call.packageListBlock(tag, packages[2]),
                call.multiCall(strict=True)])
        self.assertNotEqual(rv, 1)

    def test_handle_block_pkg_no_package(self):
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
            handle_block_pkg,
            self.options, self.session, arguments,
            stderr='Package package2 doesn\'t exist in tag tag\n',
            stdout='',
            activate_session=None,
            exit_code=1)
        # Finally, assert that things were called as we expected.
        self.activate_session_mock.assert_called_once_with(self.session, self.options)
        self.session.getTag.assert_called_once_with(tag)
        self.session.listPackages.assert_called_once_with(
            tagID=dsttag['id'], inherited=True, with_owners=False)
        self.session.packageListBlock.assert_not_called()
        self.session.multiCall.assert_not_called()

    def test_handle_block_pkg_tag_no_exists(self):
        tag = 'tag'
        dsttag = None
        packages = ['package1', 'package2', 'package3']
        arguments = [tag] + packages

        self.session.getTag.return_value = dsttag
        # Run it and check immediate output
        # args: tag, package1, package2, package3
        # expected: failed: tag does not exist
        self.assert_system_exit(
            handle_block_pkg,
            self.options, self.session, arguments,
            stderr='No such tag: %s\n' % tag,
            stdout='',
            activate_session=None,
            exit_code=1)
        # Finally, assert that things were called as we expected.
        self.activate_session_mock.assert_called_once_with(self.session, self.options)
        self.session.getTag.assert_called_once_with(tag)
        self.session.listPackages.assert_not_called()
        self.session.packageListBlock.assert_not_called()

    def test_handle_block_pkg_without_args(self):
        arguments = []
        # Run it and check immediate output
        self.assert_system_exit(
            handle_block_pkg,
            self.options, self.session, arguments,
            stderr=self.format_error_message('Please specify a tag and at least one package'),
            stdout='',
            activate_session=None,
            exit_code=2)

        # Finally, assert that things were called as we expected.
        self.activate_session_mock.assert_not_called()
        self.session.getTag.assert_not_called()
        self.session.listPackages.assert_not_called()
        self.session.packageListBlock.assert_not_called()

    def test_handle_block_pkg_help(self):
        self.assert_help(
            handle_block_pkg,
            """Usage: %s block-pkg [options] <tag> <package> [<package> ...]
(Specify the --help global option for a list of other help options)

Options:
  -h, --help  show this help message and exit
  --force     Override blocks and owner if necessary
""" % self.progname)
