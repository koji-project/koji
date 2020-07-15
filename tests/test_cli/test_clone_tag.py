from __future__ import absolute_import

import mock
import six
from mock import call

try:
    import unittest2 as unittest
except ImportError:
    import unittest

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
        self.activate_session = mock.patch(
            'koji_cli.commands.activate_session').start()

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
            activate_session=None)
        self.activate_session.assert_not_called()

    def test_handle_clone_tag_not_admin(self):
        args = ['src-tag', 'dst-tag']
        self.session.hasPerm.return_value = False
        self.assert_system_exit(
            handle_clone_tag,
            self.options,
            self.session,
            args,
            stderr=self.format_error_message(
                "This action requires tag or admin privileges"),
            activate_session=None)
        self.activate_session.assert_called_once()
        self.session.hasPerm.assert_has_calls([call('admin'), call('tag')])

    def test_handle_clone_tag_same_tag(self):
        args = ['src-tag', 'src-tag']
        self.assert_system_exit(
            handle_clone_tag,
            self.options,
            self.session,
            args,
            stderr=self.format_error_message(
                "Source and destination tags must be different."),
            activate_session=None)
        self.activate_session.assert_called_once()

    def test_handle_clone_tag_invalid_batch(self):
        args = ['src-tag', 'dst-tag', '--batch=-1']
        self.assert_system_exit(
            handle_clone_tag,
            self.options,
            self.session,
            args,
            stderr=self.format_error_message(
                "batch size must be bigger than zero"),
            activate_session=None)
        self.activate_session.assert_called_once()

    def test_handle_clone_tag_no_srctag(self):
        args = ['src-tag', 'dst-tag']
        self.session.getTag.side_effect = [None, None]
        self.assert_system_exit(
            handle_clone_tag,
            self.options,
            self.session,
            args,
            stderr=self.format_error_message("Unknown src-tag: src-tag"),
            activate_session=None)
        self.activate_session.assert_called_once()
        self.activate_session.getTag.has_called([mock.call('src-tag'),
                                                 mock.call('dst-tag')])

    def test_handle_clone_tag_locked(self):
        args = ['src-tag', 'dst-tag']
        self.session.getTag.side_effect = [{'id': 1,
                                            'locked': True},
                                           {'id': 2,
                                            'locked': False}]
        self.assert_system_exit(
            handle_clone_tag,
            self.options,
            self.session,
            args,
            stderr=self.format_error_message(
                "Error: You are attempting to clone from or to a tag which is locked.\n"
                "Please use --force if this is what you really want to do."),
            activate_session=None)
        self.activate_session.assert_called_once()
        self.activate_session.getTag.has_called([mock.call('src-tag'),
                                                 mock.call('dst-tag')])

    def test_handle_clone_tag_no_config(self):
        args = ['src-tag', 'dst-tag']
        self.session.getTag.side_effect = [{'id': 1,
                                            'locked': False},
                                           None]
        self.assert_system_exit(
            handle_clone_tag,
            self.options,
            self.session,
            args,
            stderr=self.format_error_message(
                "Cannot create tag without specifying --config"),
            activate_session=None)
        self.activate_session.assert_called_once()
        self.activate_session.getTag.has_called([mock.call('src-tag'),
                                                 mock.call('dst-tag')])

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
        self.session.getTag.side_effect = [{'id': 1,
                                            'name': 'src-tag',
                                            'arches': 'arch1 arch2',
                                            'perm_id': 1,
                                            'maven_support': False,
                                            'maven_include_all': True,
                                            'locked': False},
                                           None,
                                           {'id': 2,
                                            'name': 'dst-tag',
                                            'arches': 'arch1 arch2',
                                            'perm_id': 1,
                                            'maven_support': False,
                                            'maven_include_all': True,
                                            'locked': False}]
        handle_clone_tag(self.options, self.session, args)
        self.activate_session.assert_called_once()
        self.session.assert_has_calls([call.hasPerm('admin'),
                                       call.getTag('src-tag', event=None),
                                       call.getTag('dst-tag'),
                                       call.createTag('dst-tag',
                                                      arches='arch1 arch2',
                                                      locked=False,
                                                      maven_include_all=True,
                                                      maven_support=False,
                                                      parent=None, perm=1),
                                       call.getTag('dst-tag', strict=True),
                                       call.listPackages(event=None,
                                                         inherited=True,
                                                         tagID=1),
                                       call.packageListAdd('dst-tag', 'apkg',
                                                           block=False,
                                                           extra_arches='arch4',
                                                           owner='userA'),
                                       call.packageListAdd('dst-tag', 'pkg1',
                                                           block=False,
                                                           extra_arches=None,
                                                           owner='userA'),
                                       call.packageListAdd('dst-tag', 'pkg2',
                                                           block=True,
                                                           extra_arches='arch3 arch4',
                                                           owner='userB'),
                                       call.multiCall(batch=1000),
                                       call.listTagged(1, event=None,
                                                       inherit=None,
                                                       latest=None),
                                       call.tagBuildBypass('dst-tag', {
                                           'owner_name': 'b_owner',
                                           'nvr': 'pkg2-1.0-1',
                                           'package_name': 'pkg2', 'state': 2,
                                           'tag_name': 'src-tag-p',
                                           'name': 'pkg2'}, force=None,
                                                           notify=False),
                                       call.tagBuildBypass('dst-tag', {
                                           'owner_name': 'b_owner',
                                           'nvr': 'pkg1-1.0-1',
                                           'package_name': 'pkg1', 'state': 1,
                                           'tag_name': 'src-tag',
                                           'name': 'pkg1'}, force=None,
                                                           notify=False),
                                       call.tagBuildBypass('dst-tag', {
                                           'owner_name': 'b_owner',
                                           'nvr': 'pkg1-1.0-2',
                                           'package_name': 'pkg1', 'state': 1,
                                           'tag_name': 'src-tag',
                                           'name': 'pkg1'}, force=None,
                                                           notify=False),
                                       call.tagBuildBypass('dst-tag', {
                                           'owner_name': 'b_owner',
                                           'nvr': 'pkg1-1.1-2',
                                           'package_name': 'pkg1', 'state': 1,
                                           'tag_name': 'src-tag',
                                           'name': 'pkg1'}, force=None,
                                                           notify=False),
                                       call.multiCall(batch=1000),
                                       call.getTagGroups('src-tag',
                                                         event=None),
                                       call.groupListAdd('dst-tag', 'group1'),
                                       call.groupPackageListAdd('dst-tag',
                                                                'group1',
                                                                'pkg1',
                                                                block=False),
                                       call.groupPackageListAdd('dst-tag',
                                                                'group1',
                                                                'pkg2',
                                                                block=False),
                                       call.groupListAdd('dst-tag', 'group2'),
                                       call.groupPackageListAdd('dst-tag',
                                                                'group2',
                                                                'apkg',
                                                                block=False),
                                       call.groupPackageListAdd('dst-tag',
                                                                'group2',
                                                                'bpkg',
                                                                block=False),
                                       call.multiCall(batch=1000)])
        self.assert_console_message(stdout, """
List of changes:

    Action  Package                      Blocked    Owner      From Tag  
    ------- ---------------------------- ---------- ---------- ----------
    [new]   apkg                         False      userA      src-tag-p 
    [new]   pkg1                         False      userA      src-tag   
    [new]   pkg2                         True       userB      src-tag-p 

    Action  From/To Package              Build(s)                                 State      Owner      From Tag  
    ------- ---------------------------- ---------------------------------------- ---------- ---------- ----------
    [new]   pkg2                         pkg2-1.0-1                               DELETED    b_owner    src-tag-p 
    [new]   pkg1                         pkg1-1.0-1                               COMPLETE   b_owner    src-tag   
    [new]   pkg1                         pkg1-1.0-2                               COMPLETE   b_owner    src-tag   
    [new]   pkg1                         pkg1-1.1-2                               COMPLETE   b_owner    src-tag   

    Action  Package                      Group                       
    ------- ---------------------------- ----------------------------
    [new]   pkg1                         group1                      
    [new]   pkg2                         group1                      
    [new]   apkg                         group2                      
    [new]   bpkg                         group2                      
""")

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
        self.session.getTag.side_effect = [{'id': 1,
                                            'name': 'src-tag',
                                            'arches': 'arch1 arch2',
                                            'perm_id': 1,
                                            'maven_support': False,
                                            'maven_include_all': True,
                                            'locked': False},
                                           {'id': 2,
                                            'name': 'dst-tag',
                                            'arches': 'arch1 arch2',
                                            'perm_id': 1,
                                            'maven_support': False,
                                            'maven_include_all': True,
                                            'locked': False}]
        handle_clone_tag(self.options, self.session, args)
        self.activate_session.assert_called_once()
        self.session.assert_has_calls([call.hasPerm('admin'),
                                       call.getTag('src-tag', event=None),
                                       call.getTag('dst-tag'),
                                       call.listPackages(event=None,
                                                         inherited=True,
                                                         tagID=1),
                                       call.listPackages(inherited=True,
                                                         tagID=2),
                                       call.listTagged(1, event=None,
                                                       inherit=None,
                                                       latest=None),
                                       call.listTagged(2, inherit=False,
                                                       latest=False),
                                       call.getTagGroups('src-tag',
                                                         event=None),
                                       call.getTagGroups('dst-tag'),
                                       call.packageListAdd('dst-tag', 'pkg2',
                                                           block=True,
                                                           extra_arches='arch3 arch4',
                                                           owner='userB'),
                                       call.multiCall(batch=1000),
                                       call.untagBuildBypass('dst-tag', {
                                           'owner_name': 'b_owner',
                                           'nvr': 'pkg1-2.1-2',
                                           'package_name': 'pkg1', 'state': 1,
                                           'tag_name': 'dst-tag',
                                           'name': 'pkg1'}, force=None,
                                                             notify=False),
                                       call.untagBuildBypass('dst-tag', {
                                           'owner_name': 'b_owner',
                                           'nvr': 'pkg1-0.1-1',
                                           'package_name': 'pkg1', 'state': 1,
                                           'tag_name': 'dst-tag',
                                           'name': 'pkg1'}, force=None,
                                                             notify=False),
                                       call.untagBuildBypass('dst-tag', {
                                           'owner_name': 'b_owner',
                                           'nvr': 'pkg3-1.0-1',
                                           'package_name': 'pkg3', 'state': 1,
                                           'tag_name': 'dst-tag',
                                           'name': 'pkg3'}, force=None,
                                                             notify=False),
                                       call.multiCall(batch=1000),
                                       call.tagBuildBypass('dst-tag', {
                                           'owner_name': 'b_owner',
                                           'nvr': 'pkg1-0.1-1',
                                           'package_name': 'pkg1', 'state': 1,
                                           'tag_name': 'src-tag',
                                           'name': 'pkg1'}, force=None,
                                                           notify=False),
                                       call.tagBuildBypass('dst-tag', {
                                           'owner_name': 'b_owner',
                                           'nvr': 'pkg1-1.0-2',
                                           'package_name': 'pkg1', 'state': 1,
                                           'tag_name': 'src-tag',
                                           'name': 'pkg1'}, force=None,
                                                             notify=False),
                                       call.tagBuildBypass('dst-tag', {
                                           'owner_name': 'b_owner',
                                           'nvr': 'pkg1-1.1-2',
                                           'package_name': 'pkg1', 'state': 1,
                                           'tag_name': 'src-tag',
                                           'name': 'pkg1'}, force=None,
                                                           notify=False),
                                       call.multiCall(batch=1000),
                                       call.multiCall(batch=1000),
                                       call.groupPackageListAdd('dst-tag',
                                                                'group1',
                                                                'pkg2',
                                                                force=None),
                                       call.groupPackageListAdd('dst-tag',
                                                                'group1',
                                                                'pkg3',
                                                                force=None),
                                       call.groupPackageListAdd('dst-tag',
                                                                'group1',
                                                                'pkg4',
                                                                force=None),
                                       call.groupPackageListAdd('dst-tag',
                                                                'group2',
                                                                'bpkg',
                                                                force=None),
                                       call.multiCall(batch=1000),
                                       call.multiCall(batch=1000),
                                       call.packageListBlock('dst-tag',
                                                             'bpkg'),
                                       call.packageListBlock('dst-tag',
                                                             'cpkg'),
                                       call.packageListBlock('dst-tag',
                                                             'dpkg'),
                                       call.multiCall(batch=1000),
                                       call.groupListRemove('dst-tag',
                                                            'group3',
                                                            force=None),
                                       call.groupListBlock('dst-tag',
                                                           'group4'),
                                       call.multiCall(batch=1000),
                                       call.groupPackageListRemove('dst-tag',
                                                                   'group1',
                                                                   'pkg5',
                                                                   force=None),
                                       call.groupPackageListBlock('dst-tag',
                                                                  'group2',
                                                                  'cpkg'),
                                       call.multiCall(batch=1000)])
        self.assert_console_message(stdout, """
List of changes:

    Action  Package                      Blocked    Owner      From Tag  
    ------- ---------------------------- ---------- ---------- ----------
    [add]   pkg2                         True       userB      src-tag-p 
    [blk]   bpkg                         False      userC      src-tag   
    [blk]   cpkg                         True       userC      src-tag-p 
    [blk]   dpkg                         True       userC      src-tag   

    Action  From/To Package              Build(s)                                 State      Owner      From Tag  
    ------- ---------------------------- ---------------------------------------- ---------- ---------- ----------
    [del]   pkg1                         pkg1-2.1-2                               COMPLETE   b_owner    dst-tag   
    [del]   pkg1                         pkg1-0.1-1                               COMPLETE   b_owner    dst-tag   
    [del]   pkg3                         pkg3-1.0-1                               COMPLETE   b_owner    dst-tag   
    [add]   pkg1                         pkg1-0.1-1                               COMPLETE   b_owner    src-tag   
    [add]   pkg1                         pkg1-1.0-2                               COMPLETE   b_owner    src-tag   
    [add]   pkg1                         pkg1-1.1-2                               COMPLETE   b_owner    src-tag   

    Action  Package                      Group                       
    ------- ---------------------------- ----------------------------
    [new]   pkg2                         group1                      
    [new]   pkg3                         group1                      
    [new]   pkg4                         group1                      
    [new]   bpkg                         group2                      
    [del]   cpkg                         group3                      
    [del]   dpkg                         group3                      
    [blk]   epkg                         group4                      
    [blk]   fpkg                         group4                      
    [del]   pkg5                         group1                      
    [blk]   cpkg                         group2                      
""")

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
        self.session.getTag.side_effect = [{'id': 1,
                                            'name': 'src-tag',
                                            'arches': 'arch1 arch2',
                                            'perm_id': 1,
                                            'maven_support': False,
                                            'maven_include_all': True,
                                            'locked': False},
                                           {'id': 2,
                                            'name': 'dst-tag',
                                            'arches': 'arch1 arch2',
                                            'perm_id': 1,
                                            'maven_support': False,
                                            'maven_include_all': True,
                                            'locked': False}]
        handle_clone_tag(self.options, self.session, args)
        self.activate_session.assert_called_once()
        self.assert_console_message(stdout, """
List of changes:

    Action  Package                      Blocked    Owner      From Tag  
    ------- ---------------------------- ---------- ---------- ----------

    Action  From/To Package              Build(s)                                 State      Owner      From Tag  
    ------- ---------------------------- ---------------------------------------- ---------- ---------- ----------
    [add]   pkg                          pkg-0.1-1                                COMPLETE   b_owner    src-tag   
    [add]   pkg                          pkg-1.0-21                               COMPLETE   b_owner    src-tag   
    [add]   pkg                          pkg-1.0-23                               COMPLETE   b_owner    src-tag   

    Action  Package                      Group                       
    ------- ---------------------------- ----------------------------
""")

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
        self.session.getTag.side_effect = [{'id': 1,
                                            'name': 'src-tag',
                                            'arches': 'arch1 arch2',
                                            'perm_id': 1,
                                            'maven_support': False,
                                            'maven_include_all': True,
                                            'locked': False},
                                           {'id': 2,
                                            'name': 'dst-tag',
                                            'arches': 'arch1 arch2',
                                            'perm_id': 1,
                                            'maven_support': False,
                                            'maven_include_all': True,
                                            'locked': False}]
        handle_clone_tag(self.options, self.session, args)
        self.activate_session.assert_called_once()
        self.assert_console_message(stdout, """
List of changes:

    Action  Package                      Blocked    Owner      From Tag  
    ------- ---------------------------- ---------- ---------- ----------

    Action  From/To Package              Build(s)                                 State      Owner      From Tag  
    ------- ---------------------------- ---------------------------------------- ---------- ---------- ----------
    [add]   pkg                          pkg-1.0-21                               COMPLETE   b_owner    src-tag   
    [add]   pkg                          pkg-1.0-23                               COMPLETE   b_owner    src-tag   

    Action  Package                      Group                       
    ------- ---------------------------- ----------------------------
""")

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
        self.session.getTag.side_effect = [{'id': 1,
                                            'name': 'src-tag',
                                            'arches': 'arch1 arch2',
                                            'perm_id': 1,
                                            'maven_support': False,
                                            'maven_include_all': True,
                                            'locked': False},
                                           {'id': 2,
                                            'name': 'dst-tag',
                                            'arches': 'arch1 arch2',
                                            'perm_id': 1,
                                            'maven_support': False,
                                            'maven_include_all': True,
                                            'locked': False}]
        handle_clone_tag(self.options, self.session, args)
        self.activate_session.assert_called_once()
        self.assert_console_message(stdout, """
List of changes:

    Action  Package                      Blocked    Owner      From Tag  
    ------- ---------------------------- ---------- ---------- ----------

    Action  From/To Package              Build(s)                                 State      Owner      From Tag  
    ------- ---------------------------- ---------------------------------------- ---------- ---------- ----------
    [add]   pkg                          pkg-1.0-23                               COMPLETE   b_owner    src-tag   

    Action  Package                      Group                       
    ------- ---------------------------- ----------------------------
""")
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
  -v, --verbose     show changes
  --notify          Send tagging/untagging notifications
  -f, --force       override tag locks if necessary
  -n, --test        test mode
  --batch=SIZE      batch size of multicalls [0 to disable, default: 1000]
""" % self.progname)


if __name__ == '__main__':
    unittest.main()
