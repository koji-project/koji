# coding: utf-8
import mock
import unittest

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
        self.InsertProcessor = mock.patch('kojihub.InsertProcessor',
                side_effect=self.getInsert).start()
        self.inserts = []
        self._dml = mock.patch('kojihub._dml').start()
        self.get_tag = mock.patch('kojihub.get_tag').start()
        self.get_tag_id = mock.patch('kojihub.get_tag_id').start()
        self.writeInheritanceData = mock.patch('kojihub.writeInheritanceData').start()
        self.context = mock.patch('kojihub.context').start()
        # It seems MagicMock will not automatically handle attributes that
        # start with "assert"
        self.context.session.assertPerm = mock.MagicMock()
        self.context.session.assertLogin = mock.MagicMock()

    def tearDown(self):
        mock.patch.stopall()

    def test_duplicate(self):
        self.get_tag.return_value = {'name': 'duptag'}
        with self.assertRaises(koji.GenericError):
            kojihub.create_tag('duptag')

    def test_simple_create(self):
        self.get_tag.return_value = None
        self.get_tag_id.return_value = 99
        self.context.event_id = 42
        self.context.session.user_id = 23
        kojihub.create_tag('newtag')

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
        self.context.event_id = 42
        self.context.session.user_id = 23

        with self.assertRaises(koji.GenericError):
            kojihub.create_tag('newtag', arches=u'ěšč')

        with self.assertRaises(koji.GenericError):
            kojihub.create_tag('newtag', arches=u'arch1;arch2')

        with self.assertRaises(koji.GenericError):
            kojihub.create_tag('newtag', arches=u'arch1,arch2')

        self.assertEqual(len(self.inserts), 0)
