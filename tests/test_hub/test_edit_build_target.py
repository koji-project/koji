import unittest

import mock

import koji
import kojihub

QP = kojihub.QueryProcessor


class TestEditBuildTarget(unittest.TestCase):

    def getQuery(self, *args, **kwargs):
        query = QP(*args, **kwargs)
        query.execute = mock.MagicMock()
        query.executeOne = mock.MagicMock()
        query.singleValue = self.query_singleValue
        self.queries.append(query)
        return query

    def setUp(self):
        self.lookup_build_target = mock.patch('kojihub.lookup_build_target').start()
        self.verify_name_internal = mock.patch('kojihub.verify_name_internal').start()
        self.get_tag = mock.patch('kojihub.get_tag').start()
        self.exports = kojihub.RootExports()
        self.target_name = 'build-target'
        self.name = 'build-target-rename'
        self.build_tag = 'tag'
        self.dest_tag = 'dest-tag'
        self.target_info = {'id': 123, 'name': self.target_name}
        self.build_tag_info = {'id': 111, 'name': self.build_tag}
        self.dest_tag_info = {'id': 112, 'name': self.dest_tag}
        self.session = kojihub.context.session = mock.MagicMock()
        self.session.assertPerm = mock.MagicMock()
        self.QueryProcessor = mock.patch('kojihub.QueryProcessor',
                                         side_effect=self.getQuery).start()
        self.queries = []
        self.query_singleValue = mock.MagicMock()

    def tearDown(self):
        mock.patch.stopall()

    def test_non_exist_build_target(self):
        self.verify_name_internal.return_value = None
        self.lookup_build_target.return_value = None
        with self.assertRaises(koji.GenericError) as cm:
            self.exports.editBuildTarget(self.target_name, self.name, self.build_tag,
                                         self.dest_tag)
        self.assertEqual(f"No such build target: {self.target_name}", str(cm.exception))
        self.session.assertPerm.called_once_with('target')
        self.verify_name_internal.called_once_with(name=self.name)
        self.lookup_build_target.called_once_with(self.target_name)

    def test_target_wrong_format(self):
        name = 'build-target-rename+'

        # name is longer as expected
        self.verify_name_internal.side_effect = koji.GenericError
        with self.assertRaises(koji.GenericError):
            self.exports.editBuildTarget(self.target_name, name, self.build_tag, self.dest_tag)

        # not except regex rules
        self.verify_name_internal.side_effect = koji.GenericError
        with self.assertRaises(koji.GenericError):
            self.exports.editBuildTarget(self.target_name, name, self.build_tag, self.dest_tag)

    def test_target_non_exist_build_tag(self):
        self.verify_name_internal.return_value = None
        self.lookup_build_target.return_value = self.target_info
        self.get_tag.return_value = None
        with self.assertRaises(koji.GenericError) as cm:
            self.exports.editBuildTarget(self.target_name, self.name, self.build_tag,
                                         self.dest_tag)
        self.assertEqual(f"build tag '{self.build_tag}' does not exist", str(cm.exception))
        self.session.assertPerm.called_once_with('target')
        self.verify_name_internal.called_once_with(name=self.name)
        self.lookup_build_target.called_once_with(self.target_name)
        self.get_tag.called_once_with(self.build_tag)

    def test_target_non_exist_dest_tag(self):
        self.verify_name_internal.return_value = None
        self.lookup_build_target.return_value = self.target_info
        self.get_tag.side_effect = [self.build_tag_info, None]
        with self.assertRaises(koji.GenericError) as cm:
            self.exports.editBuildTarget(self.target_name, self.name, self.build_tag,
                                         self.dest_tag)
        self.assertEqual(f"destination tag '{self.dest_tag}' does not exist", str(cm.exception))
        self.session.assertPerm.called_once_with('target')
        self.verify_name_internal.called_once_with(name=self.name)
        self.lookup_build_target.called_once_with(self.target_name)
        self.get_tag.has_calls([mock.call(self.build_tag), mock.call(self.dest_tag)])

    def test_target_exists(self):
        self.verify_name_internal.return_value = None
        self.lookup_build_target.return_value = self.target_info
        self.get_tag.side_effect = [self.build_tag_info, self.dest_tag_info]
        self.query_singleValue.return_value = 2
        with self.assertRaises(koji.GenericError) as cm:
            self.exports.editBuildTarget(self.target_name, self.name, self.build_tag,
                                         self.dest_tag)
        self.assertEqual(f'name "{self.name}" is already taken by build target 2',
                         str(cm.exception))
        self.session.assertPerm.called_once_with('target')
        self.verify_name_internal.called_once_with(name=self.name)
        self.lookup_build_target.called_once_with(self.target_name)
        self.get_tag.has_calls([mock.call(self.build_tag), mock.call(self.dest_tag)])
