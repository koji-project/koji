import unittest
import koji
import kojihub
from unittest import mock


class TestBuildImage(unittest.TestCase):

    def setUp(self):
        self.context = mock.patch('kojihub.kojihub.context').start()
        self.exports = kojihub.RootExports()
        self.context.session.assertPerm = mock.MagicMock()
        self.context.session.hasPerm = mock.MagicMock()
        self.make_task = mock.patch('kojihub.kojihub.make_task').start()
        self.mock_parse_arches = mock.patch('koji.parse_arches').start()
        self.name = 'image-name'
        self.version = 'test-version'
        self.arch = 'x86_64'
        self.target = 'test-target'
        self.ksfile = 'test-ksfile'
        self.image_type = 'livecd'

    def tearDown(self):
        mock.patch.stopall()

    def test_img_type_not_supported(self):
        image_type = 'test-type'
        with self.assertRaises(koji.GenericError) as cm:
            self.exports.buildImage(self.name, self.version, self.arch, self.target,
                                    self.ksfile, image_type)
        self.assertEqual(f"Unrecognized image type: {image_type}", str(cm.exception))

    def test_name_wrong_type(self):
        name = ['test-name']
        with self.assertRaises(koji.GenericError) as cm:
            self.exports.buildImage(name, self.version, self.arch, self.target, self.ksfile,
                                    self.image_type)
        self.assertEqual(f"Invalid type for value '{name}': {type(name)}, "
                         f"expected type <class 'str'>", str(cm.exception))

    def test_version_wrong_type(self):
        version = ['test-version']
        with self.assertRaises(koji.GenericError) as cm:
            self.exports.buildImage(self.name, version, self.arch, self.target, self.ksfile,
                                    self.image_type)
        self.assertEqual(f"Invalid type for value '{version}': {type(version)}, "
                         f"expected type <class 'str'>", str(cm.exception))

    def test_ksfile_wrong_type(self):
        ksfile = ['test-ksfile']
        with self.assertRaises(koji.GenericError) as cm:
            self.exports.buildImage(self.name, self.version, self.arch, self.target, ksfile,
                                    self.image_type)
        self.assertEqual(f"Invalid type for value '{ksfile}': {type(ksfile)}, "
                         f"expected type <class 'str'>", str(cm.exception))

    def test_priority_without_admin(self):
        priority = -10
        image_type = 'livemedia'
        self.context.session.assertPerm.side_effect = None
        self.context.session.hasPerm.return_value = False
        with self.assertRaises(koji.ActionNotAllowed) as cm:
            self.exports.buildImage(self.name, self.version, self.arch, self.target, self.ksfile,
                                    image_type, priority=priority)
        self.assertEqual("only admins may create high-priority tasks", str(cm.exception))

    def test_valid(self):
        priority = 10
        self.context.session.assertPerm.side_effect = None
        self.make_task.return_value = 123
        self.exports.buildImage(self.name, self.version, self.arch, self.target, self.ksfile,
                                self.image_type, priority=priority)
