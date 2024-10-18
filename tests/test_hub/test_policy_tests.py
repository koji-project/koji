from unittest import mock
import unittest

import koji
import kojihub


class TestBasicTests(unittest.TestCase):

    def test_operation_test(self):
        obj = kojihub.OperationTest('operation foo*')
        self.assertFalse(obj.run({'operation': 'FOOBAR'}))
        self.assertTrue(obj.run({'operation': 'foobar'}))

    @mock.patch('kojihub.kojihub.policy_get_pkg')
    def test_package_test(self, policy_get_pkg):
        obj = kojihub.PackageTest('package foo*')
        policy_get_pkg.return_value = {'name': 'mypackage'}
        self.assertFalse(obj.run({}))
        policy_get_pkg.return_value = {'name': 'foobar'}
        self.assertTrue(obj.run({}))

    @mock.patch('kojihub.kojihub.policy_get_version')
    def test_version_test(self, policy_get_version):
        obj = kojihub.VersionTest('version 1.2.*')
        policy_get_version.return_value = '0.0.1'
        self.assertFalse(obj.run({}))
        policy_get_version.return_value = '1.2.1'
        self.assertTrue(obj.run({}))

    @mock.patch('kojihub.kojihub.policy_get_release')
    def test_release_test(self, policy_get_release):
        obj = kojihub.ReleaseTest('release 1.2.*')
        policy_get_release.return_value = '0.0.1'
        self.assertFalse(obj.run({}))
        policy_get_release.return_value = '1.2.1'
        self.assertTrue(obj.run({}))

    @mock.patch('kojihub.kojihub.policy_get_pkg')
    def test_new_package_test(self, policy_get_pkg):
        obj = kojihub.NewPackageTest('is_new_package')
        policy_get_pkg.return_value = {'name': 'mypackage', 'id': 42}
        self.assertFalse(obj.run({}))
        policy_get_pkg.return_value = {'name': 'foobar', 'id': None}
        self.assertTrue(obj.run({}))

    def test_skip_tag_test(self):
        obj = kojihub.kojihub.SkipTagTest('skip_tag')
        data = {'skip_tag': True}
        self.assertTrue(obj.run(data))
        data = {'skip_tag': False}
        self.assertFalse(obj.run(data))
        data = {'skip_tag': None}
        self.assertFalse(obj.run(data))
        data = {}
        self.assertFalse(obj.run(data))


class TestPolicyGetUser(unittest.TestCase):

    def setUp(self):
        self.get_user = mock.patch('kojihub.kojihub.get_user').start()
        self.context = mock.patch('kojihub.kojihub.context').start()

    def tearDown(self):
        mock.patch.stopall()

    def test_get_user_specified(self):
        self.get_user.return_value = 'USER'
        result = kojihub.policy_get_user({'user_id': 42})
        self.assertEqual(result, 'USER')
        self.get_user.assert_called_once_with(42)

    def test_get_no_user(self):
        self.context.session.logged_in = False
        result = kojihub.policy_get_user({})
        self.assertEqual(result, None)
        self.get_user.assert_not_called()

    def test_get_logged_in_user(self):
        self.context.session.logged_in = True
        self.context.session.user_id = 99
        self.get_user.return_value = 'USER'
        result = kojihub.policy_get_user({})
        self.assertEqual(result, 'USER')
        self.get_user.assert_called_once_with(99)

    def test_get_user_specified_with_login(self):
        self.get_user.return_value = 'USER'
        self.context.session.logged_in = True
        self.context.session.user_id = 99
        result = kojihub.policy_get_user({'user_id': 42})
        self.assertEqual(result, 'USER')
        self.get_user.assert_called_once_with(42)


class TestPolicyGetCGs(unittest.TestCase):

    def setUp(self):
        self.get_build = mock.patch('kojihub.kojihub.get_build').start()
        self.list_rpms = mock.patch('kojihub.kojihub.list_rpms').start()
        self.list_archives = mock.patch('kojihub.kojihub.list_archives').start()
        self.get_buildroot = mock.patch('kojihub.kojihub.get_buildroot').start()
        self.lookup_name = mock.patch('kojihub.kojihub.lookup_name').start()

    def tearDown(self):
        mock.patch.stopall()

    def _fakebr(self, br_id, strict):
        self.assertEqual(strict, True)
        return {
            'cg_name': self._cgname(br_id),
            'repo_create_event_id': 1234,
        }

    def _cgname(self, br_id):
        if br_id is None:
            return None
        return 'cg for br %s' % br_id

    def test_policy_get_cg_from_brs(self):
        self.get_build.return_value = {'id': 42}
        br1 = [1, 1, 1, 2, 3, 4, 5, 5]
        br2 = [2, 2, 7, 7, 8, 8, 9, 9, None]
        self.list_rpms.return_value = [{'buildroot_id': n} for n in br1]
        self.list_archives.return_value = [{'buildroot_id': n} for n in br2]
        self.get_buildroot.side_effect = self._fakebr
        # let's see...
        result = kojihub.policy_get_cgs({'build': 'NVR'})
        expect = set([self._cgname(n) for n in br1 + br2])
        self.assertEqual(result, expect)
        self.list_rpms.assert_called_once_with(buildID=42)
        self.list_archives.assert_called_once_with(buildID=42)
        self.get_build.assert_called_once_with('NVR', strict=True)

    def test_policy_get_cg_from_cgs(self):
        data = {
            'cg_list': [1, 1, 1, 2, 2, 2, 3, 3, 3],
            'build': 'whatever',
            'buildroots': [],
        }

        def my_lookup_name(table, info, strict=False, create=False):
            self.assertEqual(strict, True)
            self.assertEqual(create, False)
            self.assertEqual(table, 'content_generator')
            return {'id': info, 'name': "cg %i" % info}
        self.lookup_name.side_effect = my_lookup_name

        result = kojihub.policy_get_cgs(data)
        expect = set(['cg %i' % c for c in data['cg_list']])
        self.assertEqual(result, expect)
        self.get_build.assert_not_called()
        self.get_buildroot.assert_not_called()

    def test_policy_get_cg_nobuild(self):
        result = kojihub.policy_get_cgs({'package': 'foobar'})
        self.get_build.assert_not_called()
        self.assertEqual(result, set())


class TestBuildTagTest(unittest.TestCase):

    def setUp(self):
        self.get_build = mock.patch('kojihub.kojihub.get_build').start()
        self.get_tag = mock.patch('kojihub.kojihub.get_tag').start()
        self.list_rpms = mock.patch('kojihub.kojihub.list_rpms').start()
        self.list_archives = mock.patch('kojihub.kojihub.list_archives').start()
        self.get_buildroot = mock.patch('kojihub.kojihub.get_buildroot').start()

    def tearDown(self):
        mock.patch.stopall()

    def test_build_tag_given(self):
        obj = kojihub.BuildTagTest('buildtag foo*')
        data = {'build_tag': 'TAGINFO'}
        self.get_tag.return_value = {'name': 'foo-3.0-build'}
        self.assertTrue(obj.run(data))
        self.list_rpms.assert_not_called()
        self.list_archives.assert_not_called()
        self.get_buildroot.assert_not_called()
        self.get_tag.assert_called_once_with('TAGINFO', event='auto', strict=True)

    def test_build_tag_given_alt(self):
        obj = kojihub.BuildTagTest('buildtag foo*')
        data = {'build_tag': 'TAGINFO'}
        self.get_tag.return_value = {'name': 'foo-3.0-build'}
        self.assertTrue(obj.run(data))
        self.get_tag.return_value = {'name': 'bar-1.2-build'}
        self.assertFalse(obj.run(data))

        obj = kojihub.BuildTagTest('buildtag foo-3* foo-4* fake-*')
        data = {'build_tag': 'TAGINFO', 'build': 'BUILDINFO'}
        self.get_tag.return_value = {'name': 'foo-4.0-build'}
        self.assertTrue(obj.run(data))
        self.get_tag.return_value = {'name': 'foo-3.0.1-build'}
        self.assertTrue(obj.run(data))
        self.get_tag.return_value = {'name': 'fake-0.99-build'}
        self.assertTrue(obj.run(data))
        self.get_tag.return_value = {'name': 'foo-2.1'}
        self.assertFalse(obj.run(data))
        self.get_tag.return_value = {'name': 'foo-5.5-alt'}
        self.assertFalse(obj.run(data))
        self.get_tag.return_value = {'name': 'baz-2-candidate'}
        self.assertFalse(obj.run(data))

        self.list_rpms.assert_not_called()
        self.list_archives.assert_not_called()
        self.get_buildroot.assert_not_called()

    def _fakebr(self, br_id, strict=None):
        return {
            'tag_name': self._brtag(br_id),
            'repo_create_event_id': 123,
        }

    def _brtag(self, br_id):
        if br_id == '':
            return None
        return br_id

    def test_build_tag_from_build(self):
        # Note: the match is for any buildroot tag
        brtags = [None, '', 'a', 'b', 'c', 'd', 'not-foo-5', 'foo-3-build']
        self.list_rpms.return_value = [{'buildroot_id': x} for x in brtags]
        self.list_archives.return_value = [{'buildroot_id': x} for x in brtags]
        self.get_buildroot.side_effect = self._fakebr

        obj = kojihub.BuildTagTest('buildtag foo-*')
        data = {'build': 'BUILDINFO'}
        self.assertTrue(obj.run(data))

        obj = kojihub.BuildTagTest('buildtag bar-*')
        data = {'build': 'BUILDINFO'}
        self.assertFalse(obj.run(data))

        self.get_tag.assert_has_calls([
            mock.call('a', event=123, strict=True),
            mock.call('b', event=123, strict=True),
            mock.call('c', event=123, strict=True),
            mock.call('d', event=123, strict=True),
            mock.call('not-foo-5', event=123, strict=True),
            mock.call('foo-3-build', event=123, strict=True),
        ], any_order=True)

    def test_build_tag_no_info(self):
        obj = kojihub.BuildTagTest('buildtag foo*')
        data = {}
        self.assertFalse(obj.run(data))
        self.list_rpms.assert_not_called()
        self.list_archives.assert_not_called()
        self.get_buildroot.assert_not_called()


class TestHasTagTest(unittest.TestCase):

    def setUp(self):
        self.list_tags = mock.patch('kojihub.kojihub.list_tags').start()

    def tearDown(self):
        mock.patch.stopall()

    def test_build_not_in_data(self):
        data = {'key': 'test'}
        obj = kojihub.HasTagTest('hastag *-candidate')
        self.assertFalse(obj.run(data))
        self.list_tags.assert_not_called()

    def test_has_tag_simple(self):
        obj = kojihub.HasTagTest('hastag *-candidate')
        tags = ['foo-1.0', 'foo-2.0', 'foo-3.0-candidate']
        self.list_tags.return_value = [{'name': t} for t in tags]
        data = {'build': 'NVR'}
        self.assertTrue(obj.run(data))
        self.list_tags.assert_called_once_with(build='NVR')

        # check no match case
        self.list_tags.return_value = []
        self.assertFalse(obj.run(data))


class TestBuildTagInheritsFromTest(unittest.TestCase):

    def setUp(self):
        self.policy_get_build_tags = mock.patch('kojihub.kojihub.policy_get_build_tags').start()
        self.readFullInheritance = mock.patch('kojihub.kojihub.readFullInheritance').start()

    def tearDown(self):
        mock.patch.stopall()

    def test_wrong_test_name(self):
        obj = kojihub.BuildTagInheritsFromTest('buildtag_inherits_from_type foo*')
        data = {}
        self.policy_get_build_tags.return_value = {None}
        with self.assertRaises(AssertionError):
            obj.run(data)

    def test_no_buildtag(self):
        obj = kojihub.BuildTagInheritsFromTest('buildtag_inherits_from foo*')
        data = {}
        self.policy_get_build_tags.return_value = {None}
        self.assertFalse(obj.run(data))
        self.policy_get_build_tags.assert_called_once_with(data, taginfo=True)
        self.readFullInheritance.assert_not_called()

    def test_no_inheritance(self):
        obj = kojihub.BuildTagInheritsFromTest('buildtag_inherits_from foo*')
        data = {}
        self.policy_get_build_tags.return_value = [{'id': 123, 'tag_name': 'foox'}]
        self.readFullInheritance.return_value = []
        self.assertFalse(obj.run(data))
        self.policy_get_build_tags.assert_called_once_with(data, taginfo=True)
        self.readFullInheritance.assert_called_once_with(123, event=None)

    def test_inheritance_pass(self):
        obj = kojihub.BuildTagInheritsFromTest('buildtag_inherits_from foo*')
        data = {}
        self.policy_get_build_tags.return_value = [{'id': 123, 'tag_name': 'wrong'}]
        self.readFullInheritance.return_value = [
            {'name': 'still-wrong'},
            {'name': 'foox'},
        ]
        self.assertTrue(obj.run(data))
        self.policy_get_build_tags.assert_called_once_with(data, taginfo=True)
        self.readFullInheritance.assert_called_once_with(123, event=None)

    def test_inheritance_fail(self):
        obj = kojihub.BuildTagInheritsFromTest('buildtag_inherits_from foo*')
        data = {}
        self.policy_get_build_tags.return_value = [{'id': 123, 'tag_name': 'wrong'}]
        self.readFullInheritance.return_value = [
            {'name': 'still-wrong'},
            {'name': 'still-still-wrong'},
        ]
        self.assertFalse(obj.run(data))
        self.policy_get_build_tags.assert_called_once_with(data, taginfo=True)
        self.readFullInheritance.assert_called_once_with(123, event=None)


class TestBuildTypeTest(unittest.TestCase):
    def setUp(self):
        self.get_build_type = mock.patch('kojihub.kojihub.get_build_type').start()
        self.get_build = mock.patch('kojihub.kojihub.get_build').start()

    def tearDown(self):
        mock.patch.stopall()

    def test_invalid(self):
        binfo = {'id': 1, 'name': 'nvr-1-2'}
        self.get_build.return_value = binfo
        self.get_build_type.return_value = {'rpm': None}
        obj = kojihub.BuildTypeTest('buildtype foo-*')
        data = {'build': 'nvr-1-2'}
        self.assertFalse(obj.run(data))
        self.get_build_type.assert_called_once_with(binfo)

    def test_valid(self):
        binfo = {'id': 1, 'name': 'nvr-1-2'}
        self.get_build.return_value = binfo
        self.get_build_type.return_value = {'rpm': None}
        obj = kojihub.BuildTypeTest('buildtype rpm')
        data = {'build': 'nvr-1-2'}
        self.assertTrue(obj.run(data))
        self.get_build_type.assert_called_once_with(binfo)

    def test_prepopulated(self):
        # self.get_build.return_value = {'id': 1, 'name': 'nvr-1-2'}
        self.get_build_type.return_value = {'rpm': None}
        obj = kojihub.BuildTypeTest('buildtype rpm')
        data = {'build': 123, 'btypes': set(['rpm'])}
        self.assertTrue(obj.run(data))
        self.get_build_type.assert_not_called()


class TestImportedTest(unittest.TestCase):
    def setUp(self):
        self.list_rpms = mock.patch('kojihub.kojihub.list_rpms').start()
        self.list_archives = mock.patch('kojihub.kojihub.list_archives').start()
        self.get_build = mock.patch('kojihub.kojihub.get_build').start()

    def tearDown(self):
        mock.patch.stopall()

    def test_no_build(self):
        self.get_build.side_effect = koji.GenericError
        obj = kojihub.ImportedTest('imported - no build')
        data = {}
        with self.assertRaises(koji.GenericError) as cm:
            obj.run(data)
        self.assertEqual(cm.exception.args[0],
                         'policy data must contain a build')
        self.get_build.assert_not_called()

    def test_invalid_build(self):
        self.get_build.side_effect = koji.GenericError
        obj = kojihub.ImportedTest('imported - invalid build')
        data = {'build': 'nvr-1-1'}
        with self.assertRaises(koji.GenericError):
            obj.run(data)
        self.get_build.assert_called_once_with('nvr-1-1', strict=True)

    def test_imported_rpm(self):
        binfo = {'id': 1, 'name': 'nvr-1-1'}
        self.get_build.return_value = binfo
        self.list_rpms.return_value = [{'id': 1, 'buildroot_id': None}]
        obj = kojihub.ImportedTest('imported - imported rpm')
        data = {'build': 'nvr-1-1'}
        self.assertTrue(obj.run(data))
        self.get_build.assert_called_once_with('nvr-1-1', strict=True)
        self.list_rpms.assert_called_once_with(buildID=1)
        self.list_archives.assert_not_called()

    def test_imported_archive(self):
        binfo = {'id': 1, 'name': 'nvr-1-1'}
        self.get_build.return_value = binfo
        self.list_rpms.return_value = [{'id': 1, 'buildroot_id': 1}]
        self.list_archives.return_value = [{'id': 1, 'buildroot_id': None}]
        obj = kojihub.ImportedTest('imported - imported archive')
        data = {'build': 'nvr-1-1'}
        self.assertTrue(obj.run(data))
        self.get_build.assert_called_once_with('nvr-1-1', strict=True)
        self.list_rpms.assert_called_once_with(buildID=1)
        self.list_archives.assert_called_once_with(buildID=1)

    def test_false(self):
        binfo = {'id': 1, 'name': 'nvr-1-1'}
        self.get_build.return_value = binfo
        self.list_rpms.return_value = [{'id': 1, 'buildroot_id': 1}]
        self.list_archives.return_value = [{'id': 1, 'buildroot_id': 2}]
        obj = kojihub.ImportedTest('imported - false test')
        data = {'build': 'nvr-1-1'}
        self.assertFalse(obj.run(data))
        self.get_build.assert_called_once_with('nvr-1-1', strict=True)
        self.list_rpms.assert_called_once_with(buildID=1)
        self.list_archives.assert_called_once_with(buildID=1)


class TestPolicyGetVersion(unittest.TestCase):
    def setUp(self):
        self.get_build = mock.patch('kojihub.kojihub.get_build').start()

    def tearDown(self):
        mock.patch.stopall()

    def test_policy_version(self):
        data = {'version': 123}
        rv = kojihub.policy_get_version(data)
        self.assertEqual(rv, 123)
        self.get_build.assert_not_called()

    def test_policy_build(self):
        data = {'build': 123}
        buildinfo = {'id': 123, 'version': 100}
        self.get_build.return_value = buildinfo
        rv = kojihub.policy_get_version(data)
        self.assertEqual(rv, 100)
        self.get_build.assert_called_once_with(data['build'], strict=True)

    def test_policy_version_error(self):
        data = {'release': 123}
        with self.assertRaises(koji.GenericError) as cm:
            kojihub.policy_get_version(data)
        self.assertEqual("policy requires version data", str(cm.exception))
        self.get_build.assert_not_called()


class TestPolicyGetRelease(unittest.TestCase):
    def setUp(self):
        self.get_build = mock.patch('kojihub.kojihub.get_build').start()

    def tearDown(self):
        mock.patch.stopall()

    def test_policy_release(self):
        data = {'release': 123}
        rv = kojihub.policy_get_release(data)
        self.assertEqual(rv, 123)
        self.get_build.assert_not_called()

    def test_policy_build(self):
        data = {'build': 123}
        buildinfo = {'id': 123, 'release': 100}
        self.get_build.return_value = buildinfo
        rv = kojihub.policy_get_release(data)
        self.assertEqual(rv, 100)
        self.get_build.assert_called_once_with(data['build'], strict=True)

    def test_policy_release_error(self):
        data = {'version': 123}
        with self.assertRaises(koji.GenericError) as cm:
            kojihub.policy_get_release(data)
        self.assertEqual("policy requires release data", str(cm.exception))
        self.get_build.assert_not_called()


class TestPolicyGetPkg(unittest.TestCase):
    def setUp(self):
        self.get_build = mock.patch('kojihub.kojihub.get_build').start()
        self.lookup_package = mock.patch('kojihub.kojihub.lookup_package').start()

    def tearDown(self):
        mock.patch.stopall()

    def test_no_such_pkg(self):
        data = {'package': 123}
        self.lookup_package.return_value = None
        with self.assertRaises(koji.GenericError) as cm:
            kojihub.policy_get_pkg(data)
        self.assertEqual(f"No such package: {data['package']}", str(cm.exception))
        self.lookup_package.assert_called_once_with(data['package'], strict=False)
        self.get_build.assert_not_called()

    def test_with_pkg_not_found_lookup_pkg(self):
        data = {'package': 'test-pkg'}
        self.lookup_package.return_value = None
        rv = kojihub.policy_get_pkg(data)
        self.assertEqual(rv, {'id': None, 'name': data['package']})
        self.lookup_package.assert_called_once_with(data['package'], strict=False)
        self.get_build.assert_not_called()

    def test_with_pkg(self):
        data = {'package': 'test-pkg'}
        self.lookup_package.return_value = {'id': 1, 'name': data['package']}
        rv = kojihub.policy_get_pkg(data)
        self.assertEqual(rv, {'id': 1, 'name': data['package']})
        self.lookup_package.assert_called_once_with(data['package'], strict=False)
        self.get_build.assert_not_called()

    def test_build(self):
        data = {'build': 123}
        buildinfo = {'id': 123, 'package_id': 1, 'name': 'test-pkg'}
        self.get_build.return_value = buildinfo
        rv = kojihub.policy_get_pkg(data)
        self.assertEqual(rv, {'id': buildinfo['package_id'], 'name': buildinfo['name']})
        self.lookup_package.assert_not_called()
        self.get_build.assert_called_once_with(data['build'], strict=True)

    def test_wrong_data_key(self):
        data = {'id': 123}
        with self.assertRaises(koji.GenericError) as cm:
            kojihub.policy_get_pkg(data)
        self.assertEqual("policy requires package data", str(cm.exception))
        self.lookup_package.assert_not_called()
        self.get_build.assert_not_called()


class TestVolumeTest(unittest.TestCase):
    def setUp(self):
        self.lookup_name = mock.patch('kojihub.kojihub.lookup_name').start()
        self.get_build = mock.patch('kojihub.kojihub.get_build').start()

    def tearDown(self):
        mock.patch.stopall()

    def test_volume_data(self):
        self.lookup_name.return_value = {'id': 159, 'name': 'test-volume'}
        obj = kojihub.VolumeTest('volume - volume data')
        data = {'volume': 'test-volume'}
        obj.run(data)
        self.get_build.assert_not_called()
        self.lookup_name.assert_called_once_with('volume', data['volume'], strict=False)

    def test_build_data(self):
        buildinfo = {'volume_id': 5, 'volume_name': 'test-volume', 'id': 2}
        self.get_build.return_value = buildinfo
        obj = kojihub.VolumeTest('volume - build data')
        data = {'build': 'nvr-1-1'}
        obj.run(data)
        self.get_build.assert_called_once_with(data['build'])
        self.lookup_name.assert_not_called()

    def test_not_volinfo(self):
        data = {'key': 'test'}
        obj = kojihub.VolumeTest('volume - volume none')
        self.assertFalse(obj.run(data))
        self.get_build.assert_not_called()
        self.lookup_name.assert_not_called()


class TestTagTest(unittest.TestCase):
    def setUp(self):
        self.get_tag = mock.patch('kojihub.kojihub.get_tag').start()

    def tearDown(self):
        mock.patch.stopall()

    def test_tag_is_none(self):
        data = {'key': 'test'}
        obj = kojihub.TagTest('tagtest - tag none')
        self.assertFalse(obj.run(data))
        self.get_tag.assert_not_called()

    def test_taginfo_is_none(self):
        self.get_tag.return_value = None
        data = {'tag': 'test-tag'}
        obj = kojihub.TagTest('tagtest - taginfo none')
        self.assertFalse(obj.run(data))
        self.get_tag.assert_called_once_with(data['tag'], strict=False)

    def test_taginfo_valid(self):
        data = {'tag': 'test-tag'}
        self.get_tag.return_value = {'name': data['tag']}
        obj = kojihub.TagTest('tagtest - taginfo none')
        self.assertIsNotNone(obj.run(data))
        self.get_tag.assert_called_once_with(data['tag'], strict=False)


class FromTagTest(unittest.TestCase):
    def setUp(self):
        self.get_tag = mock.patch('kojihub.kojihub.get_tag').start()

    def tearDown(self):
        mock.patch.stopall()

    def test_tag_is_none(self):
        data = {'key': 'test'}
        obj = kojihub.FromTagTest('fromtagtest - tag none')
        self.assertIsNone(obj.get_tag(data))
        self.get_tag.assert_not_called()

    def test_valid(self):
        data = {'fromtag': 'test-tag'}
        self.get_tag.return_value = {'name': data['fromtag']}
        obj = kojihub.FromTagTest('fromtagtest - tag none')
        self.assertEqual(obj.get_tag(data), {'name': data['fromtag']})
        self.get_tag.assert_called_once_with(data['fromtag'], strict=False)


class CGMatchAnyTest(unittest.TestCase):
    def setUp(self):
        self.policy_get_cgs = mock.patch('kojihub.kojihub.policy_get_cgs').start()
        self.multi_fnmatch = mock.patch('kojihub.kojihub.multi_fnmatch').start()

    def tearDown(self):
        mock.patch.stopall()

    def test_cgname_is_none(self):
        data = {'key': 'test'}
        self.policy_get_cgs.return_value = [None]
        obj = kojihub.CGMatchAnyTest('cgmatchanytest - cg name none')
        self.assertFalse(obj.run(data))

    def test_cg_name_true(self):
        data = {'key': 'test'}
        self.policy_get_cgs.return_value = ['cgname']
        self.multi_fnmatch.return_value = True
        obj = kojihub.CGMatchAnyTest('cgmatchanytest - cg name true')
        self.assertTrue(obj.run(data))


class CGMatchAllTest(unittest.TestCase):
    def setUp(self):
        self.policy_get_cgs = mock.patch('kojihub.kojihub.policy_get_cgs').start()
        self.multi_fnmatch = mock.patch('kojihub.kojihub.multi_fnmatch').start()

    def tearDown(self):
        mock.patch.stopall()

    def test_cgs_none(self):
        data = {'key': 'test'}
        self.policy_get_cgs.return_value = []
        obj = kojihub.CGMatchAllTest('cgmatchalltest - cg name none')
        self.assertFalse(obj.run(data))

    def test_cgname_is_none(self):
        data = {'key': 'cgname'}
        self.policy_get_cgs.return_value = [None]
        obj = kojihub.CGMatchAllTest('cgmatchalltest - cg name none')
        self.assertFalse(obj.run(data))

    def test_cg_name_all_true(self):
        data = {'key': 'cgname'}
        self.policy_get_cgs.return_value = ['cgname']
        self.multi_fnmatch.return_value = True
        obj = kojihub.CGMatchAllTest('cgmatchalltest - cg name true')
        self.assertTrue(obj.run(data))

    def test_cg_name_not_found(self):
        data = {'key': 'cgname'}
        self.policy_get_cgs.return_value = ['cgname']
        self.multi_fnmatch.return_value = False
        obj = kojihub.CGMatchAllTest('cgmatchalltest - cg name true')
        self.assertFalse(obj.run(data))


class UserTest(unittest.TestCase):
    def setUp(self):
        self.policy_get_user = mock.patch('kojihub.kojihub.policy_get_user').start()

    def tearDown(self):
        mock.patch.stopall()

    def test_not_user(self):
        data = {'user': 'username'}
        self.policy_get_user.return_value = None
        obj = kojihub.UserTest('usertest - not user')
        self.assertFalse(obj.run(data))

    def test_valid(self):
        data = {'user': 'username'}
        self.policy_get_user.return_value = {'name': 'username'}
        obj = kojihub.UserTest('usertest - valid')
        self.assertIsNotNone(obj.run(data))


class IsBuildOwnerTest(unittest.TestCase):
    def setUp(self):
        self.policy_get_user = mock.patch('kojihub.kojihub.policy_get_user').start()
        self.get_build = mock.patch('kojihub.kojihub.get_build').start()
        self.get_user = mock.patch('kojihub.kojihub.get_user').start()
        self.get_user_groups = mock.patch('kojihub.kojihub.get_user_groups').start()

    def tearDown(self):
        mock.patch.stopall()

    def test_not_user(self):
        data = {'build': 1}
        self.get_build.return_value = {'build_id': data['build'], 'owner_id': 3}
        self.get_user.return_value = {'id': 3, 'name': 'username'}
        self.policy_get_user.return_value = None
        obj = kojihub.IsBuildOwnerTest('isbuildownertest - not user')
        self.assertFalse(obj.run(data))
        self.get_build.assert_called_once_with(data['build'])
        self.get_user.assert_called_once_with(3)
        self.policy_get_user.assert_called_once_with(data)
        self.get_user_groups.assert_not_called()

    def test_owner_is_user(self):
        data = {'build': 1}
        self.get_build.return_value = {'build_id': data['build'], 'owner_id': 3}
        self.get_user.return_value = {'id': 3, 'name': 'username'}
        self.policy_get_user.return_value = {'id': 3, 'name': 'username'}
        obj = kojihub.IsBuildOwnerTest('isbuildownertest - owner is user')
        self.assertTrue(obj.run(data))
        self.get_build.assert_called_once_with(data['build'])
        self.get_user.assert_called_once_with(3)
        self.policy_get_user.assert_called_once_with(data)
        self.get_user_groups.assert_not_called()

    def test_owner_is_group(self):
        data = {'build': 1}
        self.get_build.return_value = {'build_id': data['build'], 'owner_id': 3}
        self.get_user.return_value = {'id': 2, 'name': 'testuser', 'usertype': 2}
        self.policy_get_user.return_value = {'id': 3, 'name': 'username'}
        self.get_user_groups.return_value = {2: 'group_name'}
        obj = kojihub.IsBuildOwnerTest('isbuildownertest - owner group')
        self.assertTrue(obj.run(data))
        self.get_build.assert_called_once_with(data['build'])
        self.get_user.assert_called_once_with(3)
        self.policy_get_user.assert_called_once_with(data)
        self.get_user_groups.assert_called_once_with(3)

    def test_owner_false(self):
        data = {'build': 1}
        self.get_build.return_value = {'build_id': data['build'], 'owner_id': 3}
        self.get_user.return_value = {'id': 2, 'name': 'testuser', 'usertype': 1}
        self.policy_get_user.return_value = {'id': 3, 'name': 'username'}
        obj = kojihub.IsBuildOwnerTest('isbuildownertest - owner false')
        self.assertFalse(obj.run(data))
        self.get_build.assert_called_once_with(data['build'])
        self.get_user.assert_called_once_with(3)
        self.policy_get_user.assert_called_once_with(data)
        self.get_user_groups.assert_not_called()


class TestPolicyDataFromTask(unittest.TestCase):

    def setUp(self):
        self.lookup_build_target = mock.patch('kojihub.kojihub.lookup_build_target').start()
        self.lookup_build_target.return_value = {'id': 100, 'name': 'MYTARGET'}
        self.lookup_tag = mock.patch('kojihub.kojihub.lookup_tag').start()
        self.lookup_tag.return_value = {'id': 100, 'name': 'MYTAG'}

    def tearDown(self):
        mock.patch.stopall()

    GOOD = [
        # method, kwargs, expect
        ['build',
            {'src': 'git://foo', 'target': 100, 'opts': {}},
            {'source': 'git://foo', 'target': 'MYTARGET'}],
        ['build',
            {'src': 'git://foo', 'target': 100, 'opts': {'scratch': True}},
            {'source': 'git://foo', 'target': 'MYTARGET', 'scratch': True}],
        ['build', 
            {'src': 'git://foo', 'target': {'name': 'MYTARGET'}, 'opts': {}},
            {'source': 'git://foo', 'target': 'MYTARGET'}],
        ['newRepo',
            {'tag': 100},
            {'tag': 'MYTAG'}],
        ['newRepo',
            {'tag': 'MYTAG', 'src': 'should be ignored'},
            {'tag': 'MYTAG'}],
        ['rebuildSRPM',
            {'srpm': 'SRPM', 'build_tag': 100},
            {'build_tag': 'MYTAG'}],
        ['indirectionimage',
            {'opts': {'scratch': True, 'target': 100}},
            {'target': 'MYTARGET', 'scratch': True}],
    ]

    BAD = [
        # method, arglist
        ['nosuchmethod', []],
        ['build', [1,2,3,4,5,6,7,8]],  # too many args
        ['build', True],  # not a list
    ]

    def test_good(self):
        for method, kwargs, expect in self.GOOD:
            arglist = koji.encode_args(**kwargs)
            data = kojihub.policy_data_from_task_args(method, arglist)
            self.assertEqual(data, expect)

    def test_bad(self):
        # this function should be tolerant of bad parameters
        for method, arglist in self.BAD:
            data = kojihub.policy_data_from_task_args(method, arglist)
            self.assertEqual(data, {})

    def test_unexpected_exception(self):
        arglist = mock.MagicMock()
        arglist.__len__.side_effect = Exception('highly unlikely scenario')
        data = kojihub.policy_data_from_task_args('build', arglist)
        self.assertEqual(data, {})

    def test_bad_target(self):
        kwargs = {'src': 'git://foo', 'target': {}}
        arglist = koji.encode_args(**kwargs)
        data = kojihub.policy_data_from_task_args('build', arglist)
        self.assertEqual(data, {'source': 'git://foo', 'target': None})

    def test_bad_target2(self):
        kwargs = {'src': 'git://foo', 'target': 100}
        arglist = koji.encode_args(**kwargs)
        self.lookup_build_target.return_value = None
        data = kojihub.policy_data_from_task_args('build', arglist)
        self.assertEqual(data, {'source': 'git://foo', 'target': None})

    def test_bad_tag(self):
        kwargs = {'tag': 100}
        arglist = koji.encode_args(**kwargs)
        self.lookup_tag.side_effect = koji.GenericError('...')
        data = kojihub.policy_data_from_task_args('newRepo', arglist)
        self.assertEqual(data, {})

    def test_bad_build_tag(self):
        kwargs = {'srpm': 'SRPM', 'build_tag': 100}
        arglist = koji.encode_args(**kwargs)
        self.lookup_tag.side_effect = koji.GenericError('...')
        data = kojihub.policy_data_from_task_args('rebuildSRPM', arglist)
        self.assertEqual(data, {})


# the end
