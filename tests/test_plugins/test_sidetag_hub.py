from __future__ import absolute_import
import mock
import unittest

import koji
import kojihub
import sidetag_hub


class TestCreateSideTagHub(unittest.TestCase):
    def setUp(self):
        self.QueryProcessor = mock.patch('sidetag_hub.QueryProcessor',
                                         side_effect=self.getQuery).start()
        self.queries = []
        self.context = mock.patch('sidetag_hub.context').start()
        self.get_user = mock.patch('sidetag_hub.get_user').start()
        self.get_tag = mock.patch('sidetag_hub.get_tag').start()
        self._create_tag = mock.patch('sidetag_hub._create_tag').start()
        self._create_build_target = mock.patch('sidetag_hub._create_build_target').start()
        self.nextval = mock.patch('sidetag_hub.nextval').start()
        self.assert_policy = mock.patch('sidetag_hub.assert_policy').start()
        self.query_executeOne = mock.MagicMock()
        self.basetag = {
            'id': 32,
            'name': 'base_tag',
            'arches': ['x86_64', 'i686']
        }
        self.user = {
            'id': 23,
            'name': 'username',
        }

    def tearDown(self):
        mock.patch.stopall()

    def getQuery(self, *args, **kwargs):
        query = kojihub.QueryProcessor(*args, **kwargs)
        query.execute = mock.MagicMock()
        query.executeOne = self.query_executeOne
        self.queries.append(query)
        return query

    def test_createsidetag_basic(self):
        self.query_executeOne.return_value = {'user_tags': 0}
        sidetag_name = 'base_tag-side-12346'
        self.context.session.assertLogin = mock.MagicMock()
        self.context.session.user_id = 23
        self.get_user.return_value = self.user
        self.get_tag.return_value = self.basetag
        self.nextval.return_value = 12345
        self._create_tag.return_value = 12346

        ret = sidetag_hub.createSideTag('base_tag')
        self.assertEqual(ret, {'name': sidetag_name, 'id': 12346})

        self.get_user.assert_called_once_with(23, strict=True)
        self.get_tag.assert_called_once_with(self.basetag['name'], strict=True)
        self.assert_policy.assert_called_once_with(
            "sidetag", {"tag": self.basetag["id"], "number_of_tags": 0}
        )
        self.nextval.assert_called_once_with('tag_id_seq')
        self._create_tag.assert_called_once_with(
            sidetag_name,
            parent=self.basetag['id'],
            arches=self.basetag['arches'],
            extra={
                "sidetag": True,
                "sidetag_user": self.user["name"],
                "sidetag_user_id": self.user["id"],
            })
        self._create_build_target.assert_called_once_with(sidetag_name, 12346, 12346)

    def test_createsidetag_template_valid_and_debuginfo(self):
        self.query_executeOne.return_value = {'user_tags': 0}
        sidetag_name = 'base_tag-sidetag-12346-suffix'
        self.context.session.assertLogin = mock.MagicMock()
        self.context.session.user_id = 23
        self.get_user.return_value = self.user
        self.get_tag.return_value = self.basetag
        self.nextval.return_value = 12345
        self._create_tag.return_value = 12346
        sidetag_hub.ALLOWED_SUFFIXES = ['suffix', 'another']
        sidetag_hub.NAME_TEMPLATE = '{basetag}-sidetag-{tag_id}'

        ret = sidetag_hub.createSideTag('base_tag', debuginfo=True, suffix='suffix')
        self.assertEqual(ret, {'name': sidetag_name, 'id': 12346})

    def test_createsidetag_template_forbidden_suffix(self):
        sidetag_hub.ALLOWED_SUFFIXES = ['suffix', 'another']
        frbd_suffix = 'forbidden_suffix'
        with self.assertRaises(koji.GenericError) as ex:
            sidetag_hub.createSideTag('base_tag', suffix=frbd_suffix)
        self.assertEqual("%s suffix is not allowed for sidetag" % frbd_suffix, str(ex.exception))
        self.get_user.assert_not_called()
        self.get_tag.assert_not_called()
        self.assert_policy.assert_not_called()
        self.nextval.assert_not_called()
        self._create_tag.assert_not_called()
        self._create_build_target.assert_not_called()

    def test_createsidetag_unknown_db_error(self):
        self.query_executeOne.return_value = None
        self.context.session.assertLogin = mock.MagicMock()
        self.context.session.user_id = 23
        self.get_user.return_value = self.user
        self.get_tag.return_value = self.basetag
        sidetag_hub.ALLOWED_SUFFIXES = ['suffix', 'another']
        sidetag_hub.NAME_TEMPLATE = '{basetag}-sidetag-{tag_id}'

        with self.assertRaises(koji.GenericError) as ex:
            sidetag_hub.createSideTag('base_tag', suffix='suffix')
        self.assertEqual("Unknown db error", str(ex.exception))
        self.get_user.assert_called_once_with(23, strict=True)
        self.get_tag.assert_called_once_with(self.basetag['name'], strict=True)
        self.assert_policy.assert_not_called()
        self.nextval.assert_not_called()
        self._create_tag.assert_not_called()
        self._create_build_target.assert_not_called()


class TestRemoveSideTagHub(unittest.TestCase):
    def setUp(self):
        self.context = mock.patch('sidetag_hub.context').start()
        self.context.session.hasPerm = mock.MagicMock()
        self.context.session.hasPerm.return_value = False
        self.get_user = mock.patch('sidetag_hub.get_user').start()
        self.get_tag = mock.patch('sidetag_hub.get_tag').start()
        self.get_build_target = mock.patch('sidetag_hub.get_build_target').start()
        self._delete_build_target = mock.patch('sidetag_hub._delete_build_target').start()
        self._delete_tag = mock.patch('sidetag_hub._delete_tag').start()
        self.sidetag = 'base_tag-sidetag-12346-suffix'
        self.user_info = {
            'id': 23,
            'name': 'testuser',
        }
        self.sidetag_info = {
            'arches': '',
            'extra': {'sidetag': True, 'sidetag_user': 'testuser', 'sidetag_user_id': 23},
            'id': 96,
            'name': 'base_tag-sidetag-12346-suffix'
        }
        self.target_info = {
            'build_tag': 96,
            'dest_tag': 96,
            'id': 153,
        }

    def tearDown(self):
        mock.patch.stopall()

    def test_remove_sidetag_not_sidetag(self):
        tag_info = {
            'arches': '',
            'extra': {},
            'id': 96,
            'name': 'base_tag'
        }
        self.context.session.assertLogin = mock.MagicMock()
        self.context.session.user_id = 23
        self.get_user.return_value = self.user_info
        self.get_tag.return_value = tag_info
        with self.assertRaises(koji.GenericError) as ex:
            sidetag_hub.removeSideTag('base-tag')
        self.assertEqual("Not a sidetag: %(name)s" % tag_info, str(ex.exception))

        self.get_user.assert_called_once_with(23, strict=True)
        self.get_tag.assert_called_once_with('base-tag', strict=True)
        self.get_build_target.assert_not_called()
        self._delete_build_target.assert_not_called()
        self._delete_tag.assert_not_called()

    def test_remove_sidetag_not_owner_sidetag(self):
        sidetag_info = {
            'arches': '',
            'extra': {'sidetag': True, 'sidetag_user': 'testuser-2', 'sidetag_user_id': 2},
            'id': 96,
            'name': 'base_tag-sidetag-12346-suffix'
        }
        self.context.session.assertLogin = mock.MagicMock()
        self.context.session.user_id = 23
        self.get_user.return_value = self.user_info
        self.get_tag.return_value = sidetag_info
        with self.assertRaises(koji.GenericError) as ex:
            sidetag_hub.removeSideTag(self.sidetag)
        self.assertEqual("This is not your sidetag", str(ex.exception))

        self.get_user.assert_called_once_with(23, strict=True)
        self.get_tag.assert_called_once_with(self.sidetag, strict=True)
        self.get_build_target.assert_not_called()
        self._delete_build_target.assert_not_called()
        self._delete_tag.assert_not_called()

    def test_remove_sidetag_wrong_target(self):
        self.context.session.assertLogin = mock.MagicMock()
        self.context.session.user_id = 23
        self.get_user.return_value = self.user_info
        self.get_tag.return_value = self.sidetag_info
        self.get_build_target.return_value = None
        with self.assertRaises(koji.GenericError) as ex:
            sidetag_hub.removeSideTag(self.sidetag)
        self.assertEqual("Target is missing for sidetag", str(ex.exception))

        self.get_user.assert_called_once_with(23, strict=True)
        self.get_tag.assert_called_once_with(self.sidetag, strict=True)
        self.get_build_target.assert_called_once_with(self.sidetag_info['name'])
        self._delete_build_target.assert_not_called()
        self._delete_tag.assert_not_called()

    def test_remove_sidetag_target_not_match_sidetag(self):
        target_info = {
            'build_tag': 85,
            'dest_tag': 85,
        }
        self.context.session.assertLogin = mock.MagicMock()
        self.context.session.user_id = 23
        self.get_user.return_value = self.user_info
        self.get_tag.return_value = self.sidetag_info
        self.get_build_target.return_value = target_info
        with self.assertRaises(koji.GenericError) as ex:
            sidetag_hub.removeSideTag(self.sidetag)
        self.assertEqual("Target does not match sidetag", str(ex.exception))

        self.get_user.assert_called_once_with(23, strict=True)
        self.get_tag.assert_called_once_with(self.sidetag, strict=True)
        self.get_build_target.assert_called_once_with(self.sidetag_info['name'])
        self._delete_build_target.assert_not_called()
        self._delete_tag.assert_not_called()

    def test_remove_sidetag_valid(self):
        self.context.session.assertLogin = mock.MagicMock()
        self.context.session.user_id = 23
        self.get_user.return_value = self.user_info
        self.get_tag.return_value = self.sidetag_info
        self.get_build_target.return_value = self.target_info
        self._delete_build_target.return_value = None
        self._delete_tag.return_value = None
        rv = sidetag_hub.removeSideTag(self.sidetag)
        self.assertEqual(rv, None)

        self.get_user.assert_called_once_with(23, strict=True)
        self.get_tag.assert_called_once_with(self.sidetag, strict=True)
        self.get_build_target.assert_called_once_with(self.sidetag_info['name'])
        self._delete_build_target.assert_called_once_with(self.target_info['id'])
        self._delete_tag.assert_called_once_with(self.sidetag_info['id'])


class TestListSideTagsHub(unittest.TestCase):
    def setUp(self):
        self.get_user = mock.patch('sidetag_hub.get_user').start()
        self.get_tag = mock.patch('sidetag_hub.get_tag').start()
        self.basetag = 'test_tag'
        self.username = 'test-user'
        self.user_info = {
            'id': 23,
            'name': 'username',
        }
        self.basetag_info = {
            'id': 32,
            'name': 'base_tag',
            'arches': ['x86_64', 'i686']
        }
        self.QueryProcessor = mock.patch('sidetag_hub.QueryProcessor',
                                         side_effect=self.getQuery).start()
        self.queries = []

    def tearDown(self):
        mock.patch.stopall()

    def getQuery(self, *args, **kwargs):
        query = kojihub.QueryProcessor(*args, **kwargs)
        query.execute = mock.MagicMock()
        self.queries.append(query)
        return query

    def test_list_sidetags_default(self):
        sidetag_hub.listSideTags()

        self.assertEqual(len(self.queries), 1)
        query = self.queries[0]
        self.assertEqual(query.tables, ['tag'])
        self.assertEqual(query.joins, [
            "LEFT JOIN tag_extra AS te1 ON tag.id = te1.tag_id",
            "LEFT JOIN tag_extra AS te2 ON tag.id = te2.tag_id",
            "LEFT JOIN users ON CAST(te2.value AS INTEGER) = users.id", ])
        self.assertEqual(query.clauses, [
            "te1.active IS TRUE", "te1.key = 'sidetag'", "te1.value = 'true'",
            "te2.active IS TRUE", "te2.key = 'sidetag_user_id'"
        ])
        self.assertEqual(query.values, {"basetag_id": None, "user_id": None})

        self.get_tag.assert_not_called()
        self.get_user.assert_not_called()

    def test_list_sidetags_basetag(self):
        self.get_tag.return_value = self.basetag_info
        sidetag_hub.listSideTags(basetag=self.basetag)

        self.assertEqual(len(self.queries), 1)
        query = self.queries[0]
        self.assertEqual(query.tables, ['tag'])
        self.assertEqual(query.joins, [
            "LEFT JOIN tag_extra AS te1 ON tag.id = te1.tag_id",
            "LEFT JOIN tag_extra AS te2 ON tag.id = te2.tag_id",
            "LEFT JOIN users ON CAST(te2.value AS INTEGER) = users.id",
            "LEFT JOIN tag_inheritance ON tag.id = tag_inheritance.tag_id"])
        self.assertEqual(query.clauses, [
            "tag_inheritance.active IS TRUE", "tag_inheritance.parent_id = %(basetag_id)s",
            "te1.active IS TRUE", "te1.key = 'sidetag'", "te1.value = 'true'",
            "te2.active IS TRUE", "te2.key = 'sidetag_user_id'",
        ])
        self.assertEqual(query.values, {"basetag_id": self.basetag_info['id'], "user_id": None})

        self.get_tag.assert_called_once_with(self.basetag, strict=True)
        self.get_user.assert_not_called()

    def test_list_sidetags_user(self):
        self.get_user.return_value = self.user_info
        sidetag_hub.listSideTags(user=self.username)

        self.assertEqual(len(self.queries), 1)
        query = self.queries[0]
        self.assertEqual(query.tables, ['tag'])
        self.assertEqual(query.joins, [
            "LEFT JOIN tag_extra AS te1 ON tag.id = te1.tag_id",
            "LEFT JOIN tag_extra AS te2 ON tag.id = te2.tag_id",
            "LEFT JOIN users ON CAST(te2.value AS INTEGER) = users.id"])
        self.assertEqual(query.clauses, [
            "te1.active IS TRUE", "te1.key = 'sidetag'", "te1.value = 'true'",
            "te2.active IS TRUE", "te2.key = 'sidetag_user_id'", "te2.value = %(user_id)s",
        ])
        self.assertEqual(query.values, {"basetag_id": None, "user_id": str(self.user_info['id'])})

        self.get_tag.assert_not_called()
        self.get_user.assert_called_once_with(self.username, strict=True)

    def test_list_sidetags_user_and_basetag(self):
        self.get_tag.return_value = self.basetag_info
        self.get_user.return_value = self.user_info
        sidetag_hub.listSideTags(basetag=self.basetag, user=self.username)

        self.assertEqual(len(self.queries), 1)
        query = self.queries[0]
        self.assertEqual(query.tables, ['tag'])
        self.assertEqual(query.joins, [
            "LEFT JOIN tag_extra AS te1 ON tag.id = te1.tag_id",
            "LEFT JOIN tag_extra AS te2 ON tag.id = te2.tag_id",
            "LEFT JOIN users ON CAST(te2.value AS INTEGER) = users.id",
            "LEFT JOIN tag_inheritance ON tag.id = tag_inheritance.tag_id"])
        self.assertEqual(query.clauses, [
            "tag_inheritance.active IS TRUE", "tag_inheritance.parent_id = %(basetag_id)s",
            "te1.active IS TRUE", "te1.key = 'sidetag'", "te1.value = 'true'",
            "te2.active IS TRUE", "te2.key = 'sidetag_user_id'", "te2.value = %(user_id)s",
        ])
        self.assertEqual(query.values, {"basetag_id": self.basetag_info['id'],
                                        "user_id": str(self.user_info["id"])})

        self.get_tag.assert_called_once_with(self.basetag, strict=True)
        self.get_user.assert_called_once_with(self.username, strict=True)


class TestEditSideTagHub(unittest.TestCase):
    def setUp(self):
        self.context = mock.patch('sidetag_hub.context').start()
        self.get_user = mock.patch('sidetag_hub.get_user').start()
        self.get_tag = mock.patch('sidetag_hub.get_tag').start()
        self.read_inheritance_data = mock.patch('sidetag_hub.readInheritanceData').start()
        self._edit_tag = mock.patch('sidetag_hub._edit_tag').start()
        self.sidetag = 'base_tag-sidetag-12346-suffix'
        self.user_info = {
            'id': 23,
            'name': 'username',
        }
        self.sidetag_info = {
            'arches': '',
            'extra': {'sidetag': True, 'sidetag_user': 'testuser', 'sidetag_user_id': 1},
            'id': 96,
            'name': 'base_tag-sidetag-12346-suffix'
        }

    def tearDown(self):
        mock.patch.stopall()

    def test_edit_sidetag_debuginfo_not_allowed(self):
        read_inheritance_data = [{'parent_id': 999}]
        parent_info = {'id': 999, 'extra': {}}
        self.context.session.assertLogin = mock.MagicMock()
        self.context.session.user_id = 23
        self.get_user.return_value = self.user_info
        self.read_inheritance_data.return_value = read_inheritance_data
        self.get_tag.side_effect = [self.sidetag_info, parent_info]
        with self.assertRaises(koji.GenericError) as ex:
            sidetag_hub.editSideTag(self.sidetag, debuginfo=True)
        self.assertEqual("Debuginfo setting is not allowed in parent tag.", str(ex.exception))

        self.get_user.assert_called_once_with(23, strict=True)
        self.get_tag.assert_has_calls([mock.call(self.sidetag, strict=True), mock.call(999)])
        self.read_inheritance_data.assert_called_once_with(self.sidetag_info['id'])
        self._edit_tag.assert_not_called()

    def test_edit_sidetag_rpm_macros_not_allowed(self):
        read_inheritance_data = [{'parent_id': 999}]
        parent_info = {'id': 999, 'extra': {}}
        self.context.session.assertLogin = mock.MagicMock()
        self.context.session.user_id = 23
        self.get_user.return_value = self.user_info
        self.read_inheritance_data.return_value = read_inheritance_data
        self.get_tag.side_effect = [self.sidetag_info, parent_info]
        with self.assertRaises(koji.GenericError) as ex:
            sidetag_hub.editSideTag(self.sidetag, rpm_macros={'macro_1_name': 'macro_1_value'})
        self.assertEqual("RPM macros change is not allowed in parent tag.", str(ex.exception))

        self.get_user.assert_called_once_with(23, strict=True)
        self.get_tag.assert_has_calls([mock.call(self.sidetag, strict=True), mock.call(999)])
        self.read_inheritance_data.assert_called_once_with(self.sidetag_info['id'])
        self._edit_tag.assert_not_called()

    def test_edit_sidetag_rpm_macros_valid(self):
        read_inheritance_data = [{'parent_id': 999}]
        parent_info = {'id': 999, 'extra': {'sidetag_debuginfo_allowed': True,
                                            'sidetag_rpm_macros_allowed': True}}
        self.context.session.assertLogin = mock.MagicMock()
        self.context.session.user_id = 23
        self.get_user.return_value = self.user_info
        self.read_inheritance_data.return_value = read_inheritance_data
        self.get_tag.side_effect = [self.sidetag_info, parent_info]
        sidetag_hub.editSideTag(self.sidetag, debuginfo=True,
                                rpm_macros={'macro_1_name': 'macro_1_value'},
                                remove_rpm_macros=['macro_2_name'])

        self.get_user.assert_called_once_with(23, strict=True)
        self.get_tag.assert_has_calls([mock.call(self.sidetag, strict=True), mock.call(999)])
        self.read_inheritance_data.assert_called_once_with(self.sidetag_info['id'])
        self._edit_tag.assert_called_once_with(self.sidetag_info['id'],
                                               extra={'with_debuginfo': True,
                                                      'rpm.macro.macro_1_name': 'macro_1_value'},
                                               remove_extra=['rpm.macro.macro_2_name'])


class TestSideTagUntagHub(unittest.TestCase):
    def setUp(self):
        self.get_tag = mock.patch('sidetag_hub.get_tag').start()
        self.is_sidetag = mock.patch('sidetag_hub.is_sidetag').start()
        self._remove_sidetag = mock.patch('sidetag_hub._remove_sidetag').start()
        self.tag_input = {
            'id': 96,
            'name': 'base_tag-sidetag-12346-suffix'
        }
        self.tag_info = {
            'arches': '',
            'extra': {'sidetag': True, 'sidetag_user': 'testuser', 'sidetag_user_id': 1},
            'id': self.tag_input['id'],
            'name': self.tag_input['name']
        }
        self.QueryProcessor = mock.patch('sidetag_hub.QueryProcessor',
                                         side_effect=self.getQuery).start()
        self.queries = []
        self.query_execute = mock.MagicMock()

    def tearDown(self):
        mock.patch.stopall()

    def getQuery(self, *args, **kwargs):
        query = kojihub.QueryProcessor(*args, **kwargs)
        query.execute = self.query_execute
        self.queries.append(query)
        return query

    def test_handle_sidetag_untag_tag_not_in_kws(self):
        rv = sidetag_hub.handle_sidetag_untag('cbtype', {}, {})
        self.assertEqual(rv, None)
        self.assertEqual(len(self.queries), 0)
        self.get_tag.assert_not_called()
        self.is_sidetag.assert_not_called()
        self._remove_sidetag.assert_not_called()

    def test_handle_sidetag_untag_not_tag(self):
        self.get_tag.return_value = None
        rv = sidetag_hub.handle_sidetag_untag('cbtype', tag=self.tag_input)

        self.assertEqual(rv, None)
        self.assertEqual(len(self.queries), 0)

        self.get_tag.assert_called_once_with(self.tag_input['id'], strict=False)
        self.is_sidetag.assert_not_called()
        self._remove_sidetag.assert_not_called()

    def test_handle_sidetag_untag_not_sidetag(self):
        tag_info = {'name': self.tag_input['name'], 'id': self.tag_input['id'], 'extra': {}}
        self.get_tag.return_value = tag_info
        self.is_sidetag.return_value = False
        rv = sidetag_hub.handle_sidetag_untag('cbtype', tag=self.tag_input)

        self.assertEqual(rv, None)
        self.assertEqual(len(self.queries), 0)

        self.get_tag.assert_called_once_with(self.tag_input['id'], strict=False)
        self.is_sidetag.assert_called_once_with(tag_info)
        self._remove_sidetag.assert_not_called()

    def test_handle_sidetag_untag_valid(self):
        self.query_execute.return_value = None
        self.get_tag.return_value = self.tag_info
        self.is_sidetag.return_value = True
        self._remove_sidetag.return_value = None
        rv = sidetag_hub.handle_sidetag_untag('cbtype', tag=self.tag_input)

        self.assertEqual(rv, None)
        self.assertEqual(len(self.queries), 1)
        query = self.queries[0]
        self.assertEqual(query.tables, ['tag_listing'])
        self.assertEqual(query.joins, None)
        self.assertEqual(query.clauses, ["active IS TRUE", "tag_id = %(tag_id)s"])
        self.assertEqual(query.values, {"tag_id": self.tag_info["id"]})

        self.get_tag.assert_called_once_with(self.tag_input['id'], strict=False)
        self.is_sidetag.assert_called_once_with(self.tag_info)
        self._remove_sidetag.assert_called_once_with(self.tag_info)

    def test_handle_sidetag_untag_catch_genericerror(self):
        self.query_execute.return_value = None
        self.get_tag.return_value = self.tag_info
        self.is_sidetag.return_value = True
        self._remove_sidetag.side_effect = koji.GenericError
        rv = sidetag_hub.handle_sidetag_untag('cbtype', tag=self.tag_input)

        self.assertEqual(rv, None)
        self.assertEqual(len(self.queries), 1)
        query = self.queries[0]
        self.assertEqual(query.tables, ['tag_listing'])
        self.assertEqual(query.joins, None)
        self.assertEqual(query.clauses, ["active IS TRUE", "tag_id = %(tag_id)s"])
        self.assertEqual(query.values, {"tag_id": self.tag_info["id"]})

        self.get_tag.assert_called_once_with(self.tag_input['id'], strict=False)
        self.is_sidetag.assert_called_once_with(self.tag_info)
        self._remove_sidetag.assert_called_once_with(self.tag_info)

    def test_handle_sidetag_untag_tag_not_empty(self):
        self.query_execute.return_value = {'build_tag': 22, 'tag_id': self.tag_info['id']}
        self.get_tag.return_value = self.tag_info
        self.is_sidetag.return_value = True
        self._remove_sidetag.side_effect = koji.GenericError
        rv = sidetag_hub.handle_sidetag_untag('cbtype', tag=self.tag_input)

        self.assertEqual(rv, None)
        self.assertEqual(len(self.queries), 1)
        query = self.queries[0]
        self.assertEqual(query.tables, ['tag_listing'])
        self.assertEqual(query.joins, None)
        self.assertEqual(query.clauses, ["active IS TRUE", "tag_id = %(tag_id)s"])
        self.assertEqual(query.values, {"tag_id": self.tag_info["id"]})

        self.get_tag.assert_called_once_with(self.tag_input['id'], strict=False)
        self.is_sidetag.assert_called_once_with(self.tag_info)
        self._remove_sidetag.assert_not_called()
