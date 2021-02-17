from __future__ import absolute_import
import mock
import time
import unittest
from datetime import datetime
import koji
from six.moves import StringIO

from koji_cli.commands import anon_handle_list_history
from . import utils


class TestListHistory(utils.CliTestCase):
    def setUp(self):
        self.options = mock.MagicMock()
        self.options.debug = False
        self.session = mock.MagicMock()

    @staticmethod
    def get_expected_date_active_action(item, act='add'):
        if act == 'add':
            dt = datetime.fromtimestamp(item['create_ts'])
            if item['active']:
                active = ' [still active]'
            else:
                active = ''
        else:
            dt = datetime.fromtimestamp(item['revoke_ts'])
            active = ''

        expected_date = time.asctime(dt.timetuple())
        return expected_date, active

    def get_expected_channel(self, item):
        if item['active']:
            list_active = ['add']
        else:
            list_active = ['add', 'remove']
        expected = ''
        for act in list_active:
            expected_date, active = self.get_expected_date_active_action(
                item, act)
            if act == 'add':
                action = 'added to'
            else:
                action = 'removed from'
            expected = expected + '{} host {} {} channel {} by {}{}\n'.format(
                expected_date, item['host.name'], action, item['channels.name'],
                item['creator_name'], active)
        return expected

    def get_expected_host(self, item):
        if item['active']:
            list_active = ['add']
        else:
            list_active = ['add', 'remove']
        expected = ''
        for act in list_active:
            expected_date, active = self.get_expected_date_active_action(
                item, act)
            if act == 'add':
                action = 'new host'
            else:
                action = 'host deleted'
            expected = expected + "{} {}: {} by {}{}\n".format(
                expected_date, action, item['host.name'], item['creator_name'],
                active)
        return expected

    def get_expected_package_owner(self, item):
        expected_date, active = self.get_expected_date_active_action(item)
        expected = "{} package owner {} set for {} in {} by {}{}\n".format(
            expected_date, item['owner.name'], item['package.name'],
            item['tag.name'], item['creator_name'], active)
        return expected

    def get_expected_tag_listing(self, item):
        if item['active']:
            list_active = ['add']
        else:
            list_active = ['add', 'remove']
        expected = ''
        for act in list_active:
            expected_date, active = self.get_expected_date_active_action(
                item, act)
            if act == 'add':
                action = 'tagged into'
            else:
                action = 'untagged from'
            expected = expected + "{} {}-{}-{} {} {} by {}{}\n".format(
                expected_date, item['name'], item['version'],
                item['release'], action, item['tag.name'],
                item['creator_name'], active)
        return expected

    def get_expected_tag_config(self, item):
        expected_date, active = self.get_expected_date_active_action(item)
        expected = "{} new tag: {} by {}{}\n".format(
            expected_date, item['tag.name'], item['creator_name'], active)
        return expected

    def get_expected_tag_extra(self, item):
        expected_date, active = self.get_expected_date_active_action(item)
        expected = "{} added tag option {} for tag {} by {}{}\n".format(
            expected_date, item['key'], item['tag.name'],
            item['creator_name'], active)
        return expected

    def get_expected_build_target(self, item):
        if item['active']:
            list_active = ['add']
        else:
            list_active = ['add', 'remove']
        expected = ''
        for act in list_active:
            expected_date, active = self.get_expected_date_active_action(
                item, act)
            if act == 'add':
                action = 'new build target'
            else:
                action = 'build target deleted'
            expected = expected + "{} {}: {} by {}{}\n".format(
                expected_date, action, item['build_target.name'],
                item['creator_name'], active)
        return expected

    def get_expected_tag_packages(self, item):
        expected_date, active = self.get_expected_date_active_action(item)
        expected = "{} package list entry created: {} in {} by {}{}\n".format(
            expected_date, item['package.name'], item['tag.name'],
            item['creator_name'], active)
        return expected

    def get_expected_tag_inheritance(self, item):
        if item['active']:
            list_active = ['add']
        else:
            list_active = ['add', 'remove']
        expected = ''
        for act in list_active:
            expected_date, active = self.get_expected_date_active_action(
                item, act)
            if act == 'add':
                action = 'added'
            else:
                action = 'removed'
            expected = \
                expected + "{} inheritance line {}->{} {} by {}{}\n".format(
                    expected_date, item['tag.name'], item['parent.name'],
                    action, item['creator_name'], active)
        return expected

    def get_expected_user_perm(self, item):
        if item['active']:
            list_active = ['add']
        else:
            list_active = ['add', 'remove']
        expected = ''
        for act in list_active:
            expected_date, active = self.get_expected_date_active_action(
                item, act)
            if act == 'add':
                action = 'granted to'
            else:
                action = 'revoked for'
            expected = expected + "{} permission {} {} {} by {}{}\n".format(
                expected_date, item['permission.name'], action,
                item['user.name'], item['creator_name'], active)
        return expected

    def get_expected_cg_user(self, item):
        if item['active']:
            list_active = ['add']
        else:
            list_active = ['add', 'remove']
        expected = ''
        for act in list_active:
            expected_date, active = self.get_expected_date_active_action(
                item, act)
            if act == 'add':
                action = 'added to'
            else:
                action = 'removed from'
            expected = \
                expected + "{} user {} {} content generator {} by {}" \
                           "{}\n".format(expected_date, item['user.name'],
                                         action, item['content_generator.name'],
                                         item['creator_name'], active)
        return expected

    def get_expected_ext_repo(self, item):
        expected_date, active = self.get_expected_date_active_action(item)
        expected = "{} new external repo: {} by {}{}\n".format(
            expected_date, item['external_repo.name'], item['creator_name'],
            active)
        return expected

    def get_expected_tag_ext_repo(self, item):
        expected_date, active = self.get_expected_date_active_action(item)
        expected = "{} external repo entry for {} added to tag {} " \
                   "by {}{}\n".format(expected_date, item['external_repo.name'],
                                      item['tag.name'], item['creator_name'],
                                      active)
        return expected

    @mock.patch('sys.stderr', new_callable=StringIO)
    def test_list_history_without_option(self, stderr):
        expected = "Usage: python -m nose list-history [options]\n" \
                   "(Specify the --help global option for a list of other " \
                   "help options)\n\n" \
                   "python -m nose: error: Please specify an option to limit " \
                   "the query\n"
        self.session.getChannel.return_value = None
        with self.assertRaises(SystemExit) as ex:
            anon_handle_list_history(self.options, self.session, [])
        self.assertExitCode(ex, 2)
        self.assert_console_message(stderr, expected)

    @mock.patch('sys.stderr', new_callable=StringIO)
    @mock.patch('sys.stdout', new_callable=StringIO)
    @mock.patch('koji_cli.commands.ensure_connection')
    def test_list_history_channel(self, ensure_connection_mock, stdout, stderr):
        # test case when channel is still active
        channel_name = 'default'

        # when channel name is created
        dict_history = {
            'host_channels': [
                {'active': True,
                 'channel_id': 1,
                 'channels.name': 'default',
                 'create_event': 3,
                 'create_ts': 1612355089.887727,
                 'creator_id': 1,
                 'creator_name': 'kojiadmin',
                 'host.name': 'kojibuilder',
                 'host_id': 1,
                 'revoke_event': None,
                 'revoke_ts': None,
                 'revoker_id': None,
                 'revoker_name': None}]
        }
        self.session.queryHistory.return_value = dict_history
        expected = self.get_expected_channel(dict_history['host_channels'][0])
        anon_handle_list_history(self.options, self.session,
                                 ['--channel', channel_name])
        self.assert_console_message(stdout, expected)

        # when channel name is dropped
        dict_history = {
            'host_channels': [
                {'active': None,
                 'channel_id': 1,
                 'channels.name': 'default',
                 'create_event': 3,
                 'create_ts': 1612355089.887727,
                 'creator_id': 1,
                 'creator_name': 'kojiadmin',
                 'host.name': 'kojibuilder',
                 'host_id': 1,
                 'revoke_event': 8,
                 'revoke_ts': 1612355099.887727,
                 'revoker_id': 1,
                 'revoker_name': 'kojiadmin'}]
        }
        self.session.queryHistory.return_value = dict_history
        expected = self.get_expected_channel(dict_history['host_channels'][0])
        anon_handle_list_history(self.options, self.session,
                                 ['--channel', channel_name])
        self.assert_console_message(stdout, expected)

        # test case when channel is not existing
        expected = "No such channel: %s" % channel_name + "\n"
        self.session.untaggedBuilds.return_value = {}
        self.session.getChannel.return_value = None
        with self.assertRaises(SystemExit) as ex:
            anon_handle_list_history(self.options, self.session,
                                     ['--channel', channel_name])
        self.assertExitCode(ex, 1)
        self.assert_console_message(stderr, expected)

    @mock.patch('sys.stderr', new_callable=StringIO)
    @mock.patch('sys.stdout', new_callable=StringIO)
    @mock.patch('koji_cli.commands.ensure_connection')
    def test_list_history_host(self, ensure_connection_mock, stdout, stderr):
        host_name = 'kojibuilder'

        # new host
        dict_history = {
            'host_config': [
                {'active': True,
                 'arches': 'x86_64',
                 'capacity': 2.0,
                 'comment': None,
                 'create_event': 2,
                 'create_ts': 1612355089.886359,
                 'creator_id': 1,
                 'creator_name': 'kojiadmin',
                 'description': None,
                 'enabled': True,
                 'host.name': 'kojibuilder',
                 'host_id': 1,
                 'revoke_event': None,
                 'revoke_ts': None,
                 'revoker_id': None,
                 'revoker_name': None}]
        }

        self.session.queryHistory.return_value = dict_history
        expected = self.get_expected_host(dict_history['host_config'][0])
        anon_handle_list_history(self.options, self.session,
                                 ['--host', host_name])
        self.assert_console_message(stdout, expected)

        # dropped
        dict_history = {
            'host_config': [
                {'active': None,
                 'arches': 'x86_64',
                 'capacity': 2.0,
                 'comment': None,
                 'create_event': 2,
                 'create_ts': 1612355089.886359,
                 'creator_id': 1,
                 'creator_name': 'kojiadmin',
                 'description': None,
                 'enabled': True,
                 'host.name': 'kojibuilder',
                 'host_id': 1,
                 'revoke_event': 3,
                 'revoke_ts': 1612355099.886359,
                 'revoker_id': 1,
                 'revoker_name': 'kojiadmin'}]
        }

        host_name = 'kojibuilder'
        self.session.queryHistory.return_value = dict_history
        expected = self.get_expected_host(dict_history['host_config'][0])
        anon_handle_list_history(self.options, self.session,
                                 ['--host', host_name])
        self.assert_console_message(stdout, expected)

        # test case when host is not existing
        expected = "No such host: %s" % host_name + "\n"
        self.session.untaggedBuilds.return_value = {}
        self.session.getHost.return_value = None
        with self.assertRaises(SystemExit) as ex:
            anon_handle_list_history(self.options, self.session,
                                     ['--host', host_name])
        self.assertExitCode(ex, 1)
        self.assert_console_message(stderr, expected)

    @mock.patch('sys.stdout', new_callable=StringIO)
    @mock.patch('koji_cli.commands.ensure_connection')
    def test_list_history_build(self, ensure_connection_mock, stdout):
        build_nvr = 'test-build-1.1-11'

        # when build is tagged
        dict_history = {
            'tag_listing': [
                {'active': True,
                 'build.state': 1,
                 'build_id': 6,
                 'create_event': 585,
                 'create_ts': 1613744957.14465,
                 'creator_id': 1,
                 'creator_name': 'kojiadmin',
                 'epoch': 7,
                 'name': 'test-build',
                 'release': '11',
                 'revoke_event': None,
                 'revoke_ts': None,
                 'revoker_id': None,
                 'revoker_name': None,
                 'tag.name': 'destination',
                 'tag_id': 13,
                 'version': '1.1'}]
        }

        self.session.queryHistory.return_value = dict_history
        expected = self.get_expected_tag_listing(dict_history['tag_listing'][0])
        anon_handle_list_history(self.options, self.session,
                                 ['--build', build_nvr])
        self.assert_console_message(stdout, expected)

        # when build is untagged
        dict_history = {
            'tag_listing': [
                {'active': None,
                 'build.state': 1,
                 'build_id': 6,
                 'create_event': 585,
                 'create_ts': 1613744957.14465,
                 'creator_id': 1,
                 'creator_name': 'kojiadmin',
                 'epoch': 7,
                 'name': 'test-build',
                 'release': '11',
                 'revoke_event': 590,
                 'revoke_ts': 1613744967.14465,
                 'revoker_id': 1,
                 'revoker_name': 'kojiadmin',
                 'tag.name': 'destination-tag',
                 'tag_id': 13,
                 'version': '1.1'}]
        }
        self.session.queryHistory.return_value = dict_history
        expected = self.get_expected_tag_listing(dict_history['tag_listing'][0])
        anon_handle_list_history(self.options, self.session,
                                 ['--build', build_nvr])
        self.assert_console_message(stdout, expected)

        # test case when build nvr is not existing
        expected = "No matching build found: %s" % build_nvr + "\n"
        self.session.queryHistory.side_effect = koji.GenericError(expected)
        with self.assertRaises(koji.GenericError) as ex:
            anon_handle_list_history(self.options, self.session,
                                     ['--build', build_nvr])
        self.assertEqual(str(ex.exception), expected)

        # test case when build has wrong format
        build = 'test-build'
        expected = "invalid format: %s" % build + "\n"
        self.session.queryHistory.side_effect = koji.GenericError(expected)
        with self.assertRaises(koji.GenericError) as ex:
            anon_handle_list_history(self.options, self.session,
                                     ['--build', build_nvr])
        self.assertEqual(str(ex.exception), expected)

    @mock.patch('sys.stdout', new_callable=StringIO)
    @mock.patch('koji_cli.commands.ensure_connection')
    def test_list_history_package(self, ensure_connection_mock, stdout):
        dict_history = {
            'tag_listing': [
                {'active': True,
                 'build.state': 1,
                 'build_id': 4,
                 'create_event': 424,
                 'create_ts': 1613736474.42776,
                 'creator_id': 1,
                 'creator_name': 'kojiadmin',
                 'epoch': 7,
                 'name': 'pkg-name',
                 'release': '11',
                 'revoke_event': None,
                 'revoke_ts': None,
                 'revoker_id': None,
                 'revoker_name': None,
                 'tag.name': 'destination-test-tag',
                 'tag_id': 10,
                 'version': '1.1'}],
            'tag_package_owners': [
                {'active': True,
                 'create_event': 418,
                 'create_ts': 1613736220.79199,
                 'creator_id': 1,
                 'creator_name': 'kojiadmin',
                 'owner': 1,
                 'owner.name': 'kojiadmin',
                 'package.name': 'pkg-name',
                 'package_id': 4,
                 'revoke_event': None,
                 'revoke_ts': None,
                 'revoker_id': None,
                 'revoker_name': None,
                 'tag.name': 'destination-test-tag',
                 'tag_id': 10}],
            'tag_packages': [
                {'active': True,
                 'blocked': False,
                 'create_event': 418,
                 'create_ts': 1613736220.79199,
                 'creator_id': 1,
                 'creator_name': 'kojiadmin',
                 'extra_arches': '',
                 'package.name': 'pkg-name',
                 'package_id': 4,
                 'revoke_event': None,
                 'revoke_ts': None,
                 'revoker_id': None,
                 'revoker_name': None,
                 'tag.name': 'destination-test-tag',
                 'tag_id': 10}]
        }

        package = 'pkg-name'
        self.session.queryHistory.return_value = dict_history
        expected = self.get_expected_package_owner(
            dict_history['tag_package_owners'][0])
        expected = expected + self.get_expected_tag_packages(
            dict_history['tag_packages'][0])
        expected = expected + self.get_expected_tag_listing(
            dict_history['tag_listing'][0])
        anon_handle_list_history(self.options, self.session,
                                 ['--package', package])
        self.assert_console_message(stdout, expected)

        # test case when package s not existing
        expected = "No such entry in table package: %s" % package + "\n"
        self.session.queryHistory.side_effect = koji.GenericError(expected)
        with self.assertRaises(koji.GenericError) as ex:
            anon_handle_list_history(self.options, self.session,
                                     ['--package', package])
        self.assertEqual(str(ex.exception), expected)

    @mock.patch('sys.stdout', new_callable=StringIO)
    @mock.patch('koji_cli.commands.ensure_connection')
    def test_list_history_tag(self, ensure_connection_mock, stdout):
        dict_history = {
            'tag_config': [
                {'active': True,
                 'arches': 'x86_64',
                 'create_event': 6,
                 'create_ts': 1612872591.313584,
                 'creator_id': 1,
                 'creator_name': 'kojiadmin',
                 'locked': False,
                 'maven_include_all': False,
                 'maven_support': False,
                 'perm_id': None,
                 'permission.name': None,
                 'revoke_event': None,
                 'revoke_ts': None,
                 'revoker_id': None,
                 'revoker_name': None,
                 'tag.name': 'test-tag',
                 'tag_id': 2}],
            'tag_extra': [
                {'active': True,
                 'create_event': 6,
                 'create_ts': 1612872591.313584,
                 'creator_id': 1,
                 'creator_name': 'kojiadmin',
                 'key': 'mock.package_manager',
                 'revoke_event': None,
                 'revoke_ts': None,
                 'revoker_id': None,
                 'revoker_name': None,
                 'tag.name': 'test-tag',
                 'tag_id': 2,
                 'value': '"dnf"'}]
        }
        tag = 'test-tag'
        self.session.queryHistory.return_value = dict_history
        expected = self.get_expected_tag_config(dict_history['tag_config'][0])
        expected = expected + self.get_expected_tag_extra(
            dict_history['tag_extra'][0])
        anon_handle_list_history(self.options, self.session, ['--tag', tag])
        self.assert_console_message(stdout, expected)

        # test case when tag s not existing
        expected = "No such entry in table tag: %s" % tag + "\n"
        self.session.queryHistory.side_effect = koji.GenericError(expected)
        with self.assertRaises(koji.GenericError) as ex:
            anon_handle_list_history(self.options, self.session,
                                     ['--tag', tag])
        self.assertEqual(str(ex.exception), expected)

    @mock.patch('sys.stdout', new_callable=StringIO)
    @mock.patch('koji_cli.commands.ensure_connection')
    def test_list_history_editor(self, ensure_connection_mock, stdout):
        dict_history = {
            'build_target_config': [
                {'_created_by': True,
                 '_revoked_by': None,
                 'active': True,
                 'build_tag': 1,
                 'build_tag.name': 'test-tag',
                 'build_target.name': 'build-target-test-tag',
                 'build_target_id': 1,
                 'create_event': 8,
                 'create_ts': 1612872656.231499,
                 'creator_id': 1,
                 'creator_name': 'kojiadmin',
                 'dest_tag': 3,
                 'dest_tag.name': 'destination-test-tag',
                 'revoke_event': None,
                 'revoke_ts': None,
                 'revoker_id': None,
                 'revoker_name': None}],
            'host_channels': [
                {'_created_by': True,
                 '_revoked_by': None,
                 'active': True,
                 'channel_id': 1,
                 'channels.name': 'default',
                 'create_event': 3,
                 'create_ts': 1612355089.887727,
                 'creator_id': 1,
                 'creator_name': 'kojiadmin',
                 'host.name': 'kojibuilder',
                 'host_id': 1,
                 'revoke_event': None,
                 'revoke_ts': None,
                 'revoker_id': None,
                 'revoker_name': None}],
            'host_config': [
                {'_created_by': True,
                 '_revoked_by': None,
                 'active': True,
                 'arches': 'x86_64',
                 'capacity': 2.0,
                 'comment': None,
                 'create_event': 2,
                 'create_ts': 1612355089.886359,
                 'creator_id': 1,
                 'creator_name': 'kojiadmin',
                 'description': None,
                 'enabled': True,
                 'host.name': 'kojibuilder',
                 'host_id': 1,
                 'revoke_event': None,
                 'revoke_ts': None,
                 'revoker_id': None,
                 'revoker_name': None}],
            'tag_config': [
                {'_created_by': True,
                 '_revoked_by': None,
                 'active': True,
                 'arches': '',
                 'create_event': 5,
                 'create_ts': 1612871243.593475,
                 'creator_id': 1,
                 'creator_name': 'kojiadmin',
                 'locked': False,
                 'maven_include_all': False,
                 'maven_support': False,
                 'perm_id': None,
                 'permission.name': None,
                 'revoke_event': None,
                 'revoke_ts': None,
                 'revoker_id': None,
                 'revoker_name': None,
                 'tag.name': 'test-tag',
                 'tag_id': 1}],
            'tag_extra': [
                {'_created_by': True,
                 '_revoked_by': None,
                 'active': True,
                 'create_event': 6,
                 'create_ts': 1612872591.313584,
                 'creator_id': 1,
                 'creator_name': 'kojiadmin',
                 'key': 'mock.package_manager',
                 'revoke_event': None,
                 'revoke_ts': None,
                 'revoker_id': None,
                 'revoker_name': None,
                 'tag.name': 'test-tag',
                 'tag_id': 1,
                 'value': '"dnf"'}],
            'tag_inheritance': [
                {'_created_by': True,
                 '_revoked_by': True,
                 'active': None,
                 'create_event': 16,
                 'create_ts': 1613545870.370125,
                 'creator_id': 1,
                 'creator_name': 'kojiadmin',
                 'intransitive': False,
                 'maxdepth': None,
                 'noconfig': False,
                 'parent.name': 'parent-test-tag',
                 'parent_id': 4,
                 'pkg_filter': '',
                 'priority': 1,
                 'revoke_event': 31,
                 'revoke_ts': 1613545887.513565,
                 'revoker_id': 1,
                 'revoker_name': 'kojiadmin',
                 'tag.name': 'test-tag',
                 'tag_id': 5}],
            'tag_package_owners': [
                {'_created_by': True,
                 '_revoked_by': None,
                 'active': True,
                 'create_event': 9,
                 'create_ts': 1612872778.934647,
                 'creator_id': 1,
                 'creator_name': 'kojiadmin',
                 'owner': 1,
                 'owner.name': 'kojiadmin',
                 'package.name': 'koji',
                 'package_id': 1,
                 'revoke_event': None,
                 'revoke_ts': None,
                 'revoker_id': None,
                 'revoker_name': None,
                 'tag.name': 'destination-test-tag',
                 'tag_id': 3}],
            'tag_packages': [
                {'_created_by': True,
                 '_revoked_by': None,
                 'active': True,
                 'blocked': False,
                 'create_event': 9,
                 'create_ts': 1612872778.934647,
                 'creator_id': 1,
                 'creator_name': 'kojiadmin',
                 'extra_arches': '',
                 'package.name': 'koji',
                 'package_id': 1,
                 'revoke_event': None,
                 'revoke_ts': None,
                 'revoker_id': None,
                 'revoker_name': None,
                 'tag.name': 'destination-test-tag',
                 'tag_id': 3}],
            'user_perms': [
                {'_created_by': True,
                 '_revoked_by': None,
                 'active': True,
                 'create_event': 1,
                 'create_ts': 1612355089.882428,
                 'creator_id': 1,
                 'creator_name': 'kojiadmin',
                 'perm_id': 1,
                 'permission.name': 'admin',
                 'revoke_event': None,
                 'revoke_ts': None,
                 'revoker_id': None,
                 'revoker_name': None,
                 'user.name': 'kojiadmin',
                 'user_id': 1}]
        }
        editor = 'kojiadmin'
        self.session.queryHistory.return_value = dict_history
        expected = self.get_expected_user_perm(dict_history['user_perms'][0])
        expected = expected + self.get_expected_host(
            dict_history['host_config'][0])
        expected = expected + self.get_expected_channel(
            dict_history['host_channels'][0])
        expected = expected + self.get_expected_tag_config(
            dict_history['tag_config'][0])
        expected = expected + self.get_expected_tag_extra(
            dict_history['tag_extra'][0])
        expected = expected + self.get_expected_build_target(
            dict_history['build_target_config'][0])
        expected = expected + self.get_expected_package_owner(
            dict_history['tag_package_owners'][0])
        expected = expected + self.get_expected_tag_packages(
            dict_history['tag_packages'][0])
        expected = expected + self.get_expected_tag_inheritance(
            dict_history['tag_inheritance'][0])
        anon_handle_list_history(self.options, self.session,
                                 ['--editor', editor])
        self.assert_console_message(stdout, expected)

        # test case when tag is not existing
        expected = "No such user: %s" % editor + "\n"
        self.session.queryHistory.side_effect = koji.GenericError(expected)
        with self.assertRaises(koji.GenericError) as ex:
            anon_handle_list_history(self.options, self.session,
                                     ['--editor', editor])
        self.assertEqual(str(ex.exception), expected)

    @mock.patch('sys.stdout', new_callable=StringIO)
    @mock.patch('koji_cli.commands.ensure_connection')
    def test_list_history_user(self, ensure_connection_mock, stdout):
        dict_history = {
            'cg_users': [],
            'tag_package_owners': [
                {'active': True,
                 'create_event': 9,
                 'create_ts': 1613730799.934647,
                 'creator_id': 1,
                 'creator_name': 'kojiadmin',
                 'owner': 1,
                 'owner.name': 'kojiadmin',
                 'package.name': 'koji',
                 'package_id': 1,
                 'revoke_event': None,
                 'revoke_ts': None,
                 'revoker_id': None,
                 'revoker_name': None,
                 'tag.name': 'destination-test-tag',
                 'tag_id': 3}],
            'user_groups': [],
            'user_perms': [
                {'active': True,
                 'create_event': 1,
                 'create_ts': 1612355089.882428,
                 'creator_id': 1,
                 'creator_name': 'kojiadmin',
                 'perm_id': 1,
                 'permission.name': 'admin',
                 'revoke_event': None,
                 'revoke_ts': None,
                 'revoker_id': None,
                 'revoker_name': None,
                 'user.name': 'kojiadmin',
                 'user_id': 1},
                {'active': None,
                 'create_event': 6,
                 'create_ts': 1613730777.437744,
                 'creator_id': 1,
                 'creator_name': 'kojiadmin',
                 'perm_id': 4,
                 'permission.name': 'dist-repo',
                 'revoke_event': 7,
                 'revoke_ts': 1613730790.797031,
                 'revoker_id': 1,
                 'revoker_name': 'kojiadmin',
                 'user.name': 'kojiadmin',
                 'user_id': 1}]
        }

        username = 'kojiadmin'
        self.session.queryHistory.return_value = dict_history
        expected = ''
        for item in dict_history['user_perms']:
            expected = expected + self.get_expected_user_perm(item)
        expected = expected + self.get_expected_package_owner(
            dict_history['tag_package_owners'][0])
        anon_handle_list_history(self.options, self.session,
                                 ['--user', username])
        self.assert_console_message(stdout, expected)

        # test case when user is not existing
        expected = "No such user: %s" % username + "\n"
        self.session.queryHistory.side_effect = koji.GenericError(expected)
        with self.assertRaises(koji.GenericError) as ex:
            anon_handle_list_history(self.options, self.session,
                                     ['--user', username])
        self.assertEqual(str(ex.exception), expected)

    @mock.patch('sys.stdout', new_callable=StringIO)
    @mock.patch('koji_cli.commands.ensure_connection')
    def test_list_history_permissions(self, ensure_connection_mock, stdout):
        permission = 'dist-repo'
        # when user has permission
        dict_history = {
            'tag_config': [],
            'user_perms': [
                {'active': True,
                 'create_event': 20,
                 'create_ts': 1613730777.437744,
                 'creator_id': 1,
                 'creator_name': 'kojiadmin',
                 'perm_id': 4,
                 'permission.name': 'dist-repo',
                 'revoke_event': None,
                 'revoke_ts': None,
                 'revoker_id': None,
                 'revoker_name': None,
                 'user.name': 'kojiadmin',
                 'user_id': 1}]
        }
        self.session.queryHistory.return_value = dict_history
        expected = self.get_expected_user_perm(dict_history['user_perms'][0])
        anon_handle_list_history(self.options, self.session,
                                 ['--permission', permission])
        self.assert_console_message(stdout, expected)

        # when user does not have permission
        dict_history = {
            'tag_config': [],
            'user_perms': [
                {'active': None,
                 'create_event': 25,
                 'create_ts': 1613730787.437744,
                 'creator_id': 1,
                 'creator_name': 'kojiadmin',
                 'perm_id': 4,
                 'permission.name': 'dist-repo',
                 'revoke_event': 27,
                 'revoke_ts': 1613730797.797031,
                 'revoker_id': 1,
                 'revoker_name': 'kojiadmin',
                 'user.name': 'kojiadmin',
                 'user_id': 1}]
        }
        self.session.queryHistory.return_value = dict_history
        expected = self.get_expected_user_perm(dict_history['user_perms'][0])
        anon_handle_list_history(self.options, self.session,
                                 ['--permission', permission])
        self.assert_console_message(stdout, expected)

        # test case when perm is not existing
        expected = "No such entry in table permissions: %s" % permission + "\n"
        self.session.queryHistory.side_effect = koji.GenericError(expected)
        with self.assertRaises(koji.GenericError) as ex:
            anon_handle_list_history(self.options, self.session,
                                     ['--permission', permission])
        self.assertEqual(str(ex.exception), expected)

    @mock.patch('sys.stdout', new_callable=StringIO)
    @mock.patch('koji_cli.commands.ensure_connection')
    def test_list_history_cg(self, ensure_connection_mock, stdout):
        cg = 'test-cg'

        # when cg is new
        dict_history = {
            'cg_users': [
                {'active': True,
                 'cg_id': 1,
                 'content_generator.name': 'test-cg',
                 'create_event': 425,
                 'create_ts': 1613736494.11504,
                 'creator_id': 1,
                 'creator_name': 'kojiadmin',
                 'revoke_event': None,
                 'revoke_ts': None,
                 'revoker_id': None,
                 'revoker_name': None,
                 'user.name': 'kojiadmin',
                 'user_id': 1}]
        }
        self.session.queryHistory.return_value = dict_history
        expected = self.get_expected_cg_user(dict_history['cg_users'][0])
        anon_handle_list_history(self.options, self.session, ['--cg', cg])
        self.assert_console_message(stdout, expected)

        # when cg is dropped
        dict_history = {
            'cg_users': [
                {'active': None,
                 'cg_id': 2,
                 'content_generator.name': 'test-cg',
                 'create_event': 430,
                 'create_ts': 1613736499.11504,
                 'creator_id': 1,
                 'creator_name': 'kojiadmin',
                 'revoke_event': 440,
                 'revoke_ts': 1613736510.11504,
                 'revoker_id': 1,
                 'revoker_name': 'kojiadmin',
                 'user.name': 'kojiadmin',
                 'user_id': 1}]
        }
        self.session.queryHistory.return_value = dict_history
        expected = self.get_expected_cg_user(dict_history['cg_users'][0])
        anon_handle_list_history(self.options, self.session, ['--cg', cg])
        self.assert_console_message(stdout, expected)

        # test case when cg is not existing
        expected = "No such entry in table content_generator: %s" % cg + "\n"
        self.session.queryHistory.side_effect = koji.GenericError(expected)
        with self.assertRaises(koji.GenericError) as ex:
            anon_handle_list_history(self.options, self.session, ['--cg', cg])
        self.assertEqual(str(ex.exception), expected)

    @mock.patch('sys.stdout', new_callable=StringIO)
    @mock.patch('koji_cli.commands.ensure_connection')
    def test_list_history_external_repo(self, ensure_connection_mock, stdout):
        dict_history = {
            'external_repo_config': [
                {'active': True,
                 'create_event': 342,
                 'create_ts': 1613736061.68861,
                 'creator_id': 1,
                 'creator_name': 'kojiadmin',
                 'external_repo.name': 'external-repo-test',
                 'external_repo_id': 5,
                 'revoke_event': None,
                 'revoke_ts': None,
                 'revoker_id': None,
                 'revoker_name': None,
                 'url': 'https://kojipkgs.fedoraproject.org/repos/'
                        'f32-build/latest/$arch/'}],
            'tag_external_repos': [
                {'active': True,
                 'create_event': 343,
                 'create_ts': 1613736061.72882,
                 'creator_id': 1,
                 'creator_name': 'kojiadmin',
                 'external_repo.name': 'external-repo-test',
                 'external_repo_id': 5,
                 'merge_mode': 'koji',
                 'priority': 5,
                 'revoke_event': None,
                 'revoke_ts': None,
                 'revoker_id': None,
                 'revoker_name': None,
                 'tag.name': 'test-tag',
                 'tag_id': 9}]
        }
        external_repo = 'external-repo-test'
        self.session.queryHistory.return_value = dict_history
        expected = self.get_expected_ext_repo(
            dict_history['external_repo_config'][0])
        expected = expected + self.get_expected_tag_ext_repo(
            dict_history['tag_external_repos'][0])
        anon_handle_list_history(self.options, self.session,
                                 ['--external-repo', external_repo])
        self.assert_console_message(stdout, expected)

        # test case when external repo is not existing
        expected = "No such entry in table external_repo: " \
                   "%s" % external_repo + "\n"
        self.session.queryHistory.side_effect = koji.GenericError(expected)
        with self.assertRaises(koji.GenericError) as ex:
            anon_handle_list_history(self.options, self.session,
                                     ['--external-repo', external_repo])
        self.assertEqual(str(ex.exception), expected)

    @mock.patch('sys.stdout', new_callable=StringIO)
    @mock.patch('koji_cli.commands.ensure_connection')
    def test_list_history_build_target(self, ensure_connection_mock, stdout):
        build_target = 'test-build-target'

        # test when build target is new
        dict_history = {
            'build_target_config': [
                {'active': True,
                 'build_tag': 10,
                 'build_tag.name': 'test-tag',
                 'build_target.name': 'test-build-target',
                 'build_target_id': 5,
                 'create_event': 420,
                 'create_ts': 1613736230.7615,
                 'creator_id': 1,
                 'creator_name': 'kojiadmin',
                 'dest_tag': 11,
                 'dest_tag.name': 'destination-test-tag',
                 'revoke_event': None,
                 'revoke_ts': None,
                 'revoker_id': None,
                 'revoker_name': None}]
        }
        self.session.queryHistory.return_value = dict_history
        expected = self.get_expected_build_target(
            dict_history['build_target_config'][0])
        anon_handle_list_history(self.options, self.session,
                                 ['--build-target', build_target])
        self.assert_console_message(stdout, expected)

        # test when build target is dropped
        dict_history = {
            'build_target_config': [
                {'active': None,
                 'build_tag': 9,
                 'build_tag.name': 'test-tag',
                 'build_target.name': 'test-build-target',
                 'build_target_id': 4,
                 'create_event': 417,
                 'create_ts': 1613736220.7615,
                 'creator_id': 1,
                 'creator_name': 'kojiadmin',
                 'dest_tag': 10,
                 'dest_tag.name': 'destination-test-tag',
                 'revoke_event': 420,
                 'revoke_ts': 1613736225.7615,
                 'revoker_id': 1,
                 'revoker_name': 'kojiadmin'}]
        }
        self.session.queryHistory.return_value = dict_history
        expected = self.get_expected_build_target(
            dict_history['build_target_config'][0])
        anon_handle_list_history(self.options, self.session,
                                 ['--build-target', build_target])
        self.assert_console_message(stdout, expected)

        # test case when build target is not existing
        expected = "No such entry in table build_target: " \
                   "%s" % build_target + "\n"
        self.session.queryHistory.side_effect = koji.GenericError(expected)
        with self.assertRaises(koji.GenericError) as ex:
            anon_handle_list_history(self.options, self.session,
                                     ['--build-target', build_target])
        self.assertEqual(str(ex.exception), expected)

    @mock.patch('sys.stdout', new_callable=StringIO)
    @mock.patch('koji_cli.commands.ensure_connection')
    def test_list_history_xkey(self, ensure_connection_mock, stdout):
        dict_history = {
            'tag_extra': [
                {'active': True,
                 'create_event': 586,
                 'create_ts': 1613744977.02986,
                 'creator_id': 1,
                 'creator_name': 'kojiadmin',
                 'key': 'extra-key-test',
                 'revoke_event': None,
                 'revoke_ts': None,
                 'revoker_id': None,
                 'revoker_name': None,
                 'tag.name': 'tag-test',
                 'tag_id': 14,
                 'value': '"extra-value-test"'}]
        }
        xkey = 'extra-key-test'
        self.session.queryHistory.return_value = dict_history
        expected = self.get_expected_tag_extra(dict_history['tag_extra'][0])

        anon_handle_list_history(self.options, self.session, ['--xkey', xkey])
        self.assert_console_message(stdout, expected)

    def test_handle_list_history_help(self):
        self.assert_help(
            anon_handle_list_history,
            """Usage: %s list-history [options]
(Specify the --help global option for a list of other help options)

Options:
  -h, --help            show this help message and exit
  --build=BUILD         Only show data for a specific build
  --package=PACKAGE     Only show data for a specific package
  --tag=TAG             Only show data for a specific tag
  --editor=USER, --by=USER
                        Only show entries modified by user
  --user=USER           Only show entries affecting a user
  --permission=PERMISSION
                        Only show entries relating to a given permission
  --cg=CG               Only show entries relating to a given content
                        generator
  --external-repo=EXTERNAL_REPO, --erepo=EXTERNAL_REPO
                        Only show entries relating to a given external repo
  --build-target=BUILD_TARGET, --target=BUILD_TARGET
                        Only show entries relating to a given build target
  --group=GROUP         Only show entries relating to a given group
  --host=HOST           Only show entries related to given host
  --channel=CHANNEL     Only show entries related to given channel
  --xkey=XKEY           Only show entries related to given tag extra key
  --before=BEFORE       Only show entries before this time, time is specified
                        as timestamp or date/time in any format which can be
                        parsed by dateutil.parser. e.g. "2020-12-31 12:35" or
                        "December 31st 12:35"
  --after=AFTER         Only show entries after timestamp (same format as for
                        --before)
  --before-event=EVENT_ID
                        Only show entries before event
  --after-event=EVENT_ID
                        Only show entries after event
  --watch               Monitor history data
  --active              Only show entries that are currently active
  --revoked             Only show entries that are currently revoked
  --context             Show related entries
  -s SHOW, --show=SHOW  Show data from selected tables
  -v, --verbose         Show more detail
  -e, --events          Show event ids
  --all                 Allows listing the entire global history
""" % self.progname)


if __name__ == '__main__':
    unittest.main()
