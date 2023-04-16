import mock
import os
import time

import koji
import kojihub
import kojihub.kojihub
from .utils import DBQueryTestCase


class TestQueryHistory(DBQueryTestCase):
    def setUp(self):
        super(TestQueryHistory, self).setUp()
        self.maxDiff = None
        self.context = mock.patch('kojihub.kojihub.context').start()
        self.get_tag_id = mock.patch('kojihub.kojihub.get_tag_id').start()
        self.get_build = mock.patch('kojihub.kojihub.get_build').start()
        self.get_id = mock.patch('kojihub.kojihub.get_id').start()
        self.get_package_id = mock.patch('kojihub.kojihub.get_package_id').start()
        self.get_user = mock.patch('kojihub.kojihub.get_user').start()
        self.get_perm_id = mock.patch('kojihub.kojihub.get_perm_id').start()
        self.lookup_name = mock.patch('kojihub.kojihub.lookup_name').start()
        self.get_external_repo_id = mock.patch('kojihub.kojihub.get_external_repo_id').start()
        self.get_build_target_id = mock.patch('kojihub.kojihub.get_build_target_id').start()
        self.get_group_id = mock.patch('kojihub.kojihub.get_group_id').start()
        self.original_timezone = os.environ.get('TZ')
        os.environ['TZ'] = 'UTC'
        time.tzset()

    def tearDown(self):
        if self.original_timezone is None:
            del os.environ['TZ']
        else:
            os.environ['TZ'] = self.original_timezone
        time.tzset()
        mock.patch.stopall()

    def test_not_exist_table(self):
        table_name = 'test-table'
        with self.assertRaises(koji.GenericError) as cm:
            kojihub.query_history(tables=[table_name])
        self.assertEqual(f"No such history table: {table_name}", str(cm.exception))
        self.assertEqual(len(self.queries), 0)

    def test_valid(self):
        self.get_tag_id.return_value = 12
        self.get_build.return_value = {'id': 13}
        self.get_package_id.return_value = 15
        self.get_user.return_value = {'id': 357, 'name': 'test-editor'}
        kojihub.query_history(tables=['user_perms', 'user_groups', 'cg_users', 'tag_inheritance',
                                      'tag_config', 'tag_extra', 'build_target_config',
                                      'external_repo_config', 'host_config', 'host_channels',
                                      'tag_external_repos', 'tag_listing', 'tag_packages',
                                      'tag_package_owners', 'group_config', 'group_req_listing',
                                      'group_package_listing'],
                              tag='test-tag', build='test-build-1.23-1', package='test-pkg',
                              active=True, editor='test-editor', afterEvent=555)
        self.assertEqual(len(self.queries), 1)
        query = self.queries[0]
        self.assertEqual(query.tables, ['tag_listing'])
        self.assertEqual(query.columns, ['tag_listing.create_event > %(afterEvent)i',
                                         'creator.id = %(editor)i',
                                         'tag_listing.revoke_event > %(afterEvent)i',
                                         'revoker.id = %(editor)i', 'tag_listing.active',
                                         'build.state', 'tag_listing.build_id',
                                         'tag_listing.create_event',
                                         "date_part('epoch', ev1.time) AS create_ts",
                                         'tag_listing.creator_id', 'creator.name', 'build.epoch',
                                         'package.name', 'build.release',
                                         'tag_listing.revoke_event',
                                         "date_part('epoch', ev2.time) AS revoke_ts",
                                         'tag_listing.revoker_id', 'revoker.name', 'tag.name',
                                         'tag_listing.tag_id', 'build.version'])
        self.assertEqual(query.clauses, ['active = TRUE', 'build.id = %(build_id)i',
                                         'creator.id = %(editor)i OR revoker.id = %(editor)i',
                                         'package.id = %(pkg_id)i', 'tag.id = %(tag_id)i',
                                         'tag_listing.create_event > %(afterEvent)i OR '
                                         'tag_listing.revoke_event > %(afterEvent)i'])
        self.assertEqual(query.joins,
                         ["events AS ev1 ON ev1.id = create_event",
                          "LEFT OUTER JOIN events AS ev2 ON ev2.id = revoke_event",
                          "users AS creator ON creator.id = creator_id",
                          "LEFT OUTER JOIN users AS revoker ON revoker.id = revoker_id",
                          'build ON build_id = build.id',
                          'package ON build.pkg_id = package.id',
                          'LEFT OUTER JOIN tag ON tag_id = tag.id'])
        self.assertEqual(query.values, {'afterEvent': 555, 'build_id': 13, 'editor': 357,
                                        'pkg_id': 15, 'tag_id': 12})

    def test_group_key(self):
        self.get_group_id.return_value = 24
        kojihub.query_history(group='test-grp')
        self.assertEqual(len(self.queries), 3)
        query = self.queries[0]
        self.assertEqual(query.tables, ['group_config'])
        self.assertEqual(query.columns, ['group_config.active', 'group_config.biarchonly',
                                         'group_config.blocked', 'group_config.create_event',
                                         "date_part('epoch', ev1.time) AS create_ts",
                                         'group_config.creator_id', 'creator.name',
                                         'group_config.description', 'group_config.display_name',
                                         'group_config.exported', 'groups.name',
                                         'group_config.group_id', 'group_config.is_default',
                                         'group_config.langonly', 'group_config.revoke_event',
                                         "date_part('epoch', ev2.time) AS revoke_ts",
                                         'group_config.revoker_id', 'revoker.name', 'tag.name',
                                         'group_config.tag_id', 'group_config.uservisible'])
        self.assertEqual(query.clauses, ['groups.id = %(group_id)i'])
        self.assertEqual(query.joins,
                         ["events AS ev1 ON ev1.id = create_event",
                          "LEFT OUTER JOIN events AS ev2 ON ev2.id = revoke_event",
                          "users AS creator ON creator.id = creator_id",
                          "LEFT OUTER JOIN users AS revoker ON revoker.id = revoker_id",
                          'groups ON group_id = groups.id',
                          'LEFT OUTER JOIN tag ON tag_id = tag.id'])
        self.assertEqual(query.values, {'group_id': 24})
        query = self.queries[1]
        self.assertEqual(query.tables, ['group_package_listing'])
        self.assertEqual(query.columns, ['group_package_listing.active',
                                         'group_package_listing.basearchonly',
                                         'group_package_listing.blocked',
                                         'group_package_listing.create_event',
                                         "date_part('epoch', ev1.time) AS create_ts",
                                         'group_package_listing.creator_id', 'creator.name',
                                         'groups.name', 'group_package_listing.group_id',
                                         'group_package_listing.package',
                                         'group_package_listing.requires',
                                         'group_package_listing.revoke_event',
                                         "date_part('epoch', ev2.time) AS revoke_ts",
                                         'group_package_listing.revoker_id',
                                         'revoker.name', 'tag.name',
                                         'group_package_listing.tag_id',
                                         'group_package_listing.type'])
        self.assertEqual(query.clauses, ['groups.id = %(group_id)i'])
        self.assertEqual(query.joins,
                         ["events AS ev1 ON ev1.id = create_event",
                          "LEFT OUTER JOIN events AS ev2 ON ev2.id = revoke_event",
                          "users AS creator ON creator.id = creator_id",
                          "LEFT OUTER JOIN users AS revoker ON revoker.id = revoker_id",
                          'groups ON group_id = groups.id',
                          'LEFT OUTER JOIN tag ON tag_id = tag.id'])
        self.assertEqual(query.values, {'group_id': 24})

        query = self.queries[2]
        self.assertEqual(query.tables, ['group_req_listing'])
        self.assertEqual(query.columns, ['group_req_listing.active', 'group_req_listing.blocked',
                                         'group_req_listing.create_event',
                                         "date_part('epoch', ev1.time) AS create_ts",
                                         'group_req_listing.creator_id', 'creator.name',
                                         'groups.name', 'group_req_listing.group_id',
                                         'group_req_listing.is_metapkg', 'req.name',
                                         'group_req_listing.req_id',
                                         'group_req_listing.revoke_event',
                                         "date_part('epoch', ev2.time) AS revoke_ts",
                                         'group_req_listing.revoker_id', 'revoker.name',
                                         'tag.name', 'group_req_listing.tag_id',
                                         'group_req_listing.type'])
        self.assertEqual(query.clauses, ['req.id = %(group_id)i'])
        self.assertEqual(query.joins,
                         ["events AS ev1 ON ev1.id = create_event",
                          "LEFT OUTER JOIN events AS ev2 ON ev2.id = revoke_event",
                          "users AS creator ON creator.id = creator_id",
                          "LEFT OUTER JOIN users AS revoker ON revoker.id = revoker_id",
                          'groups ON group_id = groups.id',
                          'LEFT OUTER JOIN tag ON tag_id = tag.id',
                          'LEFT OUTER JOIN groups AS req ON req_id = req.id'])
        self.assertEqual(query.values, {'group_id': 24})

    def test_host_key_and_active_false(self):
        self.get_id.return_value = 22
        kojihub.query_history(host='test-host', active=False)
        self.assertEqual(len(self.queries), 2)
        query = self.queries[0]
        self.assertEqual(query.tables, ['host_channels'])
        self.assertEqual(query.clauses, ['active IS NULL', 'host.id = %(host_id)i'])
        self.assertEqual(query.columns, ['host_channels.active', 'host_channels.channel_id',
                                         'channels.name', 'host_channels.create_event',
                                         "date_part('epoch', ev1.time) AS create_ts",
                                         'host_channels.creator_id', 'creator.name', 'host.name',
                                         'host_channels.host_id', 'host_channels.revoke_event',
                                         "date_part('epoch', ev2.time) AS revoke_ts",
                                         'host_channels.revoker_id', 'revoker.name'])
        self.assertEqual(query.joins,
                         ["events AS ev1 ON ev1.id = create_event",
                          "LEFT OUTER JOIN events AS ev2 ON ev2.id = revoke_event",
                          "users AS creator ON creator.id = creator_id",
                          "LEFT OUTER JOIN users AS revoker ON revoker.id = revoker_id",
                          'LEFT OUTER JOIN host ON host_id = host.id',
                          'LEFT OUTER JOIN channels ON channel_id = channels.id'])
        self.assertEqual(query.values, {'host_id': 22})
        query = self.queries[1]
        self.assertEqual(query.tables, ['host_config'])
        self.assertEqual(query.columns, ['host_config.active', 'host_config.arches',
                                         'host_config.capacity', 'host_config.comment',
                                         'host_config.create_event',
                                         "date_part('epoch', ev1.time) AS create_ts",
                                         'host_config.creator_id', 'creator.name',
                                         'host_config.description', 'host_config.enabled',
                                         'host.name', 'host_config.host_id',
                                         'host_config.revoke_event',
                                         "date_part('epoch', ev2.time) AS revoke_ts",
                                         'host_config.revoker_id', 'revoker.name'])
        self.assertEqual(query.clauses, ['active IS NULL', 'host.id = %(host_id)i'])
        self.assertEqual(query.joins,
                         ["events AS ev1 ON ev1.id = create_event",
                          "LEFT OUTER JOIN events AS ev2 ON ev2.id = revoke_event",
                          "users AS creator ON creator.id = creator_id",
                          "LEFT OUTER JOIN users AS revoker ON revoker.id = revoker_id",
                          'LEFT OUTER JOIN host ON host_id = host.id'])
        self.assertEqual(query.values, {'host_id': 22})

    def test_channel_and_before_event_key(self):
        self.get_id.return_value = 22
        kojihub.query_history(channel='test-channel', beforeEvent=99)
        self.assertEqual(len(self.queries), 1)
        query = self.queries[0]
        self.assertEqual(query.tables, ['host_channels'])
        self.assertEqual(query.clauses, ['channels.id = %(channel_id)i',
                                         'host_channels.create_event < %(beforeEvent)i OR '
                                         'host_channels.revoke_event < %(beforeEvent)i'])
        self.assertEqual(query.columns, ['host_channels.create_event < %(beforeEvent)i',
                                         'host_channels.revoke_event < %(beforeEvent)i',
                                         'host_channels.active', 'host_channels.channel_id',
                                         'channels.name', 'host_channels.create_event',
                                         "date_part('epoch', ev1.time) AS create_ts",
                                         'host_channels.creator_id', 'creator.name', 'host.name',
                                         'host_channels.host_id', 'host_channels.revoke_event',
                                         "date_part('epoch', ev2.time) AS revoke_ts",
                                         'host_channels.revoker_id', 'revoker.name'])
        self.assertEqual(query.joins,
                         ["events AS ev1 ON ev1.id = create_event",
                          "LEFT OUTER JOIN events AS ev2 ON ev2.id = revoke_event",
                          "users AS creator ON creator.id = creator_id",
                          "LEFT OUTER JOIN users AS revoker ON revoker.id = revoker_id",
                          'LEFT OUTER JOIN host ON host_id = host.id',
                          'LEFT OUTER JOIN channels ON channel_id = channels.id'])
        self.assertEqual(query.values, {'beforeEvent': 99, 'channel_id': 22})

    def test_user_and_before_key(self):
        self.get_user.return_value = {'id': 159, 'name': 'test-user'}
        kojihub.query_history(user='test-user', before=1681925020)
        self.assertEqual(len(self.queries), 4)
        query = self.queries[0]
        self.assertEqual(query.tables, ['cg_users'])
        self.assertEqual(query.clauses, ['ev1.time < %(before)s OR ev2.time < %(before)s',
                                         'users.id = %(affected_user_id)i'])
        self.assertEqual(query.columns, ['ev1.time < %(before)s', 'ev2.time < %(before)s',
                                         'cg_users.active', 'cg_users.cg_id',
                                         'content_generator.name', 'cg_users.create_event',
                                         "date_part('epoch', ev1.time) AS create_ts",
                                         'cg_users.creator_id', 'creator.name',
                                         'cg_users.revoke_event',
                                         "date_part('epoch', ev2.time) AS revoke_ts",
                                         'cg_users.revoker_id', 'revoker.name', 'users.name',
                                         'cg_users.user_id'])
        self.assertEqual(query.joins,
                         ["events AS ev1 ON ev1.id = create_event",
                          "LEFT OUTER JOIN events AS ev2 ON ev2.id = revoke_event",
                          "users AS creator ON creator.id = creator_id",
                          "LEFT OUTER JOIN users AS revoker ON revoker.id = revoker_id",
                          'LEFT OUTER JOIN users ON user_id = users.id',
                          'LEFT OUTER JOIN content_generator ON cg_id = content_generator.id'])
        self.assertEqual(query.values, {'affected_user_id': 159, 'before': '2023-04-19 17:23:40'})

        query = self.queries[1]
        self.assertEqual(query.tables, ['tag_package_owners'])
        self.assertEqual(query.clauses, ['ev1.time < %(before)s OR ev2.time < %(before)s',
                                         'owner.id = %(affected_user_id)i'])
        self.assertEqual(query.columns, ['ev1.time < %(before)s', 'ev2.time < %(before)s',
                                         'tag_package_owners.active',
                                         'tag_package_owners.create_event',
                                         "date_part('epoch', ev1.time) AS create_ts",
                                         'tag_package_owners.creator_id', 'creator.name',
                                         'tag_package_owners.owner', 'owner.name', 'package.name',
                                         'tag_package_owners.package_id',
                                         'tag_package_owners.revoke_event',
                                         "date_part('epoch', ev2.time) AS revoke_ts",
                                         'tag_package_owners.revoker_id', 'revoker.name',
                                         'tag.name', 'tag_package_owners.tag_id'])
        self.assertEqual(query.joins,
                         ["events AS ev1 ON ev1.id = create_event",
                          "LEFT OUTER JOIN events AS ev2 ON ev2.id = revoke_event",
                          "users AS creator ON creator.id = creator_id",
                          "LEFT OUTER JOIN users AS revoker ON revoker.id = revoker_id",
                          'LEFT OUTER JOIN package ON package_id = package.id',
                          'LEFT OUTER JOIN tag ON tag_id = tag.id',
                          'LEFT OUTER JOIN users AS owner ON owner = owner.id'])
        self.assertEqual(query.values, {'affected_user_id': 159, 'before': '2023-04-19 17:23:40'})

        query = self.queries[2]
        self.assertEqual(query.tables, ['user_groups'])
        self.assertEqual(query.clauses, ['ev1.time < %(before)s OR ev2.time < %(before)s',
                                         'usergroup.id = %(affected_user_id)i'])
        self.assertEqual(query.columns, ['ev1.time < %(before)s', 'ev2.time < %(before)s',
                                         'user_groups.active', 'user_groups.create_event',
                                         "date_part('epoch', ev1.time) AS create_ts",
                                         'user_groups.creator_id', 'creator.name',
                                         'usergroup.name', 'user_groups.group_id',
                                         'user_groups.revoke_event',
                                         "date_part('epoch', ev2.time) AS revoke_ts",
                                         'user_groups.revoker_id', 'revoker.name',
                                         'users.name', 'user_groups.user_id'])
        self.assertEqual(query.joins,
                         ["events AS ev1 ON ev1.id = create_event",
                          "LEFT OUTER JOIN events AS ev2 ON ev2.id = revoke_event",
                          "users AS creator ON creator.id = creator_id",
                          "LEFT OUTER JOIN users AS revoker ON revoker.id = revoker_id",
                          'LEFT OUTER JOIN users ON user_id = users.id',
                          'users AS usergroup ON group_id = usergroup.id'])
        self.assertEqual(query.values, {'affected_user_id': 159, 'before': '2023-04-19 17:23:40'})

        query = self.queries[3]
        self.assertEqual(query.tables, ['user_perms'])
        self.assertEqual(query.clauses, ['ev1.time < %(before)s OR ev2.time < %(before)s',
                                         'users.id = %(affected_user_id)i'])
        self.assertEqual(query.columns, ['ev1.time < %(before)s', 'ev2.time < %(before)s',
                                         'user_perms.active', 'user_perms.create_event',
                                         "date_part('epoch', ev1.time) AS create_ts",
                                         'user_perms.creator_id', 'creator.name',
                                         'user_perms.perm_id', 'permission.name',
                                         'user_perms.revoke_event',
                                         "date_part('epoch', ev2.time) AS revoke_ts",
                                         'user_perms.revoker_id', 'revoker.name', 'users.name',
                                         'user_perms.user_id'])
        self.assertEqual(query.joins,
                         ["events AS ev1 ON ev1.id = create_event",
                          "LEFT OUTER JOIN events AS ev2 ON ev2.id = revoke_event",
                          "users AS creator ON creator.id = creator_id",
                          "LEFT OUTER JOIN users AS revoker ON revoker.id = revoker_id",
                          'LEFT OUTER JOIN users ON user_id = users.id',
                          'LEFT OUTER JOIN permissions AS permission ON perm_id = permission.id'])
        self.assertEqual(query.values, {'affected_user_id': 159, 'before': '2023-04-19 17:23:40'})

    def test_permission_and_after_key(self):
        self.get_perm_id.return_value = 66
        kojihub.query_history(permission='test-perms', after=1681925020)
        self.assertEqual(len(self.queries), 2)
        query = self.queries[0]
        self.assertEqual(query.tables, ['tag_config'])
        self.assertEqual(query.clauses, ['ev1.time > %(after)s OR ev2.time > %(after)s',
                                         'permission.id = %(perm_id)i'])
        self.assertEqual(query.columns, ['ev1.time > %(after)s', 'ev2.time > %(after)s',
                                         'tag_config.active', 'tag_config.arches',
                                         'tag_config.create_event',
                                         "date_part('epoch', ev1.time) AS create_ts",
                                         'tag_config.creator_id', 'creator.name',
                                         'tag_config.locked', 'tag_config.maven_include_all',
                                         'tag_config.maven_support', 'tag_config.perm_id',
                                         'permission.name', 'tag_config.revoke_event',
                                         "date_part('epoch', ev2.time) AS revoke_ts",
                                         'tag_config.revoker_id', 'revoker.name', 'tag.name',
                                         'tag_config.tag_id'])
        self.assertEqual(query.joins,
                         ["events AS ev1 ON ev1.id = create_event",
                          "LEFT OUTER JOIN events AS ev2 ON ev2.id = revoke_event",
                          "users AS creator ON creator.id = creator_id",
                          "LEFT OUTER JOIN users AS revoker ON revoker.id = revoker_id",
                          'LEFT OUTER JOIN tag ON tag_id = tag.id',
                          'LEFT OUTER JOIN permissions AS permission ON perm_id = permission.id'])
        self.assertEqual(query.values, {'after': '2023-04-19 17:23:40', 'perm_id': 66})

        query = self.queries[1]
        self.assertEqual(query.tables, ['user_perms'])
        self.assertEqual(query.clauses, ['ev1.time > %(after)s OR ev2.time > %(after)s',
                                         'permission.id = %(perm_id)i'])
        self.assertEqual(query.columns, ['ev1.time > %(after)s', 'ev2.time > %(after)s',
                                         'user_perms.active', 'user_perms.create_event',
                                         "date_part('epoch', ev1.time) AS create_ts",
                                         'user_perms.creator_id', 'creator.name',
                                         'user_perms.perm_id', 'permission.name',
                                         'user_perms.revoke_event',
                                         "date_part('epoch', ev2.time) AS revoke_ts",
                                         'user_perms.revoker_id', 'revoker.name', 'users.name',
                                         'user_perms.user_id'])
        self.assertEqual(query.joins,
                         ["events AS ev1 ON ev1.id = create_event",
                          "LEFT OUTER JOIN events AS ev2 ON ev2.id = revoke_event",
                          "users AS creator ON creator.id = creator_id",
                          "LEFT OUTER JOIN users AS revoker ON revoker.id = revoker_id",
                          'LEFT OUTER JOIN users ON user_id = users.id',
                          'LEFT OUTER JOIN permissions AS permission ON perm_id = permission.id'])
        self.assertEqual(query.values, {'after': '2023-04-19 17:23:40', 'perm_id': 66})

    def test_cg_key(self):
        self.lookup_name.return_value = {'id': 147}
        kojihub.query_history(cg='test-cg')
        self.assertEqual(len(self.queries), 1)
        query = self.queries[0]
        self.assertEqual(query.tables, ['cg_users'])
        self.assertEqual(query.clauses, ['content_generator.id = %(cg_id)i'])
        self.assertEqual(query.columns, ['cg_users.active', 'cg_users.cg_id',
                                         'content_generator.name', 'cg_users.create_event',
                                         "date_part('epoch', ev1.time) AS create_ts",
                                         'cg_users.creator_id', 'creator.name',
                                         'cg_users.revoke_event',
                                         "date_part('epoch', ev2.time) AS revoke_ts",
                                         'cg_users.revoker_id', 'revoker.name', 'users.name',
                                         'cg_users.user_id'])
        self.assertEqual(query.joins,
                         ["events AS ev1 ON ev1.id = create_event",
                          "LEFT OUTER JOIN events AS ev2 ON ev2.id = revoke_event",
                          "users AS creator ON creator.id = creator_id",
                          "LEFT OUTER JOIN users AS revoker ON revoker.id = revoker_id",
                          'LEFT OUTER JOIN users ON user_id = users.id',
                          'LEFT OUTER JOIN content_generator ON cg_id = content_generator.id'])
        self.assertEqual(query.values, {'cg_id': 147})

    def test_external_repo_key(self):
        self.get_external_repo_id.return_value = 49
        kojihub.query_history(external_repo='test-ext-repo')
        self.assertEqual(len(self.queries), 2)
        query = self.queries[0]
        self.assertEqual(query.tables, ['external_repo_config'])
        self.assertEqual(query.clauses, ['external_repo.id = %(external_repo_id)i'])
        self.assertEqual(query.columns, ['external_repo_config.active',
                                         'external_repo_config.create_event',
                                         "date_part('epoch', ev1.time) AS create_ts",
                                         'external_repo_config.creator_id', 'creator.name',
                                         'external_repo.name',
                                         'external_repo_config.external_repo_id',
                                         'external_repo_config.revoke_event',
                                         "date_part('epoch', ev2.time) AS revoke_ts",
                                         'external_repo_config.revoker_id', 'revoker.name',
                                         'external_repo_config.url'])
        self.assertEqual(query.joins,
                         ["events AS ev1 ON ev1.id = create_event",
                          "LEFT OUTER JOIN events AS ev2 ON ev2.id = revoke_event",
                          "users AS creator ON creator.id = creator_id",
                          "LEFT OUTER JOIN users AS revoker ON revoker.id = revoker_id",
                          'LEFT OUTER JOIN external_repo ON external_repo_id = external_repo.id'])
        self.assertEqual(query.values, {'external_repo_id': 49})

        query = self.queries[1]
        self.assertEqual(query.tables, ['tag_external_repos'])
        self.assertEqual(query.clauses, ['external_repo.id = %(external_repo_id)i'])
        self.assertEqual(query.columns, ['tag_external_repos.active',
                                         'tag_external_repos.create_event',
                                         "date_part('epoch', ev1.time) AS create_ts",
                                         'tag_external_repos.creator_id', 'creator.name',
                                         'external_repo.name',
                                         'tag_external_repos.external_repo_id',
                                         'tag_external_repos.merge_mode',
                                         'tag_external_repos.priority',
                                         'tag_external_repos.revoke_event',
                                         "date_part('epoch', ev2.time) AS revoke_ts",
                                         'tag_external_repos.revoker_id', 'revoker.name',
                                         'tag.name', 'tag_external_repos.tag_id'
                                         ])
        self.assertEqual(query.joins,
                         ["events AS ev1 ON ev1.id = create_event",
                          "LEFT OUTER JOIN events AS ev2 ON ev2.id = revoke_event",
                          "users AS creator ON creator.id = creator_id",
                          "LEFT OUTER JOIN users AS revoker ON revoker.id = revoker_id",
                          'LEFT OUTER JOIN tag ON tag_id = tag.id',
                          'LEFT OUTER JOIN external_repo ON external_repo_id = external_repo.id'])
        self.assertEqual(query.values, {'external_repo_id': 49})

    def test_build_target_key(self):
        self.get_build_target_id.return_value = 55
        kojihub.query_history(build_target='test-target')
        self.assertEqual(len(self.queries), 1)
        query = self.queries[0]
        self.assertEqual(query.tables, ['build_target_config'])
        self.assertEqual(query.clauses, ['build_target.id = %(build_target_id)i'])
        self.assertEqual(query.columns, ['build_target_config.active',
                                         'build_target_config.build_tag', 'build_tag.name',
                                         'build_target.name',
                                         'build_target_config.build_target_id',
                                         'build_target_config.create_event',
                                         "date_part('epoch', ev1.time) AS create_ts",
                                         'build_target_config.creator_id', 'creator.name',
                                         'build_target_config.dest_tag', 'dest_tag.name',
                                         'build_target_config.revoke_event',
                                         "date_part('epoch', ev2.time) AS revoke_ts",
                                         'build_target_config.revoker_id', 'revoker.name'])
        self.assertEqual(query.joins,
                         ["events AS ev1 ON ev1.id = create_event",
                          "LEFT OUTER JOIN events AS ev2 ON ev2.id = revoke_event",
                          "users AS creator ON creator.id = creator_id",
                          "LEFT OUTER JOIN users AS revoker ON revoker.id = revoker_id",
                          'LEFT OUTER JOIN build_target ON build_target_id = build_target.id',
                          'LEFT OUTER JOIN tag AS build_tag ON build_tag = build_tag.id',
                          'LEFT OUTER JOIN tag AS dest_tag ON dest_tag = dest_tag.id'])
        self.assertEqual(query.values, {'build_target_id': 55})

    def test_xkey_key(self):
        kojihub.query_history(xkey='test-key')
        self.assertEqual(len(self.queries), 1)
        query = self.queries[0]
        self.assertEqual(query.tables, ['tag_extra'])
        self.assertEqual(query.clauses, ['tag_extra.key = %(key)s'])
        self.assertEqual(query.columns, ['tag_extra.active', 'tag_extra.create_event',
                                         "date_part('epoch', ev1.time) AS create_ts",
                                         'tag_extra.creator_id', 'creator.name', 'tag_extra.key',
                                         'tag_extra.revoke_event',
                                         "date_part('epoch', ev2.time) AS revoke_ts",
                                         'tag_extra.revoker_id', 'revoker.name', 'tag.name',
                                         'tag_extra.tag_id', 'tag_extra.value'])
        self.assertEqual(query.joins,
                         ["events AS ev1 ON ev1.id = create_event",
                          "LEFT OUTER JOIN events AS ev2 ON ev2.id = revoke_event",
                          "users AS creator ON creator.id = creator_id",
                          "LEFT OUTER JOIN users AS revoker ON revoker.id = revoker_id",
                          'LEFT OUTER JOIN tag ON tag_id = tag.id'])
        self.assertEqual(query.values, {'key': 'test-key'})
