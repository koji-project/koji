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
                                  values={},
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
                                  values={},
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
                                           '(external_repo.name = %(external_repo_name)s)'],
                                  values={'external_repo_name': 'ext_repo_1'},
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
                                           '(external_repo.id = %(external_repo_id)s)'],
                                  values={'external_repo_id': 1},
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
                                  values={'url': 'http://example.com/repo/'},
                                  opts={})
        self.assertEqual(rv, [{'id': 1,
                               'name': 'ext_repo_1',
                               'url': 'http://example.com/repo/'}])

    def test_get_external_repos_wrong_type(self):
        info = {'info_key': 'info_value'}
        with self.assertRaises(koji.GenericError) as cm:
            kojihub.get_external_repos(info=info)
        self.assertEqual("Invalid name or id value: %s" % info, str(cm.exception))
