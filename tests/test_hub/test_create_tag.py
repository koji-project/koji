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
        self.context_db = mock.patch('koji.db.context').start()
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
        insert = self.inserts[0]

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

    def test_tag_not_maven_support(self):
        self.verify_name_internal.return_value = None
        self.context.opts.get.return_value = False
        with self.assertRaises(koji.GenericError) as ex:
            kojihub.create_tag('new-tag', maven_support=True)
        self.assertEqual("Maven support not enabled", str(ex.exception))
        with self.assertRaises(koji.GenericError) as ex:
            kojihub.create_tag('new-tag', maven_include_all=True)
        self.assertEqual("Maven support not enabled", str(ex.exception))
