# coding: utf-8
import unittest

import mock

import koji
import kojihub

IP = kojihub.InsertProcessor


class TestCreateTag(unittest.TestCase):

    def getInsert(self, *args, **kwargs):
        insert = IP(*args, **kwargs)
        insert.execute = mock.MagicMock()
        self.inserts.append(insert)
        return insert

    def setUp(self):
        self.InsertProcessor = mock.patch('kojihub.kojihub.InsertProcessor',
                                          side_effect=self.getInsert).start()
        self.inserts = []
        self._dml = mock.patch('kojihub.kojihub._dml').start()
        self.get_tag = mock.patch('kojihub.kojihub.get_tag').start()
        self.get_tag_id = mock.patch('kojihub.kojihub.get_tag_id').start()
        self.get_perm_id = mock.patch('kojihub.kojihub.get_perm_id').start()
        self.verify_name_internal = mock.patch('kojihub.kojihub.verify_name_internal').start()
        self.writeInheritanceData = mock.patch('kojihub.kojihub._writeInheritanceData').start()
        self.context = mock.patch('kojihub.kojihub.context').start()
        self.context_db = mock.patch('kojihub.db.context').start()
        # It seems MagicMock will not automatically handle attributes that
        # start with "assert"
        self.context.session.assertPerm = mock.MagicMock()
        self.context_db.session.assertLogin = mock.MagicMock()

    def tearDown(self):
        mock.patch.stopall()

    def test_duplicate(self):
        self.verify_name_internal.return_value = None
        self.get_tag.return_value = {'name': 'duptag'}
        with self.assertRaises(koji.GenericError):
            kojihub.create_tag('duptag')

        self.verify_name_internal.assert_called_once_with('duptag')
        self.get_tag.assert_called_once_with('duptag')
        self.get_perm_id.assert_not_called()
        self.get_tag_id.assert_not_called()
        self.writeInheritanceData.assert_not_called()

    def test_simple_create(self):
        self.get_tag.side_effect = [None, {'id': 1, 'name': 'parent-tag'}]
        self.get_tag_id.return_value = 99
        self.verify_name_internal.return_value = None
        self.context_db.event_id = 42
        self.context_db.session.user_id = 23
        self.writeInheritanceData.return_value = None
        kojihub.create_tag('newtag', parent='parent-tag')

        # check the insert
        self.assertEqual(len(self.inserts), 1)
        insert = self.inserts[0]
        self.assertEqual(insert.table, 'tag_config')
        values = {
            'arches': '',
            'create_event': 42,
            'creator_id': 23,
            'locked': False,
            'maven_include_all': False,
            'maven_support': False,
            'perm_id': None,
            'tag_id': 99,
        }
        self.assertEqual(insert.data, values)
        self.assertEqual(insert.rawdata, {})

        self.verify_name_internal.assert_called_once_with('newtag')
        self.get_tag.assert_has_calls([mock.call('newtag'), mock.call('parent-tag')])
        self.get_perm_id.assert_not_called()
        self.get_tag_id.assert_called_once_with('newtag', create=True)
        data = {'parent_id': 1,
                'priority': 0,
                'maxdepth': None,
                'intransitive': False,
                'noconfig': False,
                'pkg_filter': ''}
        self.writeInheritanceData.assert_called_once_with(99, data)

    def test_invalid_archs(self):
        self.get_tag.return_value = None
        self.get_tag_id.return_value = 99
        self.verify_name_internal.return_value = None
        self.context_db.event_id = 42
        self.context_db.session.user_id = 23

        with self.assertRaises(koji.GenericError):
            kojihub.create_tag('newtag', arches=u'ěšč')

        with self.assertRaises(koji.GenericError):
            kojihub.create_tag('newtag', arches=u'arch1;arch2')

        with self.assertRaises(koji.GenericError):
            kojihub.create_tag('newtag', arches=u'arch1,arch2')

        self.assertEqual(len(self.inserts), 0)

    def test_tag_wrong_format(self):
        tag_name = 'test-tag+'

        # name is longer as expected
        self.verify_name_internal.side_effect = koji.GenericError
        with self.assertRaises(koji.GenericError):
            kojihub.create_tag(tag_name)

        # not except regex rules
        self.verify_name_internal.side_effect = koji.GenericError
        with self.assertRaises(koji.GenericError):
            kojihub.create_tag(tag_name)

    def test_tag_non_exist_parent(self):
        parent_tag = 'parent-tag'
        self.verify_name_internal.return_value = None
        self.get_tag.side_effect = [None, None]
        with self.assertRaises(koji.GenericError) as ex:
            kojihub.create_tag('new-tag', parent=parent_tag)
        self.assertEqual("Parent tag '%s' could not be found" % parent_tag, str(ex.exception))

        self.verify_name_internal.assert_called_once_with('new-tag')
        self.get_tag.assert_has_calls([mock.call('new-tag'), mock.call(parent_tag)])
        self.get_perm_id.assert_not_called()
        self.get_tag_id.assert_not_called()
        self.writeInheritanceData.assert_not_called()

    def test_tag_not_maven_support(self):
        self.verify_name_internal.return_value = None
        self.context.opts.get.return_value = False
        with self.assertRaises(koji.GenericError) as ex:
            kojihub.create_tag('new-tag', maven_support=True)
        self.assertEqual("Maven support not enabled", str(ex.exception))
        with self.assertRaises(koji.GenericError) as ex:
            kojihub.create_tag('new-tag', maven_include_all=True)
        self.assertEqual("Maven support not enabled", str(ex.exception))

        self.verify_name_internal.assert_has_calls([mock.call('new-tag'), mock.call('new-tag')])
        self.get_tag.assert_not_called()
        self.get_perm_id.assert_not_called()
        self.get_tag_id.assert_not_called()
        self.writeInheritanceData.assert_not_called()

    def test_tag_non_exist_perm(self):
        self.verify_name_internal.return_value = None
        self.get_tag.return_value = None
        self.get_perm_id.side_effect = koji.GenericError('No such entry in table permissions: 2')
        with self.assertRaises(koji.GenericError) as ex:
            kojihub.create_tag('new-tag', perm=2)
        self.assertEqual('No such entry in table permissions: 2', str(ex.exception))

        self.verify_name_internal.assert_called_once_with('new-tag')
        self.get_tag.assert_called_once_with('new-tag')
        self.get_perm_id.assert_called_once_with(2, strict=True)
        self.get_tag_id.assert_not_called()
        self.writeInheritanceData.assert_not_called()

    def test_tag_extra(self):
        self.get_tag.return_value = None
        self.get_tag_id.return_value = 99
        self.verify_name_internal.return_value = None
        self.context_db.event_id = 42
        self.context_db.session.user_id = 23
        kojihub.create_tag('newtag', extra={'extra-test': 'extra-name'})

        # check the insert
        self.assertEqual(len(self.inserts), 2)
        insert = self.inserts[0]
        self.assertEqual(insert.table, 'tag_config')
        values = {
            'arches': '',
            'create_event': 42,
            'creator_id': 23,
            'locked': False,
            'maven_include_all': False,
            'maven_support': False,
            'perm_id': None,
            'tag_id': 99,
        }
        self.assertEqual(insert.data, values)
        self.assertEqual(insert.rawdata, {})

        insert = self.inserts[1]
        self.assertEqual(insert.table, 'tag_extra')
        self.assertEqual(insert.data, {'create_event': 42, 'creator_id': 23, 'key': 'extra-test',
                                       'tag_id': 99, 'value': '"extra-name"'})
        self.assertEqual(insert.rawdata, {})

        self.verify_name_internal.assert_called_once_with('newtag')
        self.get_tag.assert_called_once_with('newtag')
        self.get_perm_id.assert_not_called()
        self.get_tag_id.assert_called_once_with('newtag', create=True)
        self.writeInheritanceData.assert_not_called()
