import StringIO
import unittest
import koji
import mock

import loadcli
cli = loadcli.cli


class TestSaveFailedTree(unittest.TestCase):
    def setUp(self):
        self.options = mock.MagicMock()
        self.session = mock.MagicMock()
        self.args = mock.MagicMock()
        self.original_parser = cli.OptionParser
        cli.OptionParser = mock.MagicMock()
        self.parser = cli.OptionParser.return_value
        cli.options = self.options  # globals!!!

    def tearDown(self):
        cli.OptionParser = self.original_parser

    # Show long diffs in error output...
    maxDiff = None

    @mock.patch('koji_cli.activate_session')
    def test_handle_save_failed_tree_simple(self, activate_session_mock):
        # koji save-failed-tree 123456
        task_id = 123456
        arguments = [task_id]
        options = mock.MagicMock()
        options.full = False
        options.nowait = True
        self.parser.parse_args.return_value = [options, arguments]
        self.session.getAPIVersion.return_value = koji.API_VERSION

        # Mock out the xmlrpc server
        self.session.saveFailedTree.return_value = 123

        # Run it and check immediate output
        cli.handle_save_failed_tree(self.options, self.session, self.args)

        # Finally, assert that things were called as we expected.
        activate_session_mock.assert_called_once_with(self.session)
        self.session.saveFailedTree.assert_called_once_with(task_id, options.full)

    @mock.patch('koji_cli.activate_session')
    def test_handle_save_failed_tree_full(self, activate_session_mock):
        # koji save-failed-tree 123456 --full
        task_id = 123456
        arguments = [task_id]
        options = mock.MagicMock()
        options.full = True
        options.nowait = True
        self.parser.parse_args.return_value = [options, arguments]
        self.session.getAPIVersion.return_value = koji.API_VERSION

        # Mock out the xmlrpc server
        self.session.saveFailedTree.return_value = 123

        # Run it and check immediate output
        cli.handle_save_failed_tree(self.options, self.session, self.args)

        # Finally, assert that things were called as we expected.
        activate_session_mock.assert_called_once_with(self.session)
        self.session.saveFailedTree.assert_called_once_with(task_id, options.full)

    @mock.patch('koji_cli.activate_session')
    @mock.patch('koji_cli.watch_tasks')
    def test_handle_save_failed_tree_wait(self, watch_tasks_mock, activate_session_mock):
        # koji save-failed-tree 123456 --full
        task_id = 123456
        arguments = [task_id]
        options = mock.MagicMock()
        options.full = True
        options.nowait = False
        options.quiet = False
        self.parser.parse_args.return_value = [options, arguments]
        self.session.getAPIVersion.return_value = koji.API_VERSION

        # Mock out the xmlrpc server
        spawned_id = 123
        self.session.saveFailedTree.return_value = spawned_id

        # Run it and check immediate output
        cli.handle_save_failed_tree(self.options, self.session, self.args)

        # Finally, assert that things were called as we expected.
        self.session.saveFailedTree.assert_called_once_with(task_id, options.full)
        activate_session_mock.assert_called_once_with(self.session)
        self.session.logout.assert_called_once_with()
        watch_tasks_mock.assert_called_once_with(self.session, [spawned_id],
                                                 quiet=options.quiet)

    @mock.patch('sys.stdout', new_callable=StringIO.StringIO)
    @mock.patch('koji_cli.activate_session')
    @mock.patch('koji_cli.watch_tasks')
    def test_handle_save_failed_tree_errors(self, watch_tasks_mock, activate_session_mock, stdout):
        # koji save-failed-tree 123 456
        arguments = [123, 456]
        options = mock.MagicMock()
        self.parser.parse_args.return_value = [options, arguments]
        self.parser.error.side_effect = Exception()
        self.session.getAPIVersion.return_value = koji.API_VERSION

        self.assertRaises(Exception, cli.handle_save_failed_tree,
                          self.options, self.session, self.args)

        arguments = ["text"]
        self.parser.parse_args.return_value = [options, arguments]
        self.assertRaises(Exception, cli.handle_save_failed_tree, self.options,
                          self.session, self.args)

        # plugin not installed
        arguments = [123]
        self.parser.parse_args.return_value = [options, arguments]
        self.session.saveFailedTree.side_effect = koji.GenericError("Invalid method")
        self.assertRaises(koji.GenericError, cli.handle_save_failed_tree,
                          self.options, self.session, self.args)

        # something wrong happened in task
        stdout.seek(0)
        stdout.truncate()
        self.session.saveFailedTree.return_value = 'xyz'
        self.session.saveFailedTree.side_effect = None
        cli.handle_save_failed_tree(self.options, self.session, self.args)
        actual = stdout.getvalue()
        self.assertEqual(actual, 'Error: xyz\n')
