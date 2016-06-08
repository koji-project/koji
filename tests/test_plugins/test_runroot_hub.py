import unittest
import mock

import runroot_hub


class TestRunrootHub(unittest.TestCase):
    @mock.patch('kojihub.make_task')
    @mock.patch('runroot_hub.context')
    def test_basic_invocation(self, context, make_task):
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
