from __future__ import absolute_import
import mock
import six
try:
    import unittest2 as unittest
except ImportError:
    import unittest

from koji_cli.commands import handle_set_build_volume
from . import utils


class TestSetBuildVolume(utils.CliTestCase):

    # Show long diffs in error output...
    maxDiff = None

    def setUp(self):
        self.error_format = """Usage: %s set-build-volume <volume> <n-v-r> [<n-v-r> ...]
(Specify the --help global option for a list of other help options)

%s: error: {message}
""" % (self.progname, self.progname)

    @mock.patch('sys.stdout', new_callable=six.StringIO)
    @mock.patch('koji_cli.commands.activate_session')
    def test_handle_set_build_volume(self, activate_session_mock, stdout):
        """Test handle_set_build_volume function"""
        session = mock.MagicMock()
        options = mock.MagicMock()
        volume = 'DEFAULT'
        build = 'bash-4.4.12-7.fc26'
        volinfo = {'id': 0, 'name': volume}

        # Case 1. argument error
        expected = self.format_error_message(
            "You must provide a volume and at least one build")
        self.assert_system_exit(
            handle_set_build_volume,
            options,
            session,
            [],
            stderr=expected,
            activate_session=None)
        activate_session_mock.assert_not_called()

        # Case 2. wrong volume
        session.getVolume.return_value = {}
        expected = "No such volume: %s" % volume + "\n"
        self.assertEqual(
            1, handle_set_build_volume(options, session, [volume, build]))
        self.assert_console_message(stdout, expected)
        activate_session_mock.assert_not_called()

        # Case 3. no build found
        session.getVolume.return_value = volinfo
        session.getBuild.return_value = {}
        expected = "No such build: %s" % build + "\n"
        expected += "No builds to move" + "\n"
        self.assertEqual(
            1, handle_set_build_volume(options, session, [volume, build]))
        self.assert_console_message(stdout, expected)

        # Case 3. Build already in volume
        session.getBuild.side_effect = [
            {
                "id": 1,
                "name": "bash",
                "version": "4.4.12",
                "release": "5.fc26",
                "nvr": "bash-4.4.12-5.fc26",
                "volume_id": 0,
                "volume_name": "DEFAULT",
            },
        ]

        expected = "Build %s already on volume %s" % \
            (build, volinfo['name']) + "\n"
        expected += "No builds to move" + "\n"
        self.assertEqual(
            1, handle_set_build_volume(options, session, [volume, build]))
        self.assert_console_message(stdout, expected)

        # Case 4. Change build volume
        build = "sed-4.4-1.fc26"
        build_info = {
            "id": 2,
            "name": "sed",
            "version": "4.4",
            "release": "1.fc26",
            "nvr": "sed-4.4-1.fc26",
            "volume_id": 1,
            "volume_name": "CUSTOM",
        }

        session.getBuild.side_effect = [build_info]
        expected = "%s: %s -> %s" % \
            (build, build_info['volume_name'], volinfo['name']) + "\n"
        handle_set_build_volume(options, session, [volume, build, '--verbose'])
        self.assert_console_message(stdout, expected)
        session.changeBuildVolume.assert_called_with(
            build_info['id'], volinfo['id'])

    def test_handle_set_build_volume_help(self):
        self.assert_help(
            handle_set_build_volume,
            """Usage: %s set-build-volume <volume> <n-v-r> [<n-v-r> ...]
(Specify the --help global option for a list of other help options)

Options:
  -h, --help     show this help message and exit
  -v, --verbose  Be verbose
""" % self.progname)


if __name__ == '__main__':
    unittest.main()
