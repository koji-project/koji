from __future__ import absolute_import
import mock
import unittest

import koji
import kojihub
import sidetag_hub


class TestSideTagHub(unittest.TestCase):
    def setUp(self):
        self.QueryProcessor = mock.patch('sidetag_hub.QueryProcessor',
                side_effect=self.getQuery).start()
        self.queries = []

    def getQuery(self, *args, **kwargs):
        query = kojihub.QueryProcessor(*args, **kwargs)
        query.execute = mock.MagicMock()
        query.executeOne = mock.MagicMock()
        query.executeOne.return_value = {'user_tags': 0}
        self.queries.append(query)
        return query

    @mock.patch('sidetag_hub.nextval')
    @mock.patch('sidetag_hub._create_build_target')
    @mock.patch('sidetag_hub._create_tag')
    @mock.patch('sidetag_hub.assert_policy')
    @mock.patch('sidetag_hub.get_tag')
    @mock.patch('sidetag_hub.get_user')
    @mock.patch('sidetag_hub.context')
    def test_createsidetag_basic(self, context, get_user, get_tag, assert_policy,
                                 _create_tag, _create_build_target, nextval):
        basetag = {
            'id': 32,
            'name': 'base_tag',
            'arches': ['x86_64', 'i686']
        }
        user = {
            'id': 23,
            'name': 'username',
        }
        sidetag_name = 'base_tag-side-12346'
        context.session.assertLogin = mock.MagicMock()
        context.session.user_id = 123
        get_user.return_value = user
        get_tag.return_value = basetag
        nextval.return_value = 12345
        _create_tag.return_value = 12346

        ret = sidetag_hub.createSideTag('base_tag')
        self.assertEqual(ret, {'name': sidetag_name, 'id': 12346})

        get_user.assert_called_once_with(123, strict=True)
        get_tag.assert_called_once_with(basetag['name'], strict=True)
        assert_policy.assert_called_once_with(
            "sidetag", {"tag": basetag["id"], "number_of_tags": 0}
        )
        nextval.assert_called_once_with('tag_id_seq')
        _create_tag.assert_called_once_with(
                sidetag_name,
                parent=basetag['id'],
                arches=basetag['arches'],
                extra={
                    "sidetag": True,
                    "sidetag_user": user["name"],
                    "sidetag_user_id": user["id"],
                })
        _create_build_target.assert_called_once_with(sidetag_name, 12346, 12346)

    @mock.patch('sidetag_hub.nextval')
    @mock.patch('sidetag_hub._create_build_target')
    @mock.patch('sidetag_hub._create_tag')
    @mock.patch('sidetag_hub.assert_policy')
    @mock.patch('sidetag_hub.get_tag')
    @mock.patch('sidetag_hub.get_user')
    @mock.patch('sidetag_hub.context')
    def test_createsidetag_template(self, context, get_user, get_tag, assert_policy,
                                    _create_tag, _create_build_target, nextval):
        basetag = {
            'id': 32,
            'name': 'base_tag',
            'arches': ['x86_64', 'i686']
        }
        user = {
            'id': 23,
            'name': 'username',
        }
        sidetag_name = 'base_tag-sidetag-12346-suffix'
        context.session.assertLogin = mock.MagicMock()
        context.session.user_id = 123
        get_user.return_value = user
        get_tag.return_value = basetag
        nextval.return_value = 12345
        _create_tag.return_value = 12346
        sidetag_hub.ALLOWED_SUFFIXES = ['suffix', 'another']
        sidetag_hub.NAME_TEMPLATE = '{basetag}-sidetag-{tag_id}'

        ret = sidetag_hub.createSideTag('base_tag', suffix='suffix')
        self.assertEqual(ret, {'name': sidetag_name, 'id': 12346})

        with self.assertRaises(koji.GenericError):
            ret = sidetag_hub.createSideTag('base_tag', suffix='forbidden_suffix')
