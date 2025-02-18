from unittest import mock
import tempfile
import os
import unittest

import koji
# inject builder data
from tests.test_builder.loadkojid import kojid
import __main__
__main__.BuildRoot = kojid.BuildRoot
__main__.BaseBuildTask = kojid.BaseBuildTask
__main__.BuildImageTask = kojid.BuildImageTask
__main__.SCM = kojid.SCM

from plugins.builder import kiwi


class TestKiwiBuildTask(unittest.TestCase):
    def SCM(self, *args, **kwargs):
        scm = mock.MagicMock()
        scm.assert_allowed = mock.MagicMock()
        self.scm.append(scm)
        return scm

    def setUp(self):
        self.scm = []
        self.session = mock.MagicMock()
        self.options = mock.MagicMock()
        self.options.allowed_scms = 'allowed_scms'
        self.options.allowed_scms_use_config = False
        self.options.allowed_scms_use_policy = True
        kiwi.SCM = mock.MagicMock(side_effect=self.SCM)
        koji.ensuredir = mock.MagicMock()
        self.task = kiwi.KiwiBuildTask(123, 'kiwiBuild', {}, self.session, self.options)

    def test_get_nrvp_invalid_xml(self):
        # missing file
        with self.assertRaises(koji.GenericError):
            self.task.get_nvrp('/dev/null/non_existent_path')

        # empty file
        with tempfile.NamedTemporaryFile(delete=False) as fp:
            fp.write(b'')
            fp.close()
            with self.assertRaises(koji.GenericError):
                self.task.get_nvrp(fp.name)
            os.unlink(fp.name)

        # empty xml
        with tempfile.NamedTemporaryFile(delete=False) as fp:
            fp.write(b'<?xml version="1.0"?><test></test>')
            fp.close()
            with self.assertRaises(koji.GenericError):
                self.task.get_nvrp(fp.name)
            os.unlink(fp.name)

    def test_get_nrvp_correct(self):
        # minimal correct xml
        with tempfile.NamedTemporaryFile(delete=False) as fp:
            fp.write(b'''<?xml version="1.0" encoding="utf-8"?>
                    <image schemaversion="7.4" name="Fedora-34.0_disk">
                        <profiles>
                            <profile name="Base" description="Base System"
                                     import="true" image="true"/>
                        </profiles>
                        <preferences>
                            <version>1.0.0</version>
                        </preferences>
                    </image>
            ''')
            fp.close()
            name, version, profile = self.task.get_nvrp(fp.name)
            self.assertEqual(name, 'Fedora-34.0_disk')
            self.assertEqual(version, '1.0.0')
            self.assertEqual(profile, 'Base')
            os.unlink(fp.name)

    def test_handler_correct(self, arches=None):
        if arches is None:
            arches = ['arch1', 'arch2']
        self.session.getBuildTarget.return_value = {
            'id': 1,
            'name': 'target',
            'build_tag': 123,
            'build_tag_name': 'build_tag',
            'dest_tag': 321,
            'dest_tag_name': 'dest_tag'
        }
        self.task.getRepo = mock.MagicMock()
        self.task.getRepo.return_value = {
            'create_event': 59911321,
            'create_ts': 1724763098.15199,
            'creation_time': '2024-08-27 12:51:38.151991',
            'dist': False,
            'id': 8561958,
            'state': 1,
            'task_id': 63698179
        }
        self.session.getBuildConfig.return_value = {
            'arches': 'arch1 arch2',
            'id': 1234,
            'extra': {},
        }
        self.task.run_callbacks = mock.MagicMock()
        self.task.initImageBuild = mock.MagicMock()
        self.task.initImageBuild.return_value = {
            'id': 98,
            'name': 'image_name',
            'version': 'image_version',
            'release': 'image_release',
        }
        self.task.get_nvrp = mock.MagicMock()
        self.task.get_nvrp.return_value = 'name', 'version', 'profile'
        self.task.wait = mock.MagicMock()
        self.task.wait.return_value = {
            1: 'correct result'
        }
        self.session.getChannel.return_value = {'name': 'channel_id'}
        self.session.getTaskInfo.return_value = {
            'owner': 'owner_id',
            'channel_id': 'channel_id',
        }
        self.session.getNextRelease.return_value = 'next_release'

        result = self.task.handler('target', arches,
                                   'git://desc.server/repo#fragment', 'desc_path')

        # test scm.assert_allowed inputs
        scm = self.scm[0]
        scm.assert_allowed.assert_called_once_with(
            allowed=self.options.allowed_scms,
            session=self.session,
            by_config=self.options.allowed_scms_use_config,
            by_policy=self.options.allowed_scms_use_policy,
            policy_data={
                'user_id': 'owner_id',
                'channel': 'channel_id',
                'scratch': False,
            })

        self.task.run_callbacks.assert_has_calls([
            mock.call(
                'preSCMCheckout',
                scminfo=scm.get_info(),
                build_tag=123,
                scratch=False,
            ),
            mock.call(
                'postSCMCheckout',
                scminfo=scm.get_info(),
                build_tag=123,
                scratch=False,
                srcdir=scm.checkout()
            )
        ])

        # subtasks
        self.session.host.subtask.assert_has_calls([
            mock.call(
                method='createKiwiImage',
                arglist=[
                    'name-profile',
                    'version',
                    'image_release',
                    'arch1',
                    self.session.getBuildTarget.return_value,
                    123,
                    self.task.getRepo.return_value,
                    'git://desc.server/repo#fragment',
                    'desc_path',
                    {
                        'scratch': False,
                        'optional_arches': [],
                    }
                ],
                label='arch1',
                parent=123,
                arch='arch1',
            ),
            mock.call(
                method='createKiwiImage',
                arglist=[
                    'name-profile',
                    'version',
                    'image_release',
                    'arch2',
                    self.session.getBuildTarget.return_value,
                    123,
                    self.task.getRepo.return_value,
                    'git://desc.server/repo#fragment',
                    'desc_path',
                    {
                        'scratch': False,
                        'optional_arches': []
                    }
                ],
                label='arch2',
                parent=123,
                arch='arch2'
            ),
            mock.call(
                method='tagBuild',
                arglist=[
                    321,
                    self.task.initImageBuild()['id'],
                    False,
                    None,
                    True
                ],
                label='tag',
                parent=123,
                arch='noarch'
            )
        ])

        self.assertEqual(result,
                         'image build results in: /mnt/koji/packages/'
                         'image_name/image_version/image_release/images')

    def test_handler_incompatible_archs(self):
        # arches must be preset in the buildroot
        with self.assertRaises(koji.BuildError):
            self.test_handler_correct(arches=['arch3', 'arch4'])

    def test_no_arches(self):
        # exactly same as correct variant. No arches are supplied,
        # they should be taken from build_config
        self.test_handler_correct(arches=[])


class TestKiwiCreateImageTask(unittest.TestCase):
    pass
