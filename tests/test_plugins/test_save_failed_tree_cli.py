from __future__ import absolute_import
import mock
import six
try:
    import unittest2 as unittest
except ImportError:
    import unittest

import koji

from . import load_plugin
save_failed_tree = load_plugin.load_plugin('cli', 'save_failed_tree')


class TestSaveFailedTree(unittest.TestCase):
    def setUp(self):
        self.session = mock.MagicMock()
        self.args = mock.MagicMock()
        self.parser = mock.MagicMock()
        save_failed_tree.activate_session = mock.MagicMock()
        save_failed_tree.OptionParser = mock.MagicMock()
        save_failed_tree.watch_tasks = mock.MagicMock()
        self.parser = save_failed_tree.OptionParser.return_value

    # Show long diffs in error output...
    maxDiff = None

    def test_handle_save_failed_tree_simple(self ):
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
        save_failed_tree.handle_save_failed_tree(options, self.session, self.args)

        # Finally, assert that things were called as we expected.
        save_failed_tree.activate_session.assert_called_once_with(self.session, options)
        self.session.listBuildroots.assert_called_once_with(taskID=task_id)
        self.session.saveFailedTree.assert_called_once_with(broot_id, options.full)

    def test_handle_save_failed_tree_buildroots(self):
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
        save_failed_tree.handle_save_failed_tree(options, self.session, self.args)

        # Finally, assert that things were called as we expected.
        save_failed_tree.activate_session.assert_called_once_with(self.session, options)
        self.session.listBuildroots.assert_not_called()
        self.session.saveFailedTree.assert_called_once_with(broot_id, options.full)


    def test_handle_save_failed_tree_full(self):
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
        save_failed_tree.handle_save_failed_tree(options, self.session, self.args)

        # Finally, assert that things were called as we expected.
        save_failed_tree.activate_session.assert_called_once_with(self.session, options)
        self.session.listBuildroots.assert_called_once_with(taskID=task_id)
        self.session.saveFailedTree.assert_called_once_with(broot_id, options.full)

    def test_handle_save_failed_tree_wait(self):
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
        save_failed_tree.handle_save_failed_tree(options, self.session, self.args)

        # Finally, assert that things were called as we expected.
        self.session.listBuildroots.assert_called_once_with(taskID=task_id)
        self.session.saveFailedTree.assert_called_once_with(broot_id, options.full)
        save_failed_tree.activate_session.assert_called_once_with(self.session, options)
        self.session.logout.assert_called_once_with()
        save_failed_tree.watch_tasks.assert_called_once_with(self.session, [spawned_id],
                                                             poll_interval=options.poll_interval,
                                                             quiet=options.quiet)

    @mock.patch('sys.stdout', new_callable=six.StringIO)
    def test_handle_save_failed_tree_errors(self, stdout):
        # koji save-failed-tree 123 456
        arguments = [123, 456]
        options = mock.MagicMock()
        self.parser.parse_args.return_value = [options, arguments]
        self.parser.error.side_effect = Exception()
        self.session.getAPIVersion.return_value = koji.API_VERSION
        self.session.listBuildroots.return_value = [{'id': 321}]

        self.assertRaises(Exception, save_failed_tree.handle_save_failed_tree,
                          options, self.session, self.args)

        arguments = ["text"]
        self.parser.parse_args.return_value = [options, arguments]
        self.assertRaises(Exception, save_failed_tree.handle_save_failed_tree, options,
                          self.session, self.args)
        save_failed_tree.logger = mock.MagicMock()

        # plugin not installed
        arguments = [123]
        self.parser.parse_args.return_value = [options, arguments]
        self.session.saveFailedTree.side_effect = koji.GenericError("Invalid method")
        save_failed_tree.handle_save_failed_tree(options, self.session, self.args)
        actual = stdout.getvalue()
        self.assertTrue('The save_failed_tree plugin appears to not be installed' in actual)

        # Task which is not FAILED, disabled in config, wrong owner
        self.session.saveFailedTree.side_effect = koji.PreBuildError('placeholder')
        with self.assertRaises(koji.PreBuildError) as cm:
            save_failed_tree.handle_save_failed_tree(options, self.session, self.args)
        e = cm.exception
        self.assertEqual(e, self.session.saveFailedTree.side_effect)
