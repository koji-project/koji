import mock
import unittest

import kojihub


class TestGetBuildConfig(unittest.TestCase):

    @mock.patch('kojihub.readFullInheritance')
    @mock.patch('kojihub.get_tag')
    def test_simple_tag(self, get_tag, readFullInheritance):
        tag = 'tag_name'
        get_tag.return_value = {'id': 123, 'name': tag, 'extra': {}}
        readFullInheritance.return_value = []

        taginfo = kojihub.RootExports().getBuildConfig(tag)

        get_tag.assert_called_with(tag, event=None, strict=True)
        readFullInheritance.assert_called_with(123, event=None)

        self.assertEqual(taginfo, {
            'id': 123,
            'name': tag,
            'extra': {},
            'config_inheritance': {'extra': {}, 'arches': None},
        })

    @mock.patch('kojihub.readFullInheritance')
    @mock.patch('kojihub.get_tag')
    def test_basic_inherited(self, get_tag, readFullInheritance):
        tag = 'tag_name'
        get_tag.side_effect = [
            {
                'id': 123,
                'name': tag,
                'extra': {},
                'arches': None,
            },
            {
                'id': 1234,
                'name': 'parent',
                'extra': {'value': 'inherited'},
                'arches': 'x86_64',
            },
        ]
        readFullInheritance.return_value = [
            {
                'child_id': 123,
                'currdepth': 1,
                'filter': [],
                'intransitive': False,
                'maxdepth': None,
                'name': tag,
                'nextdepth': None,
                'noconfig': False,
                'parent_id': 1234,
                'pkg_filter': '',
                'priority': 0
            }
        ]

        taginfo = kojihub.RootExports().getBuildConfig(tag, event=1111)

        get_tag.assert_has_calls([
            mock.call(tag, event=1111, strict=True),
            mock.call(1234, event=1111, strict=True),
        ])
        readFullInheritance.assert_called_with(123, event=1111)

        self.assertEqual(taginfo, {
            'arches': 'x86_64',
            'extra': {'value': 'inherited'},
            'config_inheritance': {
                'arches': {'id': 1234, 'name': 'parent'},
                'extra' : {'value': {'id': 1234, 'name': 'parent'}}
            },
            'id': 123,
            'name': 'tag_name'
        })

    @mock.patch('kojihub.readFullInheritance')
    @mock.patch('kojihub.get_tag')
    def test_inherited_noconfig(self, get_tag, readFullInheritance):
        tag = 'tag_name'
        get_tag.side_effect = [
            {
                'id': 123,
                'name': tag,
                'extra': {},
                'arches': None,
            },
            {
                'id': 1234,
                'name': 'parent',
                'extra': {'value': 'inherited'},
                'arches': 'x86_64',
            },
        ]
        readFullInheritance.return_value = [
            {
                'child_id': 123,
                'currdepth': 1,
                'filter': [],
                'intransitive': False,
                'maxdepth': None,
                'name': tag,
                'nextdepth': None,
                'noconfig': True,
                'parent_id': 1234,
                'pkg_filter': '',
                'priority': 0
            }
        ]

        taginfo = kojihub.RootExports().getBuildConfig(tag, event=1111)

        get_tag.assert_called_once_with(tag, event=1111, strict=True)
        readFullInheritance.assert_called_with(123, event=1111)

        self.assertEqual(taginfo, {
            'arches': None,
            'extra': {},
            'config_inheritance': {'extra': {}, 'arches': None},
            'id': 123,
            'name': 'tag_name'
        })
