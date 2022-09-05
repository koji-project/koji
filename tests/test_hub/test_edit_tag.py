# coding: utf-8
import unittest

import mock

import koji
import kojihub

UP = kojihub.UpdateProcessor
IP = kojihub.InsertProcessor


class TestEditTag(unittest.TestCase):
    def getInsert(self, *args, **kwargs):
        insert = IP(*args, **kwargs)
        insert.execute = mock.MagicMock()
        self.inserts.append(insert)
        return insert

    def getUpdate(self, *args, **kwargs):
        update = UP(*args, **kwargs)
        update.execute = mock.MagicMock()
        self.updates.append(update)
        return update

    def setUp(self):
        self.InsertProcessor = mock.patch('kojihub.InsertProcessor',
                                          side_effect=self.getInsert).start()
        self.inserts = []
        self.UpdateProcessor = mock.patch('kojihub.UpdateProcessor',
                                          side_effect=self.getUpdate).start()
        self.updates = []
        self._singleValue = mock.patch('kojihub._singleValue').start()
        self.get_tag = mock.patch('kojihub.get_tag').start()
        self.get_perm_id = mock.patch('kojihub.get_perm_id').start()
        self.verify_name_internal = mock.patch('kojihub.verify_name_internal').start()
        self.context = mock.patch('kojihub.context').start()
        self.context_db = mock.patch('koji.db.context').start()
        # It seems MagicMock will not automatically handle attributes that
        # start with "assert"
        self.context_db.session.assertLogin = mock.MagicMock()

    def tearDown(self):
        mock.patch.stopall()

    def test_maven_disable(self):
        self.context.opts.get.return_value = False
        with self.assertRaises(koji.GenericError):
            kojihub._edit_tag('tag', maven_support=True)
        with self.assertRaises(koji.GenericError):
            kojihub._edit_tag('tag', maven_include_all=False)
        self.context.opts.get.return_value = True
        kojihub._edit_tag('tag', maven_support=True)
        self.get_tag.assert_called_once()

    def test_edit(self):
        self.get_tag.return_value = {'id': 333,
                                     'perm_id': 1,
                                     'name': 'tag',
                                     'arches': 'arch1 arch3',
                                     'locked': False,
                                     'maven_support': False,
                                     'maven_include_all': False,
                                     'extra': {'exA': 1,
                                               'exC': 3,
                                               'exD': 4}}
        self._singleValue.return_value = None
        self.verify_name_internal.return_value = None
        self.context_db.event_id = 42
        self.context_db.session.user_id = 23
        # no1 invoke
        kwargs = {
            'perm': None,
            'name': 'newtag',
            'arches': 'arch1 arch2',
            'locked': True,
            'maven_support': True,
            'maven_include_all': True,
            'extra': {'exB': [None, 1, 'text', {'dict': 'val'}, (1, 2)]},
            'remove_extra': ['exC']
        }
        kojihub._edit_tag('tag', **kwargs)

        self.get_perm_id.assert_not_called()

        # check the insert/update
        self.assertEqual(len(self.updates), 4)
        self.assertEqual(len(self.inserts), 2)

        revoke_data = {'name': 'newtag'}

        values = {'tagID': 333}

        update = self.updates[0]
        self.assertEqual(update.table, 'tag')
        self.assertEqual(update.values, values)
        self.assertEqual(update.data, revoke_data)
        self.assertEqual(update.rawdata, {})
        self.assertEqual(update.clauses, ['id = %(tagID)i'])

        values = {
            'arches': 'arch1 arch2',
            'locked': True,
            'maven_include_all': True,
            'maven_support': True,
            'perm_id': None,
            'id': 333,
            'name': 'tag',
            'extra': {'exA': 1, 'exC': 3, 'exD': 4}
        }

        revoke_data = {
            'revoke_event': 42,
            'revoker_id': 23
        }
        revoke_rawdata = {'active': 'NULL'}

        update = self.updates[1]
        self.assertEqual(update.table, 'tag_config')
        self.assertEqual(update.values, values)
        self.assertEqual(update.data, revoke_data)
        self.assertEqual(update.rawdata, revoke_rawdata)
        self.assertEqual(update.clauses, ['tag_id = %(id)i', 'active = TRUE'])

        data = {
            'create_event': 42,
            'creator_id': 23,
            'arches': 'arch1 arch2',
            'locked': True,
            'maven_include_all': True,
            'maven_support': True,
            'perm_id': None,
            'tag_id': 333,
        }
        insert = self.inserts[0]
        self.assertEqual(insert.table, 'tag_config')
        self.assertEqual(insert.data, data)
        self.assertEqual(insert.rawdata, {})

        values = {
            'key': 'exB',
            'value': '[null, 1, "text", {"dict": "val"}, [1, 2]]',
            'tag_id': 333,
        }

        update = self.updates[2]
        self.assertEqual(update.table, 'tag_extra')
        self.assertEqual(update.values, values)
        self.assertEqual(update.data, revoke_data)
        self.assertEqual(update.rawdata, revoke_rawdata)
        self.assertEqual(update.clauses, ['tag_id = %(tag_id)i', 'key=%(key)s', 'active = TRUE'])

        data = {
            'create_event': 42,
            'creator_id': 23,
            'key': 'exB',
            'value': '[null, 1, "text", {"dict": "val"}, [1, 2]]',
            'tag_id': 333,
        }

        insert = self.inserts[1]
        self.assertEqual(insert.table, 'tag_extra')
        self.assertEqual(insert.data, data)
        self.assertEqual(insert.rawdata, {})

        values = {
            'key': 'exC',
            'tag_id': 333,
        }

        update = self.updates[3]
        self.assertEqual(update.table, 'tag_extra')
        self.assertEqual(update.values, values)
        self.assertEqual(update.data, revoke_data)
        self.assertEqual(update.rawdata, revoke_rawdata)
        self.assertEqual(update.clauses, ['tag_id = %(tag_id)i', 'key=%(key)s', 'active = TRUE'])

        # no2 invoke
        kwargs = {
            'extra': {'exC': 'text'},
            'remove_extra': ['exC']
        }

        with self.assertRaises(koji.GenericError) as cm:
            kojihub._edit_tag('tag', **kwargs)
        self.assertEqual(cm.exception.args[0],
                         'Can not both add/update and remove tag-extra: \'exC\'')

        # no3 invoke
        kwargs = {
            'remove_extra': ['exE']
        }

        with self.assertRaises(koji.GenericError) as cm:
            kojihub._edit_tag('tag', **kwargs)
        self.assertEqual(cm.exception.args[0], "Tag: tag doesn't have extra: exE")

        # no4 invoke
        self.get_perm_id.reset_mock()
        self.get_perm_id.return_value = 99
        self._singleValue.reset_mock()
        self._singleValue.return_value = 2

        kwargs = {
            'perm': 'admin',
            'name': 'newtag',
        }
        with self.assertRaises(koji.GenericError) as cm:
            kojihub._edit_tag('tag', **kwargs)
        self.get_perm_id.assert_called_once()
        self._singleValue.assert_called_once()
        self.assertEqual(cm.exception.args[0], 'Name newtag already taken by tag 2')

    def test_invalid_archs(self):
        self.get_tag.return_value = {
            'create_event': 42,
            'creator_id': 23,
            'arches': 'arch1 arch2',
            'locked': True,
            'maven_include_all': True,
            'maven_support': True,
            'perm_id': None,
            'tag_id': 333,
            'name': 'newtag',
            'id': 345,
        }

        # valid
        kwargs = {
            'name': 'newtag',
            'arches': 'valid_arch',
        }
        kojihub._edit_tag('tag', **kwargs)

        # invalid 1
        kwargs['arches'] = u'ěšč'
        with self.assertRaises(koji.GenericError):
            kojihub._edit_tag('tag', **kwargs)

        # invalid 2
        kwargs['arches'] = u'arch1;arch2'
        with self.assertRaises(koji.GenericError):
            kojihub._edit_tag('tag', **kwargs)

        # invalid 2
        kwargs['arches'] = u'arch1,arch2'
        with self.assertRaises(koji.GenericError):
            kojihub._edit_tag('tag', **kwargs)

    def test_edit_wrong_tag(self):
        tag_name_new = 'new-test-tag+'
        tag_name = 'tag'
        self.get_tag.return_value = {'id': 333,
                                     'perm_id': 1,
                                     'name': tag_name,
                                     'arches': 'arch1 arch3',
                                     'locked': False,
                                     'maven_support': False,
                                     'maven_include_all': False,
                                     'extra': {'exA': 1,
                                               'exC': 3,
                                               'exD': 4}}
        kwargs = {
            'perm': None,
            'name': tag_name_new,
            'arches': 'arch1 arch2',
            'locked': True,
            'maven_support': False,
            'maven_include_all': False,
            'extra': {},
            'remove_extra': []
        }
        # name is longer as expected
        self.verify_name_internal.side_effect = koji.GenericError
        with self.assertRaises(koji.GenericError):
            kojihub._edit_tag('tag', **kwargs)

        # not except regex rules
        self.verify_name_internal.side_effect = koji.GenericError
        with self.assertRaises(koji.GenericError):
            kojihub._edit_tag('tag', **kwargs)

    def test_edit_tag_remove_extra_wrong_format(self):
        kwargs = {
            'perm': None,
            'name': 'tag_name_new',
            'arches': 'arch1 arch2',
            'locked': True,
            'maven_support': False,
            'maven_include_all': False,
            'extra': {},
            'remove_extra': 'remove-extra'
        }
        with self.assertRaises(koji.ParameterError) as ex:
            kojihub._edit_tag('tag', **kwargs)
        self.assertEqual(f"Invalid type for value '{kwargs['remove_extra']}': "
                         f"{type(kwargs['remove_extra'])}, expected type <class 'list'>",
                         str(ex.exception))

    def test_edit_tag_block_extra_wrong_format(self):
        kwargs = {
            'perm': None,
            'name': 'tag_name_new',
            'arches': 'arch1 arch2',
            'locked': True,
            'maven_support': False,
            'maven_include_all': False,
            'extra': {},
            'remove_extra': [],
            'block_extra': 'block-extra'
        }
        with self.assertRaises(koji.ParameterError) as ex:
            kojihub._edit_tag('tag', **kwargs)
        self.assertEqual(f"Invalid type for value '{kwargs['block_extra']}': "
                         f"{type(kwargs['block_extra'])}, expected type <class 'list'>",
                         str(ex.exception))
