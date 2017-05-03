from __future__ import absolute_import
import mock
import unittest
from mock import call

import os
import optparse
import six.moves.configparser
import koji
import koji.util


class EnumTestCase(unittest.TestCase):

    def test_enum_create_alpha(self):
        """ Test that we can create an Enum with alphabet names """
        koji.Enum(('one', 'two', 'three'))

    def test_enum_bracket_access(self):
        """ Test bracket access. """
        test = koji.Enum(('one', 'two', 'three'))
        self.assertEquals(test['one'], 0)
        self.assertEquals(test['two'], 1)
        self.assertEquals(test['three'], 2)

        with self.assertRaises(KeyError):
            test['does not exist']

    def test_enum_getter_access(self):
        """ Test getter access. """
        test = koji.Enum(('one', 'two', 'three'))
        self.assertEquals(test.get('one'), 0)
        self.assertEquals(test.get('two'), 1)
        self.assertEquals(test.get('three'), 2)
        self.assertEquals(test.get('does not exist'), None)

    def test_enum_slice_access(self):
        """ Test slice access. """
        test = koji.Enum(('one', 'two', 'three'))
        self.assertEquals(test[1:], ('two', 'three'))


class MiscFunctionTestCase(unittest.TestCase):

    @mock.patch('os.path.exists')
    @mock.patch('os.path.islink')
    @mock.patch('shutil.move')
    def test_safer_move(self, move, islink, exists):
        """Test safer_move function"""
        src = '/FAKEPATH/SRC'
        dst = '/FAKEPATH/DST'

        # good args
        exists.return_value = False
        islink.return_value = False
        koji.util.safer_move(src, dst)
        exists.assert_called_once_with(dst)
        islink.assert_called_once_with(dst)
        move.assert_called_once_with(src, dst)

        move.reset_mock()
        islink.reset_mock()
        exists.reset_mock()

        # existing dst
        exists.return_value = True
        with self.assertRaises(koji.GenericError):
            koji.util.safer_move(src, dst)
        exists.assert_called_once_with(dst)
        move.assert_not_called()

        move.reset_mock()
        islink.reset_mock()
        exists.reset_mock()

        # symlink dst
        exists.return_value = False
        islink.return_value = True
        with self.assertRaises(koji.GenericError):
            koji.util.safer_move(src, dst)
        exists.assert_called_once_with(dst)
        islink.assert_called_once_with(dst)
        move.assert_not_called()

    @mock.patch('six.moves.urllib.request.urlopen')
    @mock.patch('tempfile.TemporaryFile')
    @mock.patch('shutil.copyfileobj')
    def test_openRemoteFile(self, m_copyfileobj, m_TemporaryFile,
                            m_urlopen):
        """Test openRemoteFile function"""

        if six.PY2:
            __builtins__.open = mock.MagicMock()
            m_open = __builtins__.open
        else:
            import builtins
            builtins.open = mock.MagicMock()
            m_open = builtins.open
        mocks = [m_open, m_copyfileobj, m_TemporaryFile, m_urlopen]

        topurl = 'http://example.com/koji'
        path = 'relative/file/path'
        url = 'http://example.com/koji/relative/file/path'

        # using topurl, no tempfile
        fo = koji.openRemoteFile(path, topurl)
        m_urlopen.assert_called_once_with(url)
        m_urlopen.return_value.close.assert_called_once()
        m_TemporaryFile.assert_called_once_with(dir=None)
        m_copyfileobj.assert_called_once()
        m_open.assert_not_called()
        assert fo is m_TemporaryFile.return_value

        for m in mocks:
            m.reset_mock()

        # using topurl + tempfile
        tempdir = '/tmp/koji/1234'
        fo = koji.openRemoteFile(path, topurl, tempdir=tempdir)
        m_urlopen.assert_called_once_with(url)
        m_urlopen.return_value.close.assert_called_once()
        m_TemporaryFile.assert_called_once_with(dir=tempdir)
        m_copyfileobj.assert_called_once()
        m_open.assert_not_called()
        assert fo is m_TemporaryFile.return_value

        for m in mocks:
            m.reset_mock()

        # using topdir
        topdir = '/mnt/mykojidir'
        filename = '/mnt/mykojidir/relative/file/path'
        fo = koji.openRemoteFile(path, topdir=topdir)
        m_urlopen.assert_not_called()
        m_TemporaryFile.assert_not_called()
        m_copyfileobj.assert_not_called()
        m_open.assert_called_once_with(filename)
        assert fo is m_open.return_value

        for m in mocks:
            m.reset_mock()

        # using neither
        with self.assertRaises(koji.GenericError):
            koji.openRemoteFile(path)
        for m in mocks:
            m.assert_not_called()


class MavenUtilTestCase(unittest.TestCase):
    """Test maven relative functions"""
    maxDiff = None

    def test_maven_config_opt_adapter(self):
        """Test class MavenConfigOptAdapter"""
        conf = mock.MagicMock()
        section = 'section'
        adapter = koji.util.MavenConfigOptAdapter(conf, section)
        self.assertIs(adapter._conf, conf)
        self.assertIs(adapter._section, section)
        conf.has_option.return_value = True
        adapter.goals
        adapter.properties
        adapter.someattr
        conf.has_option.return_value = False
        with self.assertRaises(AttributeError) as cm:
            adapter.noexistsattr
        self.assertEquals(cm.exception.args[0], 'noexistsattr')
        self.assertEquals(conf.mock_calls, [call.has_option(section, 'goals'),
                                            call.get(section, 'goals'),
                                            call.get().split(),
                                            call.has_option(section, 'properties'),
                                            call.get(section, 'properties'),
                                            call.get().splitlines(),
                                            call.has_option(section, 'someattr'),
                                            call.get('section', 'someattr'),
                                            call.has_option(section, 'noexistsattr')])

    def test_maven_opts(self):
        """Test maven_opts function"""
        values = optparse.Values({
            'scmurl': 'scmurl',
            'patches': 'patchurl',
            'specfile': 'specfile',
            'goals': ['goal1', 'goal2'],
            'profiles': ['profile1', 'profile2'],
            'packages': ['pkg1', 'pkg2'],
            'jvm_options': ['--opt1', '--opt2=val'],
            'maven_options': ['--opt1', '--opt2=val'],
            'properties': ['p1=1', 'p2', 'p3=ppp3'],
            'envs': ['e1=1', 'e2=2'],
            'buildrequires': ['r1', 'r2'],
            'otheropts': 'others'})
        self.assertEqual(koji.util.maven_opts(values), {
            'scmurl': 'scmurl',
            'patches': 'patchurl',
            'specfile': 'specfile',
            'goals': ['goal1', 'goal2'],
            'profiles': ['profile1', 'profile2'],
            'packages': ['pkg1', 'pkg2'],
            'jvm_options': ['--opt1', '--opt2=val'],
            'maven_options': ['--opt1', '--opt2=val'],
            'properties': {'p2': None, 'p3': 'ppp3', 'p1': '1'},
            'envs': {'e1': '1', 'e2': '2'}})
        self.assertEqual(koji.util.maven_opts(values, chain=True, scratch=True), {
            'scmurl': 'scmurl',
            'patches': 'patchurl',
            'specfile': 'specfile',
            'goals': ['goal1', 'goal2'],
            'profiles': ['profile1', 'profile2'],
            'packages': ['pkg1', 'pkg2'],
            'jvm_options': ['--opt1', '--opt2=val'],
            'maven_options': ['--opt1', '--opt2=val'],
            'properties': {'p2': None, 'p3': 'ppp3', 'p1': '1'},
            'envs': {'e1': '1', 'e2': '2'},
            'buildrequires': ['r1', 'r2']})
        self.assertEqual(koji.util.maven_opts(values, chain=False, scratch=True), {
            'scmurl': 'scmurl',
            'patches': 'patchurl',
            'specfile': 'specfile',
            'goals': ['goal1', 'goal2'],
            'profiles': ['profile1', 'profile2'],
            'packages': ['pkg1', 'pkg2'],
            'jvm_options': ['--opt1', '--opt2=val'],
            'maven_options': ['--opt1', '--opt2=val'],
            'properties': {'p2': None, 'p3': 'ppp3', 'p1': '1'},
            'envs': {'e1': '1', 'e2': '2'},
            'scratch': True})
        values = optparse.Values({'envs': ['e1']})
        with self.assertRaises(ValueError) as cm:
            koji.util.maven_opts(values)
        self.assertEqual(
            cm.exception.args[0],
            "Environment variables must be in NAME=VALUE format")

    def test_maven_params(self):
        """Test maven_params function"""
        config = self._read_conf('/data/maven/config.ini')
        self.assertEqual(koji.util.maven_params(config, 'pkg1'), {
            'scmurl': 'scmurl',
            'patches': 'patchurl',
            'specfile': 'specfile',
            'goals': ['goal1', 'goal2'],
            'profiles': ['profile1', 'profile2'],
            'packages': ['pkg1', 'pkg2'],
            'jvm_options': ['--opt1', '--opt2=val'],
            'maven_options': ['--opt1', '--opt2=val'],
            'properties': {'p2': None, 'p3': 'ppp3', 'p1': '1'},
            'envs': {'e1': '1', 'e2': '2'}})

    def test_wrapper_params(self):
        """Test wrapper_params function"""
        config = self._read_conf('/data/maven/config.ini')
        self.assertEqual(koji.util.wrapper_params(config, 'pkg2'), {
            'type': 'maven',
            'scmurl': 'scmurl',
            'buildrequires': ['r1', 'r2'],
            'create_build': True})
        self.assertEqual(koji.util.wrapper_params(config, 'pkg2', scratch=True), {
            'type': 'maven',
            'scmurl': 'scmurl',
            'buildrequires': ['r1', 'r2']})

    def test_parse_maven_params(self):
        """Test parse_maven_params function"""
        path = os.path.dirname(__file__)
        # single conf file, and chain=False, scratch=False
        confs = path + '/data/maven/config.ini'
        self.assertEqual(koji.util.parse_maven_params(confs), {
            'pkg1': {
                'scmurl': 'scmurl',
                'patches': 'patchurl',
                'specfile': 'specfile',
                'goals': ['goal1', 'goal2'],
                'profiles': ['profile1', 'profile2'],
                'packages': ['pkg1', 'pkg2'],
                'jvm_options': ['--opt1', '--opt2=val'],
                'maven_options': ['--opt1', '--opt2=val'],
                'properties': {'p2': None, 'p3': 'ppp3', 'p1': '1'},
                'envs': {'e1': '1', 'e2': '2'}},
            'pkg2': {
                'scmurl': 'scmurl',
                'patches': 'patchurl',
                'specfile': 'specfile',
                'goals': ['goal1', 'goal2'],
                'profiles': ['profile1', 'profile2'],
                'packages': ['pkg1', 'pkg2'],
                'jvm_options': ['--opt1', '--opt2=val'],
                'maven_options': ['--opt1', '--opt2=val'],
                'properties': {'p2': None, 'p3': 'ppp3', 'p1': '1'},
                'envs': {'e1': '1', 'e2': '2'}},
            'pkg3': {
                'type': 'wrapper',
                'scmurl': 'scmurl',
                'buildrequires': ['r1'],
                'create_build': True}})

        # multiple conf file, and chain=True, scratch=False
        confs = [confs, path + '/data/maven/good_config.ini']
        self.assertEqual(koji.util.parse_maven_params(confs, chain=True), {
            'pkg1': {
                'scmurl': 'scmurl',
                'patches': 'patchurl',
                'specfile': 'specfile',
                'goals': ['goal1', 'goal2'],
                'profiles': ['profile1', 'profile2'],
                'packages': ['pkg1', 'pkg2'],
                'jvm_options': ['--opt1', '--opt2=val'],
                'maven_options': ['--opt1', '--opt2=val'],
                'properties': {'p2': None, 'p3': 'ppp3', 'p1': '1'},
                'envs': {'e1': '1', 'e2': '2'},
                'buildrequires': ['r1', 'r2']},
            'pkg2': {
                'scmurl': 'scmurl',
                'patches': 'patchurl',
                'specfile': 'specfile',
                'goals': ['goal1', 'goal2'],
                'profiles': ['profile1', 'profile2'],
                'packages': ['pkg1', 'pkg2'],
                'jvm_options': ['--opt1', '--opt2=val'],
                'maven_options': ['--opt1', '--opt2=val'],
                'properties': {'p2': None, 'p3': 'ppp3', 'p1': '1'},
                'envs': {'e1': '1', 'e2': '2'},
                'buildrequires': ['r1', 'r2']},
            'pkg3': {
                'type': 'wrapper',
                'scmurl': 'scmurl',
                'buildrequires': ['r1'],
                'create_build': True},
            'pkg4': {
                'scmurl': 'scmurl',
                'patches': 'patchurl',
                'specfile': 'specfile',
                'goals': ['goal1', 'goal2'],
                'profiles': ['profile1', 'profile2'],
                'packages': ['pkg1', 'pkg2'],
                'jvm_options': ['--opt1', '--opt2=val'],
                'maven_options': ['--opt1', '--opt2=val'],
                'properties': {'p2': None, 'p3': 'ppp3', 'p1': '1'},
                'envs': {'e1': '1', 'e2': '2'},
                'buildrequires': ['r1', 'r2']},
        })

        # bad conf file - type=wrapper and len(params.get('buildrequires')!=1)
        confs = path + '/data/maven/bad_wrapper_config.ini'
        with self.assertRaises(ValueError) as cm:
            koji.util.parse_maven_params(confs)
        self.assertEqual(
            cm.exception.args[0],
            'A wrapper-rpm must depend on exactly one package')

        # bad conf file - type is neither 'maven' nor 'wrapper')
        confs = path + '/data/maven/bad_type_config.ini'
        with self.assertRaises(ValueError) as cm:
            koji.util.parse_maven_params(confs)
        self.assertEqual(cm.exception.args[0], 'Unsupported build type: other')

        # bad conf file - no scmurl param
        confs = path + '/data/maven/bad_scmurl_config.ini'
        with self.assertRaises(ValueError) as cm:
            koji.util.parse_maven_params(confs)
        self.assertEqual(
            cm.exception.args[0],
            'pkg is missing the scmurl parameter')

        # bad conf file - empty dict returned
        confs = path + '/data/maven/bad_empty_config.ini'
        with self.assertRaises(ValueError) as cm:
            koji.util.parse_maven_params(confs)
        self.assertEqual(
            cm.exception.args[0],
            'No sections found in: %s' %
            confs)

    def test_parse_maven_param(self):
        """Test parse_maven_param function"""
        path = os.path.dirname(__file__)
        # single conf file, and chain=False, scratch=False
        confs = path + '/data/maven/config.ini'
        with mock.patch('koji.util.parse_maven_params',
                        return_value={
                            'pkg1': {'sth': 'pkg1'},
                            'pkg2': {'sth': 'pkg2'},
                            'pkg3': {'sth': 'pkg3'}}):
            self.assertEqual(
                koji.util.parse_maven_param(
                    confs, section='pkg1'), {
                    'pkg1': {
                        'sth': 'pkg1'}})
            with self.assertRaises(ValueError) as cm:
                koji.util.parse_maven_param(confs, section='pkg4')
            self.assertEqual(
                cm.exception.args[0],
                'Section pkg4 does not exist in: %s' %
                confs)
            with self.assertRaises(ValueError) as cm:
                koji.util.parse_maven_param(confs)
            self.assertEqual(
                cm.exception.args[0],
                'Multiple sections in: %s, you must specify the section' %
                confs)
        with mock.patch('koji.util.parse_maven_params', return_value={
                'pkg': {'sth': 'pkg'}}):
            self.assertEqual(koji.util.parse_maven_param(confs),
                             {'pkg': {'sth': 'pkg'}})

    def test_parse_maven_chain(self):
        """Test parse_maven_chain function"""
        path = os.path.dirname(__file__)
        confs = path + '/data/maven/config.ini'
        with mock.patch('koji.util.parse_maven_params',
                        return_value={
                            'pkg1': {'buildrequires': ['pkg2', 'pkg3']},
                            'pkg2': {'buildrequires': ['pkg3']},
                            'pkg3': {'sth': 'sth'}}):
            self.assertEqual(koji.util.parse_maven_chain(confs),
                             {'pkg1': {'buildrequires': ['pkg2', 'pkg3']},
                              'pkg2': {'buildrequires': ['pkg3']},
                              'pkg3': {'sth': 'sth'}})
        # circular deps
        with mock.patch('koji.util.parse_maven_params',
                        return_value={
                            'pkg1': {'buildrequires': ['pkg2', 'pkg3']},
                            'pkg2': {'buildrequires': ['pkg3']},
                            'pkg3': {'buildrequires': ['pkg1']}}):
            with self.assertRaises(ValueError) as cm:
                koji.util.parse_maven_chain(confs)
            self.assertEqual(
                cm.exception.args[0],
                'No possible build order, missing/circular dependencies')
        # missing deps
        with mock.patch('koji.util.parse_maven_params',
                        return_value={
                            'pkg1': {'buildrequires': ['pkg2', 'pkg3']},
                            'pkg2': {'buildrequires': ['pkg3']},
                            'pkg3': {'buildrequires': ['pkg4']}}):
            with self.assertRaises(ValueError) as cm:
                koji.util.parse_maven_chain(confs)
            self.assertEqual(
                cm.exception.args[0],
                'No possible build order, missing/circular dependencies')

    def test_tsort(self):
        # success, one path
        parts = {
            'p1': {'p2', 'p3'},
            'p2': {'p3'},
            'p3': set()
        }
        self.assertEqual(koji.util.tsort(parts),
                         [{'p3'}, {'p2'}, {'p1'}])
        # success, multi-path
        parts = {
            'p1': {'p2'},
            'p2': {'p4'},
            'p3': {'p4'},
            'p4': set(),
            'p5': set()
        }
        self.assertEqual(koji.util.tsort(parts),
                         [{'p4', 'p5'}, {'p2', 'p3'}, {'p1'}])
        # failed, missing child 'p4'
        parts = {
            'p1': {'p2'},
            'p2': {'p3'},
            'p3': {'p4'}
        }
        with self.assertRaises(ValueError) as cm:
            koji.util.tsort(parts)
        self.assertEqual(cm.exception.args[0], 'total ordering not possible')

        # failed, circular
        parts = {
            'p1': {'p2'},
            'p2': {'p3'},
            'p3': {'p1'}
        }
        with self.assertRaises(ValueError) as cm:
            koji.util.tsort(parts)
        self.assertEqual(cm.exception.args[0], 'total ordering not possible')

    def _read_conf(self, cfile):
        config = six.moves.configparser.ConfigParser()
        path = os.path.dirname(__file__)
        with open(path + cfile, 'r') as conf_file:
            config.readfp(conf_file)
        return config


if __name__ == '__main__':
    unittest.main()
