import mock
import koji
import kojihub
from .utils import DBQueryTestCase


class TestGetNextRelease(DBQueryTestCase):

    def setUp(self):
        super(TestGetNextRelease, self).setUp()
        self.maxDiff = None
        self.get_build = mock.patch('kojihub.kojihub.get_build').start()
        self.binfo = {'name': 'name', 'version': 'version'}

    def tearDown(self):
        mock.patch.stopall()

    def test_get_next_release_new(self):
        # no previous build
        self.qp_execute_one_return_value = None
        result = kojihub.get_next_release(self.binfo)
        self.assertEqual(result, '1')
        self.assertEqual(len(self.queries), 1)
        query = self.queries[0]
        self.assertEqual(query.tables, ['build'])
        self.assertEqual(query.joins, ['package ON build.pkg_id = package.id'])
        self.assertEqual(query.clauses,
                         ['NOT draft', 'name = %(name)s', 'state in %(states)s',
                          'version = %(version)s'])
        self.assertEqual(query.values, {'name': self.binfo['name'],
                                        'version': self.binfo['version'],
                                        'states': (1, 2, 0)
                                        })
        self.assertEqual(query.columns, ['build.id', 'release'])

    def test_get_next_release_int(self):
        for n in [1, 2, 3, 5, 8, 13, 21, 34, 55]:
            self.qp_execute_one_return_value = {'release': str(n)}
            result = kojihub.get_next_release(self.binfo)
            self.assertEqual(result, str(n + 1))

    def test_get_next_release_complex(self):
        data = [
            # [release, bumped_release],
            ['1.el6', '2.el6'],
            ['1.fc23', '2.fc23'],
            ['45.fc23', '46.fc23'],
            ['20211105.nightly.7', '20211105.nightly.8'],
        ]
        for a, b in data:
            self.qp_execute_one_return_value = {'release': a}
            result = kojihub.get_next_release(self.binfo)
            self.assertEqual(result, b)

    def test_get_next_release_bad(self):
        data = [
            # bad_release_value
            "foo",
            "foo.bar",
            "a.b.c.d",
            "a..b..c",
            "1.2.fc23",
        ]
        for val in data:
            self.qp_execute_one_return_value = {'release': val}
            with self.assertRaises(koji.BuildError) as ex:
                kojihub.get_next_release(self.binfo)
            self.assertEqual(f'Unable to increment release value: {val}', str(ex.exception))

    def test_get_next_release_bad_incr(self):
        data = [
            # bad_incr_value
            "foo",
            None,
            {1: 1},
            [1],
        ]
        for val in data:
            with self.assertRaises(koji.ParameterError) as ex:
                kojihub.get_next_release(self.binfo, incr=val)
            self.assertEqual('incr parameter must be an integer', str(ex.exception))
