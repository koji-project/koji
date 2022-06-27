from __future__ import absolute_import

import mock
import six
from mock import call

import unittest

import koji
from koji_cli.commands import handle_clone_tag
from . import utils


class TestCloneTag(utils.CliTestCase):
    # Show long diffs in error output...
    maxDiff = None

    def setUp(self):
        self.session = mock.MagicMock()
        self.options = mock.MagicMock()
        self.session.hasPerm.return_value = True
        self.session.getTag.side_effect = [{'id': 1,
                                            'locked': False},
                                           {'id': 2,
                                            'locked': False}]
        self.activate_session = mock.patch('koji_cli.commands.activate_session').start()

        self.error_format = """Usage: %s clone-tag [options] <src-tag> <dst-tag>
clone-tag will create the destination tag if it does not already exist
(Specify the --help global option for a list of other help options)

%s: error: {message}
""" % (self.progname, self.progname)

    def tearDown(self):
        mock.patch.stopall()

    def test_handle_clone_tag_missing_arg(self):
        args = ['some-tag']
        self.assert_system_exit(
            handle_clone_tag,
            self.options,
            self.session,
            args,
            stderr=self.format_error_message(
                "This command takes two arguments: <src-tag> <dst-tag>"),
            activate_session=None,
            exit_code=2
        )
        self.activate_session.assert_not_called()

    def test_handle_clone_tag_not_admin(self):
        args = ['src-tag', 'dst-tag']
        self.session.hasPerm.return_value = False
        self.assert_system_exit(
            handle_clone_tag,
            self.options,
            self.session,
            args,
            stderr=self.format_error_message("This action requires tag or admin privileges"),
            activate_session=None,
            exit_code=2
        )
        self.activate_session.assert_called_once()
        self.session.hasPerm.assert_has_calls([call('admin'), call('tag')])

    def test_handle_clone_tag_same_tag(self):
        args = ['src-tag', 'src-tag']
        self.assert_system_exit(
            handle_clone_tag,
            self.options,
            self.session,
            args,
            stderr=self.format_error_message("Source and destination tags must be different."),
            activate_session=None,
            exit_code=2)
        self.activate_session.assert_called_once()

    def test_handle_clone_tag_invalid_batch(self):
        args = ['src-tag', 'dst-tag', '--batch=-1']
        self.assert_system_exit(
            handle_clone_tag,
            self.options,
            self.session,
            args,
            stderr=self.format_error_message("batch size must be bigger than zero"),
            activate_session=None,
            exit_code=2)
        self.activate_session.assert_called_once()

    def test_handle_clone_tag_no_srctag(self):
        args = ['src-tag', 'dst-tag']
        self.session.getBuildConfig.side_effect = koji.GenericError
        self.assert_system_exit(
            handle_clone_tag,
            self.options,
            self.session,
            args,
            stderr=self.format_error_message("No such src-tag: src-tag"),
            activate_session=None,
            exit_code=2)
        self.activate_session.assert_called_once()
        self.activate_session.getTag.has_called([call('src-tag'), call('dst-tag')])

    def test_handle_clone_tag_locked(self):
        args = ['src-tag', 'dst-tag']
        self.session.getTag.side_effect = [{'id': 1, 'locked': True},
                                           {'id': 2, 'locked': False}]
        self.assert_system_exit(
            handle_clone_tag,
            self.options,
            self.session,
            args,
            stderr=self.format_error_message(
                "Error: You are attempting to clone from or to a tag which is locked.\n"
                "Please use --force if this is what you really want to do."),
            activate_session=None,
            exit_code=2)
        self.activate_session.assert_called_once()
        self.activate_session.getTag.has_called([call('src-tag'), call('dst-tag')])

        self.activate_session.getTag.has_called([call('src-tag'), call('dst-tag')])

    @mock.patch('sys.stdout', new_callable=six.StringIO)
    def test_handle_clone_tag_new_dsttag(self, stdout):
        args = ['src-tag', 'dst-tag', '--all', '-v']
        self.session.listPackages.return_value = [{'package_id': 1,
                                                   'package_name': 'pkg1',
                                                   'blocked': False,
                                                   'owner_name': 'userA',
                                                   'tag_name': 'src-tag',
                                                   'extra_arches': None},
                                                  {'package_id': 2,
                                                   'package_name': 'pkg2',
                                                   'blocked': True,
                                                   'owner_name': 'userB',
                                                   'tag_name': 'src-tag-p',
                                                   'extra_arches': 'arch3 arch4'},
                                                  {'package_id': 3,
                                                   'package_name': 'apkg',
                                                   'blocked': False,
                                                   'owner_name': 'userA',
                                                   'tag_name': 'src-tag-p',
                                                   'extra_arches': 'arch4'}]
        self.session.listTagged.return_value = [{'package_name': 'pkg1',
                                                 'nvr': 'pkg1-1.1-2',
                                                 'state': 1,
                                                 'owner_name': 'b_owner',
                                                 'tag_name': 'src-tag'},
                                                {'package_name': 'pkg1',
                                                 'nvr': 'pkg1-1.0-2',
                                                 'state': 1,
                                                 'owner_name': 'b_owner',
                                                 'tag_name': 'src-tag'},
                                                {'package_name': 'pkg1',
                                                 'nvr': 'pkg1-1.0-1',
                                                 'state': 1,
                                                 'owner_name': 'b_owner',
                                                 'tag_name': 'src-tag'},
                                                {'package_name': 'pkg2',
                                                 'nvr': 'pkg2-1.0-1',
                                                 'state': 2,
                                                 'owner_name': 'b_owner',
                                                 'tag_name': 'src-tag-p'}
                                                ]
        self.session.getTagGroups.return_value = [{'name': 'group1',
                                                   'packagelist': [
                                                       {'package': 'pkg1',
                                                        'blocked': False},
                                                       {'package': 'pkg2',
                                                        'blocked': False}]},
                                                  {'name': 'group2',
                                                   'packagelist': [
                                                       {'package': 'apkg',
                                                        'blocked': False},
                                                       {'package': 'bpkg',
                                                        'blocked': False}]
                                                   }]
        self.session.getTag.side_effect = [None,
                                           {'id': 2,
                                            'name': 'dst-tag',
                                            'arches': 'arch1 arch2',
                                            'perm_id': 1,
                                            'maven_support': False,
                                            'maven_include_all': True,
                                            'locked': False,
                                            'extra': {}}]
        self.session.getBuildConfig.side_effect = [{'id': 1,
                                                    'name': 'src-tag',
                                                    'arches': 'arch1 arch2',
                                                    'perm_id': 1,
                                                    'maven_support': False,
                                                    'maven_include_all': True,
                                                    'locked': False,
                                                    'extra': {}},
                                                   ]
        self.session.multiCall.return_value = []
        handle_clone_tag(self.options, self.session, args)
        self.activate_session.assert_called_once()
        self.session.assert_has_calls([call.hasPerm('admin'),
                                       call.getBuildConfig('src-tag', event=None),
                                       call.getTag('dst-tag'),
                                       call.snapshotTag(1, 'dst-tag',
                                                        builds=True, config=True, event=None,
                                                        force=None, groups=True,
                                                        inherit_builds=None, latest_only=None,
                                                        pkgs=True),
                                       ])

    @mock.patch('sys.stdout', new_callable=six.StringIO)
    def test_handle_clone_tag_existing_dsttag(self, stdout):
        args = ['src-tag', 'dst-tag', '--all', '-v']
        self.session.multiCall.return_value = []
        self.session.listPackages.side_effect = [[{'package_id': 1,
                                                   'package_name': 'pkg1',
                                                   'blocked': False,
                                                   'owner_name': 'userA',
                                                   'tag_name': 'src-tag',
                                                   'extra_arches': None},
                                                  {'package_id': 2,
                                                   'package_name': 'pkg2',
                                                   'blocked': True,
                                                   'owner_name': 'userB',
                                                   'tag_name': 'src-tag-p',
                                                   'extra_arches': 'arch3 arch4'},
                                                  {'package_id': 3,
                                                   'package_name': 'apkg',
                                                   'blocked': False,
                                                   'owner_name': 'userA',
                                                   'tag_name': 'src-tag-p',
                                                   'extra_arches': 'arch4'}],
                                                 [{'package_id': 1,
                                                   'package_name': 'pkg1',
                                                   'blocked': False,
                                                   'owner_name': 'userA',
                                                   'tag_name': 'src-tag',
                                                   'extra_arches': None},
                                                  {'package_id': 3,
                                                   'package_name': 'apkg',
                                                   'blocked': False,
                                                   'owner_name': 'userA',
                                                   'tag_name': 'src-tag-p',
                                                   'extra_arches': 'arch4'},
                                                  {'package_id': 4,
                                                   'package_name': 'bpkg',
                                                   'blocked': False,
                                                   'owner_name': 'userC',
                                                   'tag_name': 'src-tag',
                                                   'extra_arches': 'arch4'},
                                                  {'package_id': 5,
                                                   'package_name': 'cpkg',
                                                   'blocked': True,
                                                   'owner_name': 'userC',
                                                   'tag_name': 'src-tag-p',
                                                   'extra_arches': 'arch4'},
                                                  {'package_id': 6,
                                                   'package_name': 'dpkg',
                                                   'blocked': True,
                                                   'owner_name': 'userC',
                                                   'tag_name': 'src-tag',
                                                   'extra_arches': 'arch4'}
                                                  ]]
        self.session.listTagged.side_effect = [[{'package_name': 'pkg1',
                                                 'nvr': 'pkg1-1.1-2',
                                                 'state': 1,
                                                 'owner_name': 'b_owner',
                                                 'tag_name': 'src-tag'},
                                                {'package_name': 'pkg1',
                                                 'nvr': 'pkg1-1.0-2',
                                                 'state': 1,
                                                 'owner_name': 'b_owner',
                                                 'tag_name': 'src-tag'},
                                                {'package_name': 'pkg1',
                                                 'nvr': 'pkg1-0.1-1',
                                                 'state': 1,
                                                 'owner_name': 'b_owner',
                                                 'tag_name': 'src-tag'},
                                                {'package_name': 'pkg1',
                                                 'nvr': 'pkg1-1.0-1',
                                                 'state': 1,
                                                 'owner_name': 'b_owner',
                                                 'tag_name': 'src-tag'},
                                                {'package_name': 'pkg2',
                                                 'nvr': 'pkg2-1.0-1',
                                                 'state': 2,
                                                 'owner_name': 'b_owner',
                                                 'tag_name': 'src-tag-p'}
                                                ],
                                               [{'package_name': 'pkg1',
                                                 'nvr': 'pkg1-2.1-2',
                                                 'state': 1,
                                                 'owner_name': 'b_owner',
                                                 'tag_name': 'dst-tag'},
                                                {'package_name': 'pkg1',
                                                 'nvr': 'pkg1-1.0-1',
                                                 'state': 1,
                                                 'owner_name': 'b_owner',
                                                 'tag_name': 'dst-tag'},
                                                {'package_name': 'pkg1',
                                                 'nvr': 'pkg1-0.1-1',
                                                 'state': 1,
                                                 'owner_name': 'b_owner',
                                                 'tag_name': 'dst-tag'},
                                                {'package_name': 'pkg2',
                                                 'nvr': 'pkg2-1.0-1',
                                                 'state': 2,
                                                 'owner_name': 'b_owner',
                                                 'tag_name': 'dst-tag'},
                                                {'package_name': 'pkg3',
                                                 'nvr': 'pkg3-1.0-1',
                                                 'state': 1,
                                                 'owner_name': 'b_owner',
                                                 'tag_name': 'dst-tag'}
                                                ]]
        self.session.getTagGroups.side_effect = [[{'name': 'group1',
                                                   'tag_id': 1,
                                                   'packagelist': [
                                                       {'package': 'pkg1',
                                                        'blocked': False},
                                                       {'package': 'pkg2',
                                                        'blocked': False},
                                                       {'package': 'pkg3',
                                                        'blocked': False},
                                                       {'package': 'pkg4',
                                                        'blocked': False}
                                                   ]},
                                                  {'name': 'group2',
                                                   'tag_id': 1,
                                                   'packagelist': [
                                                       {'package': 'apkg',
                                                        'blocked': False},
                                                       {'package': 'bpkg',
                                                        'blocked': False}]
                                                   }],
                                                 [{'name': 'group1',
                                                   'tag_id': 2,
                                                   'packagelist': [
                                                       {'package': 'pkg1',
                                                        'blocked': False},
                                                       {'package': 'pkg5',
                                                        'blocked': False}
                                                   ]},
                                                  {'name': 'group2',
                                                   'tag_id': 3,
                                                   'packagelist': [
                                                       {'package': 'apkg',
                                                        'blocked': False},
                                                       {'package': 'cpkg',
                                                        'blocked': False}]},
                                                  {'name': 'group3',
                                                   'tag_id': 2,
                                                   'packagelist': [
                                                       {'package': 'cpkg',
                                                        'blocked': False},
                                                       {'package': 'dpkg',
                                                        'blocked': False}]},
                                                  {'name': 'group4',
                                                   'tag_id': 3,
                                                   'packagelist': [
                                                       {'package': 'epkg',
                                                        'blocked': False},
                                                       {'package': 'fpkg',
                                                        'blocked': False}]}
                                                  ]]
        self.session.getBuildConfig.side_effect = [{'id': 1,
                                                    'name': 'src-tag',
                                                    'arches': 'arch1 arch2',
                                                    'perm_id': 1,
                                                    'maven_support': False,
                                                    'maven_include_all': True,
                                                    'locked': False,
                                                    'extra': {}}]
        self.session.getTag.side_effect = [{'id': 2,
                                            'name': 'dst-tag',
                                            'arches': 'arch1 arch2',
                                            'perm_id': 1,
                                            'maven_support': False,
                                            'maven_include_all': True,
                                            'locked': False,
                                            'extra': {}},
                                           {'id': 2,
                                            'name': 'dst-tag',
                                            'arches': 'arch1 arch2',
                                            'perm_id': 1,
                                            'maven_support': False,
                                            'maven_include_all': True,
                                            'locked': False,
                                            'extra': {}}]
        handle_clone_tag(self.options, self.session, args)
        self.activate_session.assert_called_once()
        self.session.assert_has_calls([call.hasPerm('admin'),
                                       call.getBuildConfig('src-tag', event=None),
                                       call.getTag('dst-tag'),
                                       call.snapshotTagModify(1, 'dst-tag',
                                                              builds=True, config=True,
                                                              event=None, force=None,
                                                              groups=True, inherit_builds=None,
                                                              latest_only=None, pkgs=True,
                                                              remove=True)
                                       ])

    @mock.patch('sys.stdout', new_callable=six.StringIO)
    def test_handle_clone_tag_existing_dsttag_nodelete(self, stdout):
        args = ['src-tag', 'dst-tag', '--all', '-v', '--no-delete']
        self.session.multiCall.return_value = []
        self.session.listPackages.return_value = []
        self.session.listTagged.side_effect = [[{'id': 1,
                                                 'package_name': 'pkg',
                                                 'nvr': 'pkg-1.0-23',
                                                 'state': 1,
                                                 'owner_name': 'b_owner',
                                                 'tag_name': 'src-tag'},
                                                {'id': 2,
                                                 'package_name': 'pkg',
                                                 'nvr': 'pkg-1.0-21',
                                                 'state': 1,
                                                 'owner_name': 'b_owner',
                                                 'tag_name': 'src-tag'},
                                                {'id': 3,
                                                 'package_name': 'pkg',
                                                 'nvr': 'pkg-0.1-1',
                                                 'state': 1,
                                                 'owner_name': 'b_owner',
                                                 'tag_name': 'src-tag'},
                                                ],
                                               [],
                                               ]
        self.session.getTagGroups.return_value = []
        self.session.getBuildConfig.side_effect = [{'id': 1,
                                                    'name': 'src-tag',
                                                    'arches': 'arch1 arch2',
                                                    'perm_id': 1,
                                                    'maven_support': False,
                                                    'maven_include_all': True,
                                                    'locked': False,
                                                    'extra': {}}]
        self.session.getTag.side_effect = [{'id': 2,
                                            'name': 'dst-tag',
                                            'arches': 'arch1 arch2',
                                            'perm_id': 1,
                                            'maven_support': False,
                                            'maven_include_all': True,
                                            'locked': False,
                                            'extra': {}},
                                           {'id': 2,
                                            'name': 'dst-tag',
                                            'arches': 'arch1 arch2',
                                            'perm_id': 1,
                                            'maven_support': False,
                                            'maven_include_all': True,
                                            'locked': False,
                                            'extra': {}}]
        handle_clone_tag(self.options, self.session, args)
        self.activate_session.assert_called_once()

    @mock.patch('sys.stdout', new_callable=six.StringIO)
    def test_handle_clone_tag_existing_dsttag_nodelete_1(self, stdout):
        args = ['src-tag', 'dst-tag', '--all', '-v', '--no-delete']
        self.session.multiCall.return_value = []
        self.session.listPackages.return_value = []
        self.session.listTagged.side_effect = [[{'id': 1,
                                                 'package_name': 'pkg',
                                                 'nvr': 'pkg-1.0-23',
                                                 'state': 1,
                                                 'owner_name': 'b_owner',
                                                 'tag_name': 'src-tag'},
                                                {'id': 2,
                                                 'package_name': 'pkg',
                                                 'nvr': 'pkg-1.0-21',
                                                 'state': 1,
                                                 'owner_name': 'b_owner',
                                                 'tag_name': 'src-tag'},
                                                {'id': 3,
                                                 'package_name': 'pkg',
                                                 'nvr': 'pkg-0.1-1',
                                                 'state': 1,
                                                 'owner_name': 'b_owner',
                                                 'tag_name': 'src-tag'},
                                                ],
                                               [{'id': 1,
                                                 'package_name': 'pkg',
                                                 'nvr': 'pkg-1.0-23',
                                                 'state': 1,
                                                 'owner_name': 'b_owner',
                                                 'tag_name': 'src-tag'},
                                                {'id': 3,
                                                 'package_name': 'pkg',
                                                 'nvr': 'pkg-0.1-1',
                                                 'state': 1,
                                                 'owner_name': 'b_owner',
                                                 'tag_name': 'src-tag'},
                                                {'id': 2,
                                                 'package_name': 'pkg',
                                                 'nvr': 'pkg-1.0-21',
                                                 'state': 1,
                                                 'owner_name': 'b_owner',
                                                 'tag_name': 'src-tag'},
                                                ]
                                               ]
        self.session.getTagGroups.return_value = []
        self.session.getTag.side_effect = [{'id': 2,
                                            'name': 'dst-tag',
                                            'arches': 'arch1 arch2',
                                            'perm_id': 1,
                                            'maven_support': False,
                                            'maven_include_all': True,
                                            'locked': False,
                                            'extra': {}},
                                           {'id': 2,
                                            'name': 'dst-tag',
                                            'arches': 'arch1 arch2',
                                            'perm_id': 1,
                                            'maven_support': False,
                                            'maven_include_all': True,
                                            'locked': False,
                                            'extra': {}}]
        self.session.getBuildConfig.return_value = {
            'id': 1,
            'name': 'src-tag',
            'arches': 'arch1 arch2',
            'perm_id': 1,
            'maven_support': False,
            'maven_include_all': True,
            'locked': False,
            'extra': {}}
        handle_clone_tag(self.options, self.session, args)
        self.activate_session.assert_called_once()

    @mock.patch('sys.stdout', new_callable=six.StringIO)
    def test_handle_clone_tag_existing_dsttag_nodelete_2(self, stdout):
        args = ['src-tag', 'dst-tag', '--all', '-v', '--no-delete']
        self.session.multiCall.return_value = []
        self.session.listPackages.return_value = []
        self.session.listTagged.side_effect = [[{'id': 1,
                                                 'package_name': 'pkg',
                                                 'nvr': 'pkg-1.0-23',
                                                 'state': 1,
                                                 'owner_name': 'b_owner',
                                                 'tag_name': 'src-tag'},
                                                {'id': 2,
                                                 'package_name': 'pkg',
                                                 'nvr': 'pkg-1.0-21',
                                                 'state': 1,
                                                 'owner_name': 'b_owner',
                                                 'tag_name': 'src-tag'},
                                                {'id': 3,
                                                 'package_name': 'pkg',
                                                 'nvr': 'pkg-0.1-1',
                                                 'state': 1,
                                                 'owner_name': 'b_owner',
                                                 'tag_name': 'src-tag'},
                                                ],
                                               [{'id': 2,
                                                 'package_name': 'pkg',
                                                 'nvr': 'pkg-1.0-21',
                                                 'state': 1,
                                                 'owner_name': 'b_owner',
                                                 'tag_name': 'src-tag'},
                                                {'id': 3,
                                                 'package_name': 'pkg',
                                                 'nvr': 'pkg-0.1-1',
                                                 'state': 1,
                                                 'owner_name': 'b_owner',
                                                 'tag_name': 'src-tag'},
                                                ]
                                               ]
        self.session.getTagGroups.return_value = []
        self.session.getTag.side_effect = [{'id': 2,
                                            'name': 'dst-tag',
                                            'arches': 'arch1 arch2',
                                            'perm_id': 1,
                                            'maven_support': False,
                                            'maven_include_all': True,
                                            'locked': False,
                                            'extra': {}},
                                           {'id': 2,
                                            'name': 'dst-tag',
                                            'arches': 'arch1 arch2',
                                            'perm_id': 1,
                                            'maven_support': False,
                                            'maven_include_all': True,
                                            'locked': False,
                                            'extra': {}}]
        self.session.getBuildConfig.side_effect = [{'id': 1,
                                                    'name': 'src-tag',
                                                    'arches': 'arch1 arch2',
                                                    'perm_id': 1,
                                                    'maven_support': False,
                                                    'maven_include_all': True,
                                                    'locked': False,
                                                    'extra': {}},
                                                   ]
        handle_clone_tag(self.options, self.session, args)
        self.activate_session.assert_called_once()

    def test_handle_clone_tag_help(self):
        self.assert_help(
            handle_clone_tag,
            """Usage: %s clone-tag [options] <src-tag> <dst-tag>
clone-tag will create the destination tag if it does not already exist
(Specify the --help global option for a list of other help options)

Options:
  -h, --help        show this help message and exit
  --config          Copy config from the source to the dest tag
  --groups          Copy group information
  --pkgs            Copy package list from the source to the dest tag
  --builds          Tag builds into the dest tag
  --all             The same as --config --groups --pkgs --builds
  --latest-only     Tag only the latest build of each package
  --inherit-builds  Include all builds inherited into the source tag into the
                    dest tag
  --ts=TIMESTAMP    Clone tag at last event before specific timestamp
  --no-delete       Don't delete any existing content in dest tag.
  --event=EVENT     Clone tag at a specific event
  --repo=REPO       Clone tag at a specific repo event
  --notify          Send tagging/untagging notifications
  -f, --force       override tag locks if necessary
  --batch=SIZE      batch size of multicalls [0 to disable, default: 100]
""" % self.progname)


if __name__ == '__main__':
    unittest.main()
