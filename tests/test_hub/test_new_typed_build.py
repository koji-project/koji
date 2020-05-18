import mock
import unittest

import kojihub


class TestNewTypedBuild(unittest.TestCase):

    @mock.patch('kojihub.lookup_name')
    @mock.patch('kojihub.QueryProcessor')
    @mock.patch('kojihub.InsertProcessor')
    def test_new_typed_build(self, InsertProcessor, QueryProcessor, lookup_name):

        binfo = {'id': 1, 'foo': '137'}
        btype = 'sometype'
        lookup_name.return_value = {'id': 99, 'name': btype}

        # no current entry
        query = QueryProcessor.return_value
        query.executeOne.return_value = None
        insert = InsertProcessor.return_value
        kojihub.new_typed_build(binfo, btype)
        QueryProcessor.assert_called_once()
        query.executeOne.assert_called_once()
        InsertProcessor.assert_called_once()
        insert.execute.assert_called_once()

        InsertProcessor.reset_mock()
        QueryProcessor.reset_mock()

        # current entry
        query = QueryProcessor.return_value
        query.executeOne.return_value = {'build_id':binfo['id']}
        kojihub.new_typed_build(binfo, btype)
        QueryProcessor.assert_called_once()
        query.executeOne.assert_called_once()
        InsertProcessor.assert_not_called()
