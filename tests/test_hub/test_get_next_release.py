import mock
import unittest
import koji
import kojihub


class TestGetNextRelease(unittest.TestCase):

    def setUp(self):
        self.QueryProcessor = mock.patch('kojihub.QueryProcessor').start()
        self._dml = mock.patch('kojihub._dml').start()
        self.query = self.QueryProcessor.return_value
        self.binfo = {'name': 'name', 'version': 'version'}

    def tearDown(self):
        mock.patch.stopall()

    def test_get_next_release_new(self):
        # no previous build
        self.query.executeOne.return_value = None
        result = kojihub.get_next_release(self.binfo)
        self.assertEqual(result, '1')

    def test_get_next_release_int(self):
        for n in [1, 2, 3, 5, 8, 13, 21, 34, 55]:
            self.query.executeOne.return_value = {'release': str(n)}
            result = kojihub.get_next_release(self.binfo)
            self.assertEqual(result, str(n+1))

    def test_get_next_release_complex(self):
        data = [
            # [release, bumped_release],
            ['1.el6', '2.el6'],
            ['1.fc23', '2.fc23'],
            ['45.fc23', '46.fc23'],
        ]
        for a, b in data:
            self.query.executeOne.return_value = {'release': a}
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
            self.query.executeOne.return_value = {'release': val}
            with self.assertRaises(koji.BuildError):
                kojihub.get_next_release(self.binfo)

