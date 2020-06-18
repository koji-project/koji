import mock

from .utils import DBQueryTestCase

import koji
import kojihub


class TestGetPackageID(DBQueryTestCase):
    maxDiff = None

    def test_getPackageID(self):
        self.qp_execute_return_value = [{'id': 1}]
        rv = kojihub.RootExports().getPackageID('koji')
        self.assertEqual(len(self.queries), 1)
        self.assertLastQueryEqual(tables=['package'],
                                  columns=['id'],
                                  clauses=['name=%(name)s'],
                                  values={'name': 'koji',
                                          'strict': False,
                                          'self': mock.ANY})
        self.assertEqual(rv, 1)

    def test_getPackageID_strict(self):
        with self.assertRaises(koji.GenericError) as cm:
            kojihub.RootExports().getPackageID('invalidpkg', strict=True)
        self.assertLastQueryEqual(tables=['package'],
                                  columns=['id'],
                                  clauses=['name=%(name)s'],
                                  values={'name': 'invalidpkg',
                                          'strict': True,
                                          'self': mock.ANY})
        self.assertEqual(cm.exception.args[0],
                         'Invalid package name: invalidpkg')

    def test_getPackageID_None(self):
        rv = kojihub.RootExports().getPackageID('invalidpkg')
        self.assertEqual(len(self.queries), 1)
        self.assertLastQueryEqual(tables=['package'],
                                  columns=['id'],
                                  clauses=['name=%(name)s'],
                                  values={'name': 'invalidpkg',
                                          'strict': False,
                                          'self': mock.ANY})
        self.assertIsNone(rv)
