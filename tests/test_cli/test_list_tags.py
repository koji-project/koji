from __future__ import absolute_import

import mock
from six.moves import StringIO

import koji
from koji_cli.commands import anon_handle_list_tags
from . import utils


class TestListTags(utils.CliTestCase):
    def setUp(self):
        self.maxDiff = None
        self.options = mock.MagicMock()
        self.options.debug = False
        self.session = mock.MagicMock()
        self.session.getAPIVersion.return_value = koji.API_VERSION
        self.ensure_connection = mock.patch('koji_cli.commands.ensure_connection').start()
        self.list_tags_api = [{'arches': '',
                               'id': 455,
                               'locked': False,
                               'maven_include_all': False,
                               'maven_support': False,
                               'name': 'test-tag-1',
                               'perm': None,
                               'perm_id': None},
                              {'arches': '',
                               'id': 456,
                               'locked': True,
                               'maven_include_all': False,
                               'maven_support': False,
                               'name': 'test-tag-2',
                               'perm': 'admin',
                               'perm_id': 1}]
        self.error_format = """Usage: %s list-tags [options] [pattern]
(Specify the --help global option for a list of other help options)

%s: error: {message}
""" % (self.progname, self.progname)

    def test_list_tags_non_exist_package(self):
        pkg = 'test-pkg'
        self.session.getPackage.return_value = None
        arguments = ['--package', pkg]
        self.assert_system_exit(
            anon_handle_list_tags,
            self.options, self.session, arguments,
            stderr=self.format_error_message('No such package: %s' % pkg),
            stdout='',
            activate_session=None,
            exit_code=2)
        self.ensure_connection.assert_called_once_with(self.session, self.options)

    def test_list_tags_non_exist_build(self):
        build = 'test-build'
        self.session.getBuild.return_value = None
        arguments = ['--build', build]
        self.assert_system_exit(
            anon_handle_list_tags,
            self.options, self.session, arguments,
            stderr=self.format_error_message('No such build: %s' % build),
            stdout='',
            activate_session=None,
            exit_code=2)
        self.ensure_connection.assert_called_once_with(self.session, self.options)

    @mock.patch('sys.stdout', new_callable=StringIO)
    def test_list_tags(self, stdout):
        self.session.listTags.return_value = self.list_tags_api
        rv = anon_handle_list_tags(self.options, self.session, [])
        actual = stdout.getvalue()
        expected = 'test-tag-1\ntest-tag-2\n'
        self.assertMultiLineEqual(actual, expected)
        self.assertEqual(rv, None)
        self.session.listTags.assert_called_once_with(build=None, package=None)
        self.ensure_connection.assert_called_once_with(self.session, self.options)

    @mock.patch('sys.stdout', new_callable=StringIO)
    def test_list_tags_show_id_unlocked(self, stdout):
        self.session.listTags.return_value = self.list_tags_api
        rv = anon_handle_list_tags(self.options, self.session,
                                   ['--show-id', '--unlocked'])
        actual = stdout.getvalue()
        expected = 'test-tag-1 [455]\n'
        self.assertMultiLineEqual(actual, expected)
        self.assertEqual(rv, None)
        self.session.listTags.assert_called_once_with(build=None, package=None)
        self.ensure_connection.assert_called_once_with(self.session, self.options)

    @mock.patch('sys.stdout', new_callable=StringIO)
    def test_list_tags_verbose(self, stdout):
        self.session.listTags.return_value = self.list_tags_api
        rv = anon_handle_list_tags(self.options, self.session,
                                   ['--show-id', '--verbose'])
        actual = stdout.getvalue()
        expected = 'test-tag-1 [455]\ntest-tag-2 [456] [LOCKED] [admin perm required]\n'
        self.assertMultiLineEqual(actual, expected)
        self.assertEqual(rv, None)
        self.session.listTags.assert_called_once_with(build=None, package=None)
        self.ensure_connection.assert_called_once_with(self.session, self.options)

    def test_list_tags_help(self):
        self.assert_help(
            anon_handle_list_tags,
            """Usage: %s list-tags [options] [pattern]
(Specify the --help global option for a list of other help options)

Options:
  -h, --help         show this help message and exit
  --show-id          Show tag ids
  --verbose          Show more information
  --unlocked         Only show unlocked tags
  --build=BUILD      Show tags associated with a build
  --package=PACKAGE  Show tags associated with a package
""" % self.progname)
