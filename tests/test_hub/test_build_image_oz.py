import unittest
import koji
import kojihub
import mock


class TestBuildImageOz(unittest.TestCase):

    def setUp(self):
        self.context = mock.patch('kojihub.context').start()
        self.exports = kojihub.RootExports()
        self.context.session.assertPerm = mock.MagicMock()
        self.context.session.hasPerm = mock.MagicMock()
        self.parse_arches = mock.patch('koji.parse_arches').start()
        self.name = 'image-name'
        self.version = 'test-version'
        self.arches = ['x86_64', 'i386']
        self.target = 'test-target'
        self.inst_tree = 'test-tree'

    def tearDown(self):
        mock.patch.stopall()

    def test_name_wrong_type(self):
        name = ['image-name']
        with self.assertRaises(koji.ParameterError) as cm:
            self.exports.buildImageOz(name, self.version, self.arches, self.target, self.inst_tree)
        self.assertEqual(f"Invalid type for value '{name}': {type(name)}", str(cm.exception))

    def test_inst_tree_wrong_type(self):
        inst_tree = ['test-tree']
        with self.assertRaises(koji.ParameterError) as cm:
            self.exports.buildImageOz(self.name, self.version, self.arches, self.target, inst_tree)
        self.assertEqual(f"Invalid type for value '{inst_tree}': {type(inst_tree)}",
                         str(cm.exception))

    def test_version_wrong_type(self):
        version = ['test-version']
        with self.assertRaises(koji.ParameterError) as cm:
            self.exports.buildImageOz(self.name, version, self.arches, self.target, self.inst_tree)
        self.assertEqual(f"Invalid type for value '{version}': {type(version)}", str(cm.exception))

    def test_priority_without_admin(self):
        priority = -10
        self.context.session.assertPerm.side_effect = None
        self.context.session.hasPerm.return_value = False
        with self.assertRaises(koji.ActionNotAllowed) as cm:
            self.exports.buildImageOz(self.name, self.version, self.arches, self.target,
                                      self.inst_tree, priority=priority)
        self.assertEqual("only admins may create high-priority tasks", str(cm.exception))

    def test_opts_without_expected_keys(self):
        priority = 10
        opts = {}
        self.context.session.assertPerm.side_effect = None
        with self.assertRaises(koji.ActionNotAllowed) as cm:
            self.exports.buildImageOz(self.name, self.version, self.arches, self.target,
                                      self.inst_tree, opts=opts, priority=priority)
        self.assertEqual("Non-scratch builds must provide ksurl", str(cm.exception))
