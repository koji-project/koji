from __future__ import absolute_import
import mock
try:
    import unittest2 as unittest
except ImportError:
    import unittest

import koji
import runroot_hub


class TestRunrootHub(unittest.TestCase):
    @mock.patch('kojihub.get_tag')
    @mock.patch('kojihub.make_task')
    @mock.patch('runroot_hub.context')
    def test_basic_invocation(self, context, make_task, get_tag):
        context.session.assertPerm = mock.MagicMock()
        get_tag.return_value = {'name': 'some_tag', 'arches': ''}
        runroot_hub.runroot(
            tagInfo='some_tag',
            arch='x86_64',
            command='ls',
        )
        make_task.assert_called_once_with(
            'runroot',
            ('some_tag', 'x86_64', 'ls'),
            priority=15,
            arch='x86_64',
            channel='runroot',
        )

    @mock.patch('kojihub.get_tag')
    @mock.patch('runroot_hub.context')
    def test_noarch_wrong_tag(self, context, get_tag):
        context.session.assertPerm = mock.MagicMock()
        get_tag.return_value = {'name': 'some_tag', 'arches': ''}
        with self.assertRaises(koji.GenericError):
            runroot_hub.runroot(
                tagInfo='some_tag',
                arch='noarch',
                command='ls',
            )
        get_tag.assert_called_once_with('some_tag', strict=True)

    @mock.patch('kojihub.make_task')
    @mock.patch('kojihub.get_all_arches')
    @mock.patch('kojihub.get_tag')
    @mock.patch('runroot_hub.context')
    def test_noarch_good_tag(self, context, get_tag, get_all_arches, make_task):
        context.session.assertPerm = mock.MagicMock()
        context.handlers = mock.MagicMock()
        context.handlers.call = mock.MagicMock()
        context.handlers.call.side_effect = [
            {'id': 2, 'name': 'runroot'}, # getChannel
            [ # listHosts
                {
                    'arches': 'i386 x86_64',
                    'capacity': 20.0,
                    'comment': '',
                    'description': '',
                    'enabled': True,
                    'id': 1,
                    'name': 'builder.example.com',
                    'ready': True,
                    'task_load': 0.0,
                    'user_id': 1
                }
            ]
        ]
        get_tag.return_value = {
            'arches': 's390 x86_64',
            'extra': {},
            'id': 123456,
            'locked': False,
            'maven_include_all': False,
            'maven_support': False,
            'name': 'some_tag',
            'perm': None,
            'perm_id': None
        }
        get_all_arches.return_value = ['s390', 's390x', 'x86_64']
        runroot_hub.runroot(
            tagInfo='some_tag',
            arch='noarch',
            command='ls',
        )

        # check results
        get_tag.assert_called_once_with('some_tag', strict=True)
        context.handlers.call.assert_has_calls([
            mock.call('getChannel', 'runroot', strict=True),
            mock.call('listHosts', channelID=2, enabled=True),
        ])
        make_task.assert_called_once_with(
            'runroot',
            ('some_tag', 'noarch', 'ls'),
            priority=15,
            arch='x86_64',
            channel='runroot',
        )

    @mock.patch('kojihub.make_task')
    @mock.patch('kojihub.get_all_arches')
    @mock.patch('kojihub.get_tag')
    @mock.patch('runroot_hub.context')
    def test_noarch_good_tag_missing_arch(self, context, get_tag, get_all_arches, make_task):
        context.session.assertPerm = mock.MagicMock()
        context.handlers = mock.MagicMock()
        context.handlers.call = mock.MagicMock()
        context.handlers.call.side_effect = [
            {'id': 2, 'name': 'runroot'}, # getChannel
            [ # listHosts
                {
                    'arches': 'i386 x86_64',
                    'capacity': 20.0,
                    'comment': '',
                    'description': '',
                    'enabled': True,
                    'id': 1,
                    'name': 'builder.example.com',
                    'ready': True,
                    'task_load': 0.0,
                    'user_id': 1
                }
            ]
        ]
        get_tag.return_value = {
            'arches': 's390',
            'extra': {},
            'id': 123456,
            'locked': False,
            'maven_include_all': False,
            'maven_support': False,
            'name': 'some_tag',
            'perm': None,
            'perm_id': None
        }
        get_all_arches.return_value = ['s390x']
        with self.assertRaises(koji.GenericError):
            runroot_hub.runroot(
                tagInfo='some_tag',
                arch='noarch',
                command='ls',
            )

        # check results
        get_tag.assert_called_once_with('some_tag', strict=True)
        context.handlers.call.assert_has_calls([
            mock.call('getChannel', 'runroot', strict=True),
            mock.call('listHosts', channelID=2, enabled=True),
        ])
        make_task.assert_not_called()
