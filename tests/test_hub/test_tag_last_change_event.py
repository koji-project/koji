from __future__ import absolute_import
import mock
import os
import re
try:
    import unittest2 as unittest
except ImportError:
    import unittest

import koji
import kojihub


QP = kojihub.QueryProcessor


class TestTagChangeEvent(unittest.TestCase):

    def setUp(self):
        self.QueryProcessor = mock.patch('kojihub.kojihub.QueryProcessor',
                side_effect=self.get_query).start()
        self.queries = []
        self.singleValue = mock.MagicMock()
        self.get_tag_id = mock.patch('kojihub.kojihub.get_tag_id').start()
        self.get_tag = mock.patch('kojihub.kojihub.get_tag').start()
        self.readFullInheritance = mock.patch('kojihub.kojihub.readFullInheritance').start()
        self.get_tag_external_repos = mock.patch('kojihub.kojihub.get_tag_external_repos').start()
        self.get_tag_external_repos.return_value = []

    def tearDown(self):
        mock.patch.stopall()

    def get_query(self, *args, **kwargs):
        query = QP(*args, **kwargs)
        query.execute = mock.MagicMock()
        query.singleValue = self.singleValue
        self.queries.append(query)
        return query

    def test_tag_last_change_simple(self):
        tags = [5, 6, 7, 8, 17, 23, 42]
        self.get_tag.return_value = {'id': tags[0], 'revoke_event': None}
        self.readFullInheritance.return_value = [{'parent_id':n} for n in tags[1:]]
        erepos = [101, 201]
        self.get_tag_external_repos.return_value = [{'external_repo_id': n} for n in erepos]
        events = [8, 8, 8, 8, 8, 8, None, 8, 8, 42, 23, 23, 23, 23, 23, None, 23, 23, 23,
                  8, 8, 8, 8]  # len=23
        # called once for tag_updates, twice for versioned tag tables, and twice for erepo tables
        # 1 + 2*9 + 2*2 = 23
        self.singleValue.side_effect = events

        event = kojihub.tag_last_change_event('TAG')

        self.assertEqual(event, 42)  # max(events)
        self.assertEqual(len(self.queries), 23)
        self.readFullInheritance.assert_called_once_with(tags[0], event=None)
        for query in self.queries[:19]:  # tag queries
            self.assertEqual(query.clauses[0], 'tag_id IN %(tags)s')
            self.assertEqual(query.values['tags'], tags)
            # we didn't pass an event, so there should be no second clause
            self.assertEqual(len(query.clauses), 1)
        for query in self.queries[19:]:  # erepo queries
            self.assertEqual(query.clauses[0], 'external_repo_id IN %(repos)s')
            self.assertEqual(query.values['repos'], erepos)
            # we didn't pass an event, so there should be no second clause
            self.assertEqual(len(query.clauses), 1)

    def test_tag_last_change_noinherit(self):
        tags = [5, 6, 7, 8, 17, 23, 42]
        self.get_tag.return_value = {'id': tags[0], 'revoke_event': None}
        self.readFullInheritance.return_value = [{'parent_id':n} for n in tags[1:]]
        events = [8, 8, 8, 8, 8, 8, None, 8, 8, 42, 23, 23, 23, 23, 23, None, 23, 23, 23]  # len=19
        self.singleValue.side_effect = events

        event = kojihub.tag_last_change_event('TAG', inherit=False)

        self.assertEqual(event, 42)  # max(events)
        self.assertEqual(len(self.queries), 19)
        self.readFullInheritance.assert_not_called()
        for query in self.queries:
            self.assertEqual(query.clauses[0], 'tag_id IN %(tags)s')
            # only the tag itself should be in the query condition
            self.assertEqual(query.values['tags'], [tags[0]])
            # we didn't pass an event, so there should be no second clause
            self.assertEqual(len(query.clauses), 1)

    def test_tag_last_change_deleted(self):
        self.get_tag.return_value = {'id': 5, 'revoke_event': 9999}

        event = kojihub.tag_last_change_event('TAG')

        self.assertEqual(event, 9999)
        self.readFullInheritance.assert_not_called()
        self.get_tag_external_repos.assert_not_called()
        self.singleValue.assert_not_called()
        self.assertEqual(len(self.queries), 0)

    def test_tag_last_change_before(self):
        tags = [5, 6, 7, 8, 17, 23, 42]
        before = 123
        self.get_tag.return_value = {'id': tags[0], 'revoke_event': None}
        self.readFullInheritance.return_value = [{'parent_id':n} for n in tags[1:]]
        erepos = [101, 201]
        self.get_tag_external_repos.return_value = [{'external_repo_id': n} for n in erepos]
        events = [8, 8, 8, 8, 8, 8, None, 8, 8, 42, 23, 23, 23, 23, 23, None, 23, 23, 23,
                  8, 8, 8, 8]  # len=23
        # called once for tag_updates, twice for versioned tag tables, and twice for erepo tables
        # 1 + 2*9 + 2*2 = 23
        self.singleValue.side_effect = events

        event = kojihub.tag_last_change_event('TAG', before=before)

        self.assertEqual(event, 42)  # max(events)
        self.assertEqual(len(self.queries), 23)
        self.readFullInheritance.assert_called_once_with(tags[0], event=before)
        for query in self.queries[:19]:
            self.assertEqual(query.values['tags'], tags)
            self.assertEqual(query.values['before'], before)
            # QP sorts the clauses, so they are not in the order the code adds them
            self.assertIn('tag_id IN %(tags)s', query.clauses)
            self.assertEqual(len(query.clauses), 2)
        for query in self.queries[19:]:  # erepo queries
            self.assertIn('external_repo_id IN %(repos)s', query.clauses)
            self.assertEqual(query.values['repos'], erepos)
            self.assertEqual(query.values['before'], before)
            # we didn't pass an event, so there should be no second clause
            self.assertEqual(len(query.clauses), 2)

    def test_tag_first_change_simple(self):
        self.get_tag_id.return_value = 99
        events = [88]
        self.singleValue.side_effect = events

        event = kojihub.tag_first_change_event('TAG')

        self.assertEqual(event, 88)
        self.assertEqual(len(self.queries), 1)
        self.readFullInheritance.assert_not_called()
        # first query is for tag_config
        query = self.queries[0]
        self.assertEqual(query.tables, ['tag_config'])
        self.assertEqual(query.clauses[0], 'tag_id = %(tag_id)s')
        self.assertEqual(query.values['tag_id'], 99)
        self.assertEqual(len(query.clauses), 1)

    def test_tag_first_change_noinherit(self):
        self.get_tag_id.return_value = 99
        events = [88]
        self.singleValue.side_effect = events

        event = kojihub.tag_first_change_event('TAG', inherit=False)

        # with no after arg, we should only query tag_config
        self.assertEqual(event, 88)
        self.readFullInheritance.assert_not_called()
        self.assertEqual(len(self.queries), 1)
        query = self.queries[0]
        self.assertEqual(query.tables, ['tag_config'])
        self.assertEqual(query.clauses[0], 'tag_id = %(tag_id)s')
        # only the tag itself should be in the query condition
        self.assertEqual(query.values['tag_id'], 99)
        # we didn't pass an event, so there should be no second clause
        self.assertEqual(len(query.clauses), 1)

    def test_tag_first_change_after(self):
        tags = [5, 6, 7, 8, 17, 23, 42]
        after = 5
        self.get_tag_id.return_value = tags[0]
        self.readFullInheritance.return_value = [{'parent_id':n} for n in tags[1:]]
        erepos = [101, 201]
        self.get_tag_external_repos.return_value = [{'external_repo_id': n} for n in erepos]
        events = [8, 8, 8, 8, 8, 8, 8, None, 8, 8, 42, 23, 23, 23, 23, 23, None, 23, 23, 23,
                  8, 8, 8, 8]  # len=24
        self.assertEqual(len(events), 24)
        # called once for tag_config, once for tag_updates, twice for versioned tag tables,
        # and twice for erepo tables
        # 1 + 1 + 2*9 + 2*2 = 23
        self.singleValue.side_effect = events

        event = kojihub.tag_first_change_event('TAG', after=after)

        self.assertEqual(event, 8)  # min(events)
        self.assertEqual(len(self.queries), 24)
        self.readFullInheritance.assert_called_once_with(tags[0], event=after)
        for query in self.queries[1:20]:
            self.assertEqual(query.values['tags'], tags)
            self.assertEqual(query.values['after'], after)
            # QP sorts the clauses, so they are not in the order the code adds them
            self.assertIn('tag_id IN %(tags)s', query.clauses)
            self.assertEqual(len(query.clauses), 2)
        for query in self.queries[20:]:
            self.assertEqual(query.values['repos'], erepos)
            self.assertEqual(query.values['after'], after)
            # QP sorts the clauses, so they are not in the order the code adds them
            self.assertIn('external_repo_id IN %(repos)s', query.clauses)
            self.assertEqual(len(query.clauses), 2)

    def test_tag_first_change_after_noinherit(self):
        # without inheritance, we'll only query the tag itself
        tag_id = 999
        after = 5
        self.get_tag_id.return_value = tag_id
        events = [8, 8, 8, 8, 8, 8, 8, None, 8, 8, 42, 23, 23, 23, 23, 23, None, 23, 23, 23]
        self.assertEqual(len(events), 20)
        # called once for tag_config, once for tag_updates, and twice for versioned tag tables
        # 2 + 2*9 = 20
        self.singleValue.side_effect = events

        event = kojihub.tag_first_change_event('TAG', after=after, inherit=False)

        self.assertEqual(event, 8)  # min(events)
        self.assertEqual(len(self.queries), 20)
        self.readFullInheritance.assert_not_called()
        for query in self.queries[1:]:
            self.assertEqual(query.values['tags'], [tag_id])
            self.assertEqual(query.values['after'], after)
            # QP sorts the clauses, so they are not in the order the code adds them
            self.assertIn('tag_id IN %(tags)s', query.clauses)
            self.assertEqual(len(query.clauses), 2)


# the end
