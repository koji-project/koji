
import unittest
import mock

import koji
import kojihub
from koji.util import dslice_ex

IP = kojihub.InsertProcessor


class TestSignedRepoInit(unittest.TestCase):


    def getInsert(self, *args, **kwargs):
        insert = IP(*args, **kwargs)
        insert.execute = mock.MagicMock()
        self.inserts.append(insert)
        return insert


    def setUp(self):
        self.InsertProcessor = mock.patch('kojihub.InsertProcessor',
                side_effect=self.getInsert).start()
        self.inserts = []
 
        self.get_tag = mock.patch('kojihub.get_tag').start()
        self.get_event = mock.patch('kojihub.get_event').start()
        self.nextval = mock.patch('kojihub.nextval').start()
        self.ensuredir = mock.patch('koji.ensuredir').start()
        self.copyfile = mock.patch('shutil.copyfile').start()

        self.get_tag.return_value = {'id': 42, 'name': 'tag'}
        self.get_event.return_value = 12345
        self.nextval.return_value = 99


    def tearDown(self):
        mock.patch.stopall()


    def test_simple_signed_repo_init(self):

        # simple case
        kojihub.signed_repo_init('tag', ['key'], {'arch': ['x86_64']})
        self.InsertProcessor.assert_called_once()

        ip = self.inserts[0]
        self.assertEquals(ip.table, 'repo')
        data = {'signed': True, 'create_event': 12345, 'tag_id': 42, 'id': 99,
                    'state': koji.REPO_STATES['INIT']}
        self.assertEquals(ip.data, data)
        self.assertEquals(ip.rawdata, {})

        # no comps option
        self.copyfile.assert_not_called()


    def test_signed_repo_init_with_comps(self):

        # simple case
        kojihub.signed_repo_init('tag', ['key'], {'arch': ['x86_64'],
                    'comps': 'COMPSFILE'})
        self.InsertProcessor.assert_called_once()

        ip = self.inserts[0]
        self.assertEquals(ip.table, 'repo')
        data = {'signed': True, 'create_event': 12345, 'tag_id': 42, 'id': 99,
                    'state': koji.REPO_STATES['INIT']}
        self.assertEquals(ip.data, data)
        self.assertEquals(ip.rawdata, {})

        # no comps option
        self.copyfile.assert_called_once()
