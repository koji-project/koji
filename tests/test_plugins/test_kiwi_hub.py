import mock
import unittest

import koji
import kojihub
from plugins.hub import kiwi

class TestKiwiHub(unittest.TestCase):
    def setUp(self):
        self.context = mock.patch('plugins.hub.kiwi.context').start()
        self.context.session.assertPerm = mock.MagicMock()
        kojihub.get_build_target = mock.MagicMock()
        kojihub.get_build_target.return_value = {'id': 1, 'name': 'target'}
        kojihub.make_task = mock.MagicMock()
        kojihub.make_task.return_value = 1

    def tearDown(self):
        mock.patch.stopall()

    def test_kiwi_basic(self):
        kiwi.kiwiBuild('target', ['arch1', 'arch2'], 'desc_url', 'desc_path')
        kojihub.get_build_target.assert_called_once_with('target', strict=True)
        kojihub.make_task.assert_called_once_with(
            'kiwiBuild',
            [
                'target',
                ['arch1', 'arch2'],
                'desc_url',
                'desc_path',
                {'use_buildroot_repo': True}
            ],
            channel='image'
        )

    def test_nonexistent_target(self):
        kojihub.get_build_target.side_effect = koji.GenericError
        with self.assertRaises(koji.GenericError):
            kiwi.kiwiBuild('target', ['arch1', 'arch2'], 'desc_url', 'desc_path')
        kojihub.get_build_target.assert_called_once_with('target', strict=True)

    def test_invalid_arches(self):
        for arch_set in ['arch1,arch2', 'ěšč']:
            with self.assertRaises(koji.GenericError):
                kiwi.kiwiBuild('target', arch_set, 'desc_url', 'desc_path')

        with self.assertRaises(TypeError):
            kiwi.kiwiBuild('target', ["arch1", None], 'desc_url', 'desc_path')

        with self.assertRaises(AttributeError):
            kiwi.kiwiBuild('target', None, 'desc_url', 'desc_path')

    def test_all_options(self):
        kiwi.kiwiBuild(
            'target',
            ['arch1', 'arch2'],
            'desc_url',
            'desc_path',
            optional_arches=['arch1'],
            profile='profile',
            scratch=True,
            priority=10,
            make_prep=True,
            repos=['repo1', 'repo2'],
            release='release',
            type='type',
            type_attr=['type_attr'],
            result_bundle_name_format='name_format',
            use_buildroot_repo=True,
            version='version',
            repo_releasever='relver'
        )
        kojihub.make_task.assert_called_once_with(
            'kiwiBuild',
            [
                'target',
                ['arch1', 'arch2'],
                'desc_url',
                'desc_path',
                {
                    'scratch': True,
                    'profile': 'profile',
                    'version': 'version',
                    'release': 'release',
                    'optional_arches': ['arch1'],
                    'repos': ['repo1', 'repo2'],
                    'repo_releasever': 'relver',
                    'make_prep': True,
                    'type': 'type',
                    'use_buildroot_repo': True,
                    'type_attr': ['type_attr'],
                    'result_bundle_name_format': 'name_format'
                },
            ],
            channel='image',
            priority=koji.PRIO_DEFAULT + 10,
        )

