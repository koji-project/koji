from __future__ import absolute_import
import mock
import six
import time
try:
    import unittest2 as unittest
except ImportError:
    import unittest

from koji_cli.commands import anon_handle_list_groups
from . import utils


class TestListGroups(utils.CliTestCase):

    # Show long diffs in error output...
    maxDiff = None

    def setUp(self):
        self.session = mock.MagicMock()
        self.options = mock.MagicMock()

        self.activate_session = mock.patch('koji_cli.commands.activate_session').start()
        self.event_from_opts = mock.patch('koji.util.eventFromOpts').start()

        self.error_format = """Usage: %s list-groups [options] <tag> [<group>]
(Specify the --help global option for a list of other help options)

%s: error: {message}
""" % (self.progname, self.progname)

    def tearDown(self):
        mock.patch.stopall()

    @mock.patch('sys.stdout', new_callable=six.StringIO)
    @mock.patch('koji_cli.commands.activate_session')
    @mock.patch('koji_cli.commands.ensure_connection')
    def test_anon_handle_list_groups_argument_error(
            self,
            ensure_connection_mock,
            activate_session_mock,
            stdout):
        """Test anon_handle_list_groups function"""
        expected = self.format_error_message(
            "Incorrect number of arguments")
        for arg in [[], ['tag', 'grp', 'etc']]:
            self.assert_system_exit(
                anon_handle_list_groups,
                self.options,
                self.session,
                arg,
                stderr=expected,
                activate_session=None)
            activate_session_mock.assert_not_called()

    def test_anon_handle_list_groups_list_all(self):
        self.event_from_opts.return_value = {}
        self.__list_groups('', [], '')

    def test_anon_handle_list_groups_list_with_group(self):
        self.event_from_opts.return_value = {}
        self.__list_groups('build', [], '')

        # output should be blank
        self.__list_groups('wrong-grp', [], '')

    def test_anon_handle_list_groups_list_with_event(self):
        self.event_from_opts.return_value = {
            'id': 4,
            'ts': 1234567
        }
        event = {'id': 4, 'timestr': time.asctime(time.localtime(1234567))}
        expected = "Querying at event %(id)i (%(timestr)s)" % event + "\n"
        self.__list_groups('build', ['--ts', '1234567'], expected)

    @mock.patch('koji_cli.commands.ensure_connection')
    def __list_groups(self, query_group, options, expected, ensure_connection_mock):
        _list_tags = [
            {
                'maven_support': False,
                'locked': False,
                'name': 'fedora',
                'perm': None,
                'id': 1,
                'arches': None,
                'maven_include_all': False,
                'perm_id': None
            }, {
                'maven_support': False,
                'locked': False,
                'name': 'fedora-build',
                'perm': None,
                'id': 2,
                'arches': 'x86_64, i386, ppc, ppc64',
                'maven_include_all': False,
                'perm_id': None
            }
        ]

        _get_tag_groups = [
            {
                "grouplist": [],
                "packagelist": [
                    {
                        "package": "bash",
                        "requires": None,
                        "tag_id": 2,
                        "group_id": 1,
                        "type": "mandatory",
                        "basearchonly": None,
                        "blocked": False
                    },
                ],
                "display_name": "build",
                "name": "build",
                "uservisible": True,
                "description": None,
                "tag_id": 2,
                "is_default": None,
                "biarchonly": False,
                "exported": True,
                "langonly": None,
                "group_id": 1,
                "blocked": False
            },
            {
                "grouplist": [
                    {
                        'is_metapkg': False,
                        'name': 'build-base',
                        'tag_id': 2,
                        'req_id': 4,
                        'group_id': 2,
                        'type': 'mandatory',
                        'blocked': False
                    }
                ],
                "packagelist": [
                    {
                        "package": "bash",
                        "requires": None,
                        "tag_id": 2,
                        "group_id": 2,
                        "type": "mandatory",
                        "basearchonly": None,
                        "blocked": False
                    }
                ],
                "display_name": "srpm-build",
                "name": "srpm-build",
                "uservisible": True,
                "description": None,
                "tag_id": 2,
                "is_default": None,
                "biarchonly": False,
                "exported": True,
                "langonly": None,
                "group_id": 2,
                "blocked": False
            },
        ]

        tags = dict([(x['id'], x['name']) for x in _list_tags])
        _group_list = [(x['name'], x) for x in _get_tag_groups]
        _group_list.sort()
        groups = [x[1] for x in _group_list]
        for group in groups:
            if query_group != '' and group['name'] != query_group:
                continue
            expected += "%s  [%s]" % (group['name'], tags.get(group['tag_id'], group['tag_id'])) + "\n"
            for grp in group["grouplist"]:
                grp['tag_name'] = tags.get(grp['tag_id'], grp['tag_id'])
                expected += "  @%(name)s  [%(tag_name)s]" % grp + "\n"
            for pkg in group["packagelist"]:
                pkg['tag_name'] = tags.get(pkg['tag_id'], pkg['tag_id'])
                expected += "  %(package)s: %(basearchonly)s, %(type)s  [%(tag_name)s]" % pkg + "\n"

        #self.session.listTags.return_value = _list_tags
        def get_tag(tag_id, strict=False):
            self.assertFalse(strict)
            for tag in _list_tags:
                if tag['id'] == tag_id:
                    return tag
            return None
        self.session.getTag.side_effect = get_tag
        self.session.getTagGroups.return_value = _get_tag_groups
        args = ['fedora26-build']
        args += [query_group] if query_group != '' else []
        args += options if options else []
        with mock.patch('sys.stdout', new_callable=six.StringIO) as stdout:
            anon_handle_list_groups(self.options, self.session, args)
        self.assert_console_message(stdout, expected)

    def test_anon_handle_list_groups_help(self):
        self.assert_help(
            anon_handle_list_groups,
            """Usage: %s list-groups [options] <tag> [<group>]
(Specify the --help global option for a list of other help options)

Options:
  -h, --help      show this help message and exit
  --event=EVENT#  query at event
  --ts=TIMESTAMP  query at last event before timestamp
  --repo=REPO#    query at event for a repo
  --show-blocked  Show blocked packages and groups
""" % self.progname)


if __name__ == '__main__':
    unittest.main()
