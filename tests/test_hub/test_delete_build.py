import mock
import time
import unittest
from collections import defaultdict

import koji
import kojihub


class TestDeleteBuild(unittest.TestCase):

    @mock.patch('kojihub.kojihub.context')
    @mock.patch('kojihub.kojihub.get_build')
    def test_delete_build_raise_error(self, build, context):
        context.session.assertPerm = mock.MagicMock()
        references = ['tags', 'rpms', 'archives', 'component_of']
        for ref in references:
            context = mock.MagicMock()
            context.session.return_value = context

            with mock.patch('kojihub.kojihub.build_references') as refs:
                retval = defaultdict(dict)
                retval[ref] = True
                refs.return_value = retval
                with self.assertRaises(koji.GenericError):
                    kojihub.delete_build(build='', strict=True)

    @mock.patch('kojihub.kojihub.context')
    @mock.patch('kojihub.kojihub.get_build')
    def test_delete_build_return_false(self, build, context):
        context.session.assertPerm = mock.MagicMock()
        references = ['tags', 'rpms', 'archives', 'component_of']
        for ref in references:
            context = mock.MagicMock()
            context.session.return_value = context

            with mock.patch('kojihub.kojihub.build_references') as refs:
                retval = defaultdict(dict)
                retval[ref] = True
                refs.return_value = retval
                assert kojihub.delete_build(build='', strict=False) is False

    @mock.patch('kojihub.kojihub.context')
    @mock.patch('kojihub.kojihub.get_build')
    def test_delete_build_check_last_used_raise_error(self, build, context):
        context.session.assertPerm = mock.MagicMock()
        references = ['tags', 'rpms', 'archives', 'component_of', 'last_used']
        for ref in references:
            context = mock.MagicMock()
            context.session.return_value = context

            with mock.patch('kojihub.kojihub.build_references') as refs:
                retval = defaultdict(dict)
                if ref == 'last_used':
                    retval[ref] = time.time() + 100
                    refs.return_value = retval
                    self.assertFalse(kojihub.delete_build(build='', strict=False))

    @mock.patch('kojihub.kojihub.get_user')
    @mock.patch('kojihub.kojihub._delete_build')
    @mock.patch('kojihub.kojihub.build_references')
    @mock.patch('kojihub.kojihub.context')
    @mock.patch('kojihub.kojihub.get_build')
    def test_delete_build_lazy_refs(self, build, context, buildrefs, _delete, get_user):
        '''Test that we can handle lazy return from build_references'''
        get_user.return_value = {'authtype': 2, 'id': 1, 'krb_principal': None,
                                 'krb_principals': [], 'name': 'kojiadmin', 'status': 0,
                                 'usertype': 0}
        context.session.assertPerm = mock.MagicMock()
        buildrefs.return_value = {'tags': []}
        binfo = {'id': 'BUILD ID', 'state': koji.BUILD_STATES['COMPLETE'],
                 'nvr': 'test_nvr-3.3-20.el8'}
        build.return_value = binfo
        kojihub.delete_build(build=binfo, strict=True)

        # no build refs, so we should have called _delete_build
        _delete.assert_called_with(binfo)
