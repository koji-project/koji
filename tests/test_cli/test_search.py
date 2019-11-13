from __future__ import absolute_import
import mock
import six
try:
    import unittest2 as unittest
except ImportError:
    import unittest

from koji_cli.commands import anon_handle_search
from . import utils


class TestSearch(utils.CliTestCase):

    # Show long diffs in error output...
    maxDiff = None

    def setUp(self):
        self.error_format = """Usage: %s search [options] <search_type> <pattern>
Available search types: package, build, tag, target, user, host, rpm, maven, win
(Specify the --help global option for a list of other help options)

%s: error: {message}
""" % (self.progname, self.progname)

    @mock.patch('sys.stdout', new_callable=six.StringIO)
    def test_anon_handle_search(
            self,
            stdout):
        """Test anon_handle_search function"""
        session = mock.MagicMock()
        options = mock.MagicMock()
        s_type, s_pattern = 'build', 'fedora'
        arguments = [s_type, s_pattern]

        search_results = [
            {'id': 166, 'name': 'f25'},
            {'id': 177, 'name': 'f26'},
            {'id': 202, 'name': 'f27'}
        ]

        session.search.return_value = search_results
        expected = ''.join('%s\n' % x['name'] for x in search_results)

        # Case 1. normal search
        anon_handle_search(options, session, arguments)
        self.assert_console_message(stdout, expected)
        session.search.assert_called_with(s_pattern, s_type, 'glob')

        # Case 2. exact match
        anon_handle_search(options, session, arguments + ['--exact'])
        self.assert_console_message(stdout, expected)
        session.search.assert_called_with(s_pattern, s_type, 'exact')

        # Case 3. regex match
        anon_handle_search(options, session, arguments + ['-r'])
        self.assert_console_message(stdout, expected)
        session.search.assert_called_with(s_pattern, s_type, 'regexp')

    def test_anon_handle_search_argument_error(self):
        """Test anon_handle_search function with argument error"""
        s_type, s_patt = 'unknown', 'unknown'
        cases = [
            {'argument': [], 'error': 'Please specify search type'},
            {'argument': [s_type], 'error': 'Please specify search pattern'},
            {'argument': [s_type, s_patt],
             'error': 'Unknown search type: %s' % s_type}
        ]

        for case in cases:
            expected = self.format_error_message(case['error'])
            self.assert_system_exit(
                anon_handle_search,
                mock.MagicMock(),
                mock.MagicMock(),
                case['argument'],
                stderr=expected,
                activate_session=None)

    def test_anon_handle_search_help(self):
        self.assert_help(
            anon_handle_search,
            """Usage: %s search [options] <search_type> <pattern>
Available search types: package, build, tag, target, user, host, rpm, maven, win
(Specify the --help global option for a list of other help options)

Options:
  -h, --help   show this help message and exit
  -r, --regex  treat pattern as regex
  --exact      exact matches only
""" % self.progname)


if __name__ == '__main__':
    unittest.main()
