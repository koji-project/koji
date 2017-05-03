from __future__ import absolute_import
import unittest
import koji
import mock
import six

from . import loadcli
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
        broot_id = 321
        arguments = [task_id]
        options = mock.MagicMock()
        options.full = False
        options.nowait = True
        self.parser.parse_args.return_value = [options, arguments]
        self.session.getAPIVersion.return_value = koji.API_VERSION
        self.session.listBuildroots.return_value = [{'id': 321}]

        # Mock out the xmlrpc server
        self.session.saveFailedTree.return_value = 123

        # Run it and check immediate output
        cli.handle_save_failed_tree(self.options, self.session, self.args)

        # Finally, assert that things were called as we expected.
        activate_session_mock.assert_called_once_with(self.session)
        self.session.listBuildroots.assert_called_once_with(taskID=task_id)
        self.session.saveFailedTree.assert_called_once_with(broot_id, options.full)

    @mock.patch('koji_cli.activate_session')
    def test_handle_save_failed_tree_buildroots(self, activate_session_mock):
        # koji save-failed-tree --buildroot 123456
        broot_id = 321
        arguments = [broot_id]
        options = mock.MagicMock()
        options.full = False
        options.nowait = True
        options.mode = "buildroot"
        self.parser.parse_args.return_value = [options, arguments]
        self.session.getAPIVersion.return_value = koji.API_VERSION
        self.session.listBuildroots.return_value = [{'id': 321}]

        # Mock out the xmlrpc server
        self.session.saveFailedTree.return_value = 123

        # Run it and check immediate output
        cli.handle_save_failed_tree(self.options, self.session, self.args)

        # Finally, assert that things were called as we expected.
        activate_session_mock.assert_called_once_with(self.session)
        self.session.listBuildroots.assert_not_called()
        self.session.saveFailedTree.assert_called_once_with(broot_id, options.full)


    @mock.patch('koji_cli.activate_session')
    def test_handle_save_failed_tree_full(self, activate_session_mock):
        # koji save-failed-tree 123456 --full
        task_id = 123456
        broot_id = 321
        arguments = [task_id]
        options = mock.MagicMock()
        options.full = True
        options.nowait = True
        self.parser.parse_args.return_value = [options, arguments]
        self.session.getAPIVersion.return_value = koji.API_VERSION
        self.session.listBuildroots.return_value = [{'id': 321}]

        # Mock out the xmlrpc server
        self.session.saveFailedTree.return_value = 123

        # Run it and check immediate output
        cli.handle_save_failed_tree(self.options, self.session, self.args)

        # Finally, assert that things were called as we expected.
        activate_session_mock.assert_called_once_with(self.session)
        self.session.listBuildroots.assert_called_once_with(taskID=task_id)
        self.session.saveFailedTree.assert_called_once_with(broot_id, options.full)

    @mock.patch('koji_cli.activate_session')
    @mock.patch('koji_cli.watch_tasks')
    def test_handle_save_failed_tree_wait(self, watch_tasks_mock, activate_session_mock):
        # koji save-failed-tree 123456 --full
        task_id = 123456
        broot_id = 321
        arguments = [task_id]
        options = mock.MagicMock()
        options.full = True
        options.nowait = False
        options.quiet = False
        self.parser.parse_args.return_value = [options, arguments]
        self.session.getAPIVersion.return_value = koji.API_VERSION
        self.session.listBuildroots.return_value = [{'id': 321}]

        # Mock out the xmlrpc server
        spawned_id = 123
        self.session.saveFailedTree.return_value = spawned_id

        # Run it and check immediate output
        cli.handle_save_failed_tree(self.options, self.session, self.args)

        # Finally, assert that things were called as we expected.
        self.session.listBuildroots.assert_called_once_with(taskID=task_id)
        self.session.saveFailedTree.assert_called_once_with(broot_id, options.full)
        activate_session_mock.assert_called_once_with(self.session)
        self.session.logout.assert_called_once_with()
        watch_tasks_mock.assert_called_once_with(self.session, [spawned_id],
                                                 quiet=options.quiet)

    @mock.patch('sys.stdout', new_callable=six.StringIO)
    @mock.patch('koji_cli.activate_session')
    @mock.patch('koji_cli.watch_tasks')
    def test_handle_save_failed_tree_errors(self, watch_tasks_mock, activate_session_mock, stdout):
        # koji save-failed-tree 123 456
        arguments = [123, 456]
        options = mock.MagicMock()
        self.parser.parse_args.return_value = [options, arguments]
        self.parser.error.side_effect = Exception()
        self.session.getAPIVersion.return_value = koji.API_VERSION
        self.session.listBuildroots.return_value = [{'id': 321}]

        self.assertRaises(Exception, cli.handle_save_failed_tree,
                          self.options, self.session, self.args)

        arguments = ["text"]
        self.parser.parse_args.return_value = [options, arguments]
        self.assertRaises(Exception, cli.handle_save_failed_tree, self.options,
                          self.session, self.args)
        cli.logger = mock.MagicMock()

        # plugin not installed
        arguments = [123]
        self.parser.parse_args.return_value = [options, arguments]
        self.session.saveFailedTree.side_effect = koji.GenericError("Invalid method")
        cli.handle_save_failed_tree(self.options, self.session, self.args)
        actual = stdout.getvalue()
        self.assertTrue('The save_failed_tree plugin appears to not be installed' in actual)

        # Task which is not FAILED, disabled in config, wrong owner
        self.session.saveFailedTree.side_effect = koji.PreBuildError('placeholder')
        with self.assertRaises(koji.PreBuildError) as cm:
            cli.handle_save_failed_tree(self.options, self.session, self.args)
        e = cm.exception
        self.assertEqual(e, self.session.saveFailedTree.side_effect)
