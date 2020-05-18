import koji
import kojihub
from .utils import DBQueryTestCase


class TestGetExternalRepos(DBQueryTestCase):
    maxDiff = None

    def test_get_external_repos(self):
        self.qp_execute_return_value = [{'id': 1,
                                         'name': 'ext_repo_1',
                                         'url': 'http://example.com/repo/'}]
        rv = kojihub.get_external_repos()
        self.assertEqual(len(self.queries), 1)
        self.assertLastQueryEqual(tables=['external_repo'],
                                  columns=['id', 'name', 'url'],
                                  joins=[
                                      'external_repo_config ON external_repo_id = id'],
                                  clauses=['(active = TRUE)'],
                                  values={'clauses': ['(active = TRUE)'],
                                          'event': None,
                                          'fields': ['id', 'name', 'url'],
                                          'info': None,
                                          'joins': [
                                              'external_repo_config ON external_repo_id = id'],
                                          'queryOpts': None,
                                          'tables': ['external_repo'],
                                          'url': None},
                                  opts={})
        self.assertEqual(rv, [{'id': 1,
                               'name': 'ext_repo_1',
                               'url': 'http://example.com/repo/'}])

    def test_get_external_repos_event(self):
        self.qp_execute_return_value = [{'id': 1,
                                         'name': 'ext_repo_1',
                                         'url': 'http://example.com/repo/'}]
        rv = kojihub.get_external_repos(event=1000)
        self.assertEqual(len(self.queries), 1)
        self.assertLastQueryEqual(tables=['external_repo'],
                                  columns=['id', 'name', 'url'],
                                  joins=[
                                      'external_repo_config'
                                      ' ON external_repo_id = id'],
                                  clauses=[
                                      '(create_event <= 1000'
                                      ' AND ( revoke_event IS NULL'
                                      ' OR 1000 < revoke_event ))'],
                                  values={'clauses': [
                                      '(create_event <= 1000'
                                      ' AND ( revoke_event IS NULL'
                                      ' OR 1000 < revoke_event ))'],
                                      'event': 1000,
                                      'fields': ['id', 'name', 'url'],
                                      'info': None,
                                      'joins': [
                                          'external_repo_config ON'
                                          ' external_repo_id = id'],
                                      'queryOpts': None,
                                      'tables': ['external_repo'],
                                      'url': None},
                                  opts={})
        self.assertEqual(rv, [{'id': 1,
                               'name': 'ext_repo_1',
                               'url': 'http://example.com/repo/'}])

    def test_get_external_repos_by_name(self):
        self.qp_execute_return_value = [{'id': 1,
                                         'name': 'ext_repo_1',
                                         'url': 'http://example.com/repo/'}]
        rv = kojihub.get_external_repos(info='ext_repo_1')
        self.assertEqual(len(self.queries), 1)
        self.assertLastQueryEqual(tables=['external_repo'],
                                  columns=['id', 'name', 'url'],
                                  joins=[
                                      'external_repo_config ON external_repo_id = id'],
                                  clauses=['(active = TRUE)',
                                           'name = %(info)s'],
                                  values={'clauses': ['(active = TRUE)',
                                                      'name = %(info)s'],
                                          'event': None,
                                          'fields': ['id', 'name', 'url'],
                                          'info': 'ext_repo_1',
                                          'joins': [
                                              'external_repo_config ON external_repo_id = id'],
                                          'queryOpts': None,
                                          'tables': ['external_repo'],
                                          'url': None},
                                  opts={})
        self.assertEqual(rv, [{'id': 1,
                               'name': 'ext_repo_1',
                               'url': 'http://example.com/repo/'}])

    def test_get_external_repos_by_id(self):
        self.qp_execute_return_value = [{'id': 1,
                                         'name': 'ext_repo_1',
                                         'url': 'http://example.com/repo/'}]
        rv = kojihub.get_external_repos(info=1)
        self.assertEqual(len(self.queries), 1)
        self.assertLastQueryEqual(tables=['external_repo'],
                                  columns=['id', 'name', 'url'],
                                  joins=[
                                      'external_repo_config ON external_repo_id = id'],
                                  clauses=['(active = TRUE)',
                                           'id = %(info)i'],
                                  values={'clauses': ['(active = TRUE)',
                                                      'id = %(info)i'],
                                          'event': None,
                                          'fields': ['id', 'name', 'url'],
                                          'info': 1,
                                          'joins': [
                                              'external_repo_config ON external_repo_id = id'],
                                          'queryOpts': None,
                                          'tables': ['external_repo'],
                                          'url': None},
                                  opts={})
        self.assertEqual(rv, [{'id': 1,
                               'name': 'ext_repo_1',
                               'url': 'http://example.com/repo/'}])

    def test_get_external_repos_by_url(self):
        self.qp_execute_return_value = [{'id': 1,
                                         'name': 'ext_repo_1',
                                         'url': 'http://example.com/repo/'}]
        rv = kojihub.get_external_repos(url='http://example.com/repo/')
        self.assertEqual(len(self.queries), 1)
        self.assertLastQueryEqual(tables=['external_repo'],
                                  columns=['id', 'name', 'url'],
                                  joins=[
                                      'external_repo_config ON external_repo_id = id'],
                                  clauses=['(active = TRUE)',
                                           'url = %(url)s'],
                                  values={'clauses': ['(active = TRUE)',
                                                      'url = %(url)s'],
                                          'event': None,
                                          'fields': ['id', 'name', 'url'],
                                          'info': None,
                                          'joins': [
                                              'external_repo_config ON external_repo_id = id'],
                                          'queryOpts': None,
                                          'tables': ['external_repo'],
                                          'url': 'http://example.com/repo/'},
                                  opts={})
        self.assertEqual(rv, [{'id': 1,
                               'name': 'ext_repo_1',
                               'url': 'http://example.com/repo/'}])
