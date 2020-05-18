# coding=utf-8
from __future__ import absolute_import
import calendar
import locale
import mock
import optparse
import os
import resource
import six.moves.configparser
import time
import six
try:
    import unittest2 as unittest
except ImportError:
    import unittest

import requests_mock
from mock import call, patch
from datetime import datetime
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


def mock_open():
    """Return the right patch decorator for open"""
    if six.PY2:
        return mock.patch('__builtin__.open')
    else:
        return mock.patch('builtins.open')


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

    @mock_open()
    @mock.patch('tempfile.TemporaryFile')
    def test_openRemoteFile(self, m_TemporaryFile, m_open):
        """Test openRemoteFile function"""

        mocks = [m_open, m_TemporaryFile ]

        topurl = 'http://example.com/koji'
        path = 'relative/file/path'
        url = 'http://example.com/koji/relative/file/path'
        with requests_mock.Mocker() as m_requests:
            m_requests.register_uri('GET', url, text='random content')
            # using topurl, no tempfile
            fo = koji.openRemoteFile(path, topurl)
            self.assertEqual(m_requests.call_count, 1)
            self.assertEqual(m_requests.request_history[0].url, url)
            m_TemporaryFile.assert_called_once_with(dir=None)
            m_open.assert_not_called()
            assert fo is m_TemporaryFile.return_value

        for m in mocks:
            m.reset_mock()

        with requests_mock.Mocker() as m_requests:
            m_requests.register_uri('GET', url, text='random content')

            # using topurl + tempfile
            tempdir = '/tmp/koji/1234'
            fo = koji.openRemoteFile(path, topurl, tempdir=tempdir)
            self.assertEqual(m_requests.call_count, 1)
            self.assertEqual(m_requests.request_history[0].url, url)
            m_TemporaryFile.assert_called_once_with(dir=tempdir)
            m_open.assert_not_called()
            assert fo is m_TemporaryFile.return_value

        for m in mocks:
            m.reset_mock()

        with requests_mock.Mocker() as m_requests:
            m_requests.register_uri('GET', url, text='random content')
            # using topdir
            topdir = '/mnt/mykojidir'
            filename = '/mnt/mykojidir/relative/file/path'
            fo = koji.openRemoteFile(path, topdir=topdir)
            self.assertEqual(m_requests.call_count, 0)
            m_TemporaryFile.assert_not_called()
            m_open.assert_called_once_with(filename)
            assert fo is m_open.return_value

        for m in mocks:
            m.reset_mock()

        with requests_mock.Mocker() as m_requests:
            m_requests.register_uri('GET', url, text='random content')
            # using neither
            with self.assertRaises(koji.GenericError):
                koji.openRemoteFile(path)
            for m in mocks:
                m.assert_not_called()

        for m in mocks:
            m.reset_mock()

        # downloaded size is larger than content-length
        with requests_mock.Mocker() as m_requests:
            text = 'random content'
            m_requests.register_uri('GET', url, text=text,
                    headers = {'Content-Length': "3"})
            m_TemporaryFile.return_value.tell.return_value = len(text)
            with self.assertRaises(koji.GenericError):
                koji.openRemoteFile(path, topurl=topurl)
            m_TemporaryFile.assert_called_once()
            m_TemporaryFile.return_value.tell.assert_called()
            m_open.assert_not_called()

        for m in mocks:
            m.reset_mock()

        # downloaded size is shorter than content-length
        with requests_mock.Mocker() as m_requests:
            text = 'random content'
            m_requests.register_uri('GET', url, text=text,
                    headers = {'Content-Length': "100"})
            m_TemporaryFile.return_value.tell.return_value = len(text)
            with self.assertRaises(koji.GenericError):
                koji.openRemoteFile(path, topurl=topurl)
            m_TemporaryFile.assert_called_once()
            m_TemporaryFile.return_value.tell.assert_called()
            m_open.assert_not_called()

    def test_openRemoteFile_valid_rpm(self):
        # downloaded file is correct rpm
        with requests_mock.Mocker() as m_requests:
            topurl = 'http://example.com/koji'
            path = 'tests/test_lib/data/rpms/test-src-1-1.fc24.src.rpm'
            url = os.path.join(topurl, path)
            m_requests.register_uri('GET', url, body=open(path, 'rb'))
            #with self.assertRaises(koji.GenericError):
            koji.openRemoteFile(path, topurl=topurl)

    def test_openRemoteFile_invalid_rpm(self):
        # downloaded file is correct rpm
        with requests_mock.Mocker() as m_requests:
            topurl = 'http://example.com/koji'
            path = 'file.rpm'
            url = os.path.join(topurl, path)
            m_requests.register_uri('GET', url, text='123')
            with self.assertRaises(koji.GenericError):
                koji.openRemoteFile(path, topurl=topurl)

    def test_joinpath_bad(self):
        bad_joins = [
            ['/foo', '../bar'],
            ['/foo', 'a/b/../../../bar'],
            ['/foo', '/bar'],
            ['/foo//', '/bar'],
            ['/foo', 'bar', 'baz', '/zoo'],
            ]
        for args in bad_joins:
            with self.assertRaises(ValueError):
                koji.util.joinpath(*args)

    def test_joinpath_good(self):
        p = koji.util.joinpath('/foo', 'bar')
        self.assertEquals(p, '/foo/bar')

        p = koji.util.joinpath('/foo', 'bar/../baz')
        self.assertEquals(p, '/foo/baz')

        p = koji.util.joinpath('/foo', 'a/b/c/../../../z')
        self.assertEquals(p, '/foo/z')


class ConfigFileTestCase(unittest.TestCase):
    """Test config file reading functions"""

    def setUp(self):
        self.manager = mock.MagicMock()
        self.manager.logging = mock.patch('koji.logging').start()
        self.manager.isdir = mock.patch("os.path.isdir").start()
        self.manager.isfile = mock.patch("os.path.isfile").start()
        self.manager.access = mock.patch("os.access", return_value=True).start()
        self.manager.cp_clz = mock.patch("six.moves.configparser.ConfigParser",
                                         spec=True).start()
        self.manager.scp_clz = mock.patch("six.moves.configparser.SafeConfigParser",
                                         spec=True).start()
        self.manager.rcp_clz = mock.patch("six.moves.configparser.RawConfigParser",
                                         spec=True).start()
        if six.PY2:
            self.real_parser_clz = self.manager.scp_clz
        else:
            self.real_parser_clz = self.manager.cp_clz
        self.mocks = [self.manager.isdir,
                      self.manager.isfile,
                      self.manager.access,
                      self.manager.open,
                      self.manager.cp_clz,
                      self.manager.scp_clz,
                      self.manager.rcp_clz]

    def reset_mock(self):
        for m in self.mocks:
            m.reset_mock()

    def tearDown(self):
        mock.patch.stopall()

    def test_read_config_files(self):

        # bad config_files
        for files in [0,
                      False,
                      set(),
                      dict(),
                      object(),
                      ('string', True),
                      [('str', True, 'str')],
                      [tuple()],]:
            with self.assertRaises(koji.GenericError):
                koji.read_config_files(files)

        # string as config_files
        files = 'test1.conf'
        self.manager.isdir.return_value = False
        conf = koji.read_config_files(files)
        self.manager.isdir.assert_called_once_with(files)
        if six.PY2:
            self.assertTrue(isinstance(conf,
                                       six.moves.configparser.SafeConfigParser.__class__))
        else:
            self.assertTrue(isinstance(conf,
                                       six.moves.configparser.ConfigParser.__class__))
        self.real_parser_clz.assert_called_once()
        self.real_parser_clz.return_value.read.assert_called_once_with([files])

        # list as config_files
        self.reset_mock()
        files = ['test1.conf', 'test2.conf']
        koji.read_config_files(files)

        self.real_parser_clz.assert_called_once()
        self.real_parser_clz.return_value.read.assert_called_once_with(files)

        # tuple as config_files
        self.reset_mock()
        files = ('test1.conf', 'test2.conf')
        koji.read_config_files(files)

        # raw
        self.reset_mock()
        conf = koji.read_config_files(files, raw=True)
        self.assertTrue(isinstance(conf,
                                   six.moves.configparser.RawConfigParser.__class__))
        self.manager.cp_clz.assert_not_called()
        self.manager.scp_clz.assert_not_called()
        self.manager.rcp_clz.assert_called_once()

        # strict
        # case1, not a file
        self.reset_mock()
        files = [('test1.conf',), ('test2.conf', True)]
        self.manager.isfile.return_value = False
        with self.assertRaises(koji.ConfigurationError) as cm:
            koji.read_config_files(files)
        self.assertEqual(cm.exception.args[0],
                         "Config file test2.conf can't be opened.")

        self.assertEqual(self.manager.isdir.call_count, 2)
        self.assertEqual(self.manager.isfile.call_count, 2)
        self.manager.access.assert_not_called()

        # case2, inaccessible
        self.reset_mock()
        self.manager.isfile.return_value = True
        self.manager.access.return_value = False
        with self.assertRaises(koji.ConfigurationError) as cm:
            koji.read_config_files(files)
        self.assertEqual(cm.exception.args[0],
                         "Config file test2.conf can't be opened.")
        self.assertEqual(self.manager.isdir.call_count, 2)
        self.assertEqual(self.manager.isfile.call_count, 2)
        self.assertEqual(self.manager.access.call_count, 2)

        # directories
        # strict==False
        self.reset_mock()
        files = ['test1.conf', 'gooddir', 'test2.conf', 'emptydir', 'nonexistdir']
        self.manager.isdir.side_effect = lambda f: False \
            if f in ['test1.conf', 'test2.conf', 'nonexistdir'] else True
        self.manager.isfile.side_effect = lambda f: False \
            if f in ['nonexistdir', 'gooddir/test1-4.dir.conf'] else True
        self.manager.access.return_value = True
        with mock.patch("os.listdir", side_effect=[['test1-2.conf',
                                                    'test1-1.conf',
                                                    'test1-3.txt',
                                                    'test1-4.dir.conf'],
                                                   []]) as listdir_mock:
            conf = koji.read_config_files(files)
        listdir_mock.assert_has_calls([call('gooddir'), call('emptydir')])
        self.real_parser_clz.assert_called_once()
        self.real_parser_clz.return_value.read.assert_called_once_with(
            ['test1.conf',
             'gooddir/test1-1.conf',
             'gooddir/test1-2.conf',
             'test2.conf'])
        self.assertEqual(self.manager.isdir.call_count, 5)
        self.assertEqual(self.manager.isfile.call_count, 6)
        self.assertEqual(self.manager.access.call_count, 4)

        # strict==True
        # case1
        self.reset_mock()
        files[1] = ('gooddir', True)
        with mock.patch("os.listdir", return_value=['test1-2.conf',
                                                    'test1-1.conf',
                                                    'test1-3.txt',
                                                    'test1-4.dir.conf']
                        ) as listdir_mock:
            with self.assertRaises(koji.ConfigurationError) as cm:
                conf = koji.read_config_files(files)
        self.assertEqual(cm.exception.args[0],
                         "Config file gooddir/test1-4.dir.conf can't be"
                         " opened.")
        listdir_mock.assert_called_once_with('gooddir')

        # case2
        self.reset_mock()
        files[1] = ('gooddir', False)
        files[3] = ('emptydir', True)
        with mock.patch("os.listdir", side_effect=[['test1-2.conf',
                                                    'test1-1.conf',
                                                    'test1-3.txt',
                                                    'test1-4.dir.conf'],
                                                   []]
                        ) as listdir_mock:
            with self.assertRaises(koji.ConfigurationError) as cm:
                conf = koji.read_config_files(files)
        self.assertEqual(cm.exception.args[0],
                         'No config files found in directory: emptydir')
        self.assertEqual(listdir_mock.call_count, 2)



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
            'p1': set(['p2', 'p3']),
            'p2': set(['p3']),
            'p3': set()
        }
        self.assertEqual(koji.util.tsort(parts),
                         [set(['p3']), set(['p2']), set(['p1'])])
        # success, multi-path
        parts = {
            'p1': set(['p2']),
            'p2': set(['p4']),
            'p3': set(['p4']),
            'p4': set(),
            'p5': set()
        }
        self.assertEqual(koji.util.tsort(parts),
                         [set(['p4', 'p5']), set(['p2', 'p3']), set(['p1'])])
        # failed, missing child 'p4'
        parts = {
            'p1': set(['p2']),
            'p2': set(['p3']),
            'p3': set(['p4'])
        }
        with self.assertRaises(ValueError) as cm:
            koji.util.tsort(parts)
        self.assertEqual(cm.exception.args[0], 'total ordering not possible')

        # failed, circular
        parts = {
            'p1': set(['p2']),
            'p2': set(['p3']),
            'p3': set(['p1'])
        }
        with self.assertRaises(ValueError) as cm:
            koji.util.tsort(parts)
        self.assertEqual(cm.exception.args[0], 'total ordering not possible')

    def _read_conf(self, cfile):
        path = os.path.dirname(__file__)
        with open(path + cfile, 'r') as conf_file:
            if six.PY2:
                config = six.moves.configparser.SafeConfigParser()
                config.readfp(conf_file)
            else:
                config = six.moves.configparser.ConfigParser()
                config.read_file(conf_file)
        return config

    def test_formatChangelog(self):
        """Test formatChangelog function"""
        # force locale to compare 'expect' value
        locale.setlocale(locale.LC_ALL, ('en_US', 'UTF-8'))
        data = [
                {
                    'author': 'Happy Koji User <user1@example.com> - 1.1-1',
                    'date': '2017-10-25 08:00:00',
                    'date_ts': 1508932800,
                    'text': '- Line 1\n- Line 2',
                },
                {
                    'author': u'Happy \u0138\u014dji \u016cs\u0259\u0155 <user2@example.com>',
                    'date': '2017-08-28 08:00:00',
                    'date_ts': 1503921600,
                    'text': '- some changelog entry',
                },
                {
                    'author': 'Koji Admin <admin@example.com> - 1.49-6',
                    'date': datetime(2017, 10, 10, 12, 34, 56),
                    'text': '- mass rebuild',
                }
               ]
        expect = (
'''* Wed Oct 25 2017 Happy Koji User <user1@example.com> - 1.1-1
- Line 1
- Line 2

* Mon Aug 28 2017 Happy ĸōji Ŭsəŕ <user2@example.com>
- some changelog entry

* Tue Oct 10 2017 Koji Admin <admin@example.com> - 1.49-6
- mass rebuild

''')
        result = koji.util.formatChangelog(data)
        self.assertMultiLineEqual(expect, result)

        locale.resetlocale()

    def test_parseTime(self):
        """Test parseTime function"""
        now = datetime.now()
        now_ts = int(calendar.timegm(now.timetuple()))
        self.assertEqual(1507593600, koji.util.parseTime('2017-10-10'))
        self.assertEqual(1507638896, koji.util.parseTime('2017-10-10 12:34:56'))
        self.assertEqual(0, koji.util.parseTime('1970-01-01 00:00:00'))
        self.assertNotEqual(now_ts, koji.util.parseTime(now.strftime("%Y-%m-%d")))
        self.assertEqual(now_ts, koji.util.parseTime(now.strftime("%Y-%m-%d %H:%M:%S")))

        # non time format string
        self.assertEqual(None, koji.util.parseTime('not-a-time-format'))

        time_tests = {
            # invalid month
            '2000-13-32': 'month must be in 1..12',
            # invalid day
            '2000-12-32': 'day is out of range for month',
            # invalid hour
            '2000-12-31 24:61:61': 'hour must be in 0..23',
            # invalid minute
            '2000-12-31 23:61:61': 'minute must be in 0..59',
            # invalid second
            '2000-12-31 23:59:61': 'second must be in 0..59',
            # corner case, leap day
            '1969-2-29': 'day is out of range for month'
        }

        # invalid date test
        for args, err in time_tests.items():
            six.assertRaisesRegex(
                self, ValueError, err, koji.util.parseTime, args)

    def test_duration(self):
        """Test duration function"""
        start = time.time()
        self.assertEqual('0:00', koji.util.duration(start))

        # wait for 2 seconds
        time.sleep(2)
        self.assertEqual('0:02', koji.util.duration(start))

    def test_printList(self):
        """Test printList function"""
        distro = ['fedora', 'rhel', 'centos', 'opensuse']
        self.assertEqual('', koji.util.printList([]))
        self.assertEqual('fedora', koji.util.printList(distro[0:1]))
        self.assertEqual('fedora and rhel', koji.util.printList(distro[0:2]))
        self.assertEqual('fedora, rhel, and centos', koji.util.printList(distro[0:3]))

    def test_multi_fnmatch(self):
        """Test multi_fnmatch function"""
        patterns = "example.py example*.py [0-9]*.py [0-9]_*_exmple.py"
        self.assertTrue(koji.util.multi_fnmatch('example.py', patterns))
        self.assertTrue(koji.util.multi_fnmatch('example.py', patterns.split()))
        self.assertTrue(koji.util.multi_fnmatch('01.py', patterns.split()))
        self.assertTrue(koji.util.multi_fnmatch('01_koji:util_example.py', patterns.split()))
        self.assertTrue(koji.util.multi_fnmatch('example_01.py', patterns.split()))
        self.assertFalse(koji.util.multi_fnmatch('sample.py', patterns.split()))

    def test_filedigestAlgo(self):
        """Test filedigestAlgo function"""
        hdr = {koji.RPM_TAG_FILEDIGESTALGO: None}
        self.assertEqual('md5', koji.util.filedigestAlgo(hdr))

        hdr = {koji.RPM_TAG_FILEDIGESTALGO: 2}
        self.assertEqual('sha1', koji.util.filedigestAlgo(hdr))

        hdr = {koji.RPM_TAG_FILEDIGESTALGO: 4}
        self.assertEqual('unknown', koji.util.filedigestAlgo(hdr))

    @mock.patch('os.WEXITSTATUS', return_value=255)
    @mock.patch('os.WTERMSIG', return_value=19)
    @mock.patch('os.WIFEXITED')
    @mock.patch('os.WIFSIGNALED')
    def test_parseStatus(self, m_signaled, m_exited, m_termsig, m_exit):
        """Test parseStatus function"""
        self.assertEqual('%s was killed by signal %i' % ('test-proc', 19),
                         koji.util.parseStatus(0, 'test-proc'))

        m_signaled.return_value = False
        self.assertEqual('%s exited with status %i' % ('test-proc', 255),
                         koji.util.parseStatus(0, 'test-proc'))

        m_exited.return_value = False
        self.assertEqual('%s terminated for unknown reasons' % ('test-proc'),
                         koji.util.parseStatus(0, 'test-proc'))

        for prefix in [['test', 'proc'], ('test', 'proc')]:
            self.assertEqual(
                '%s terminated for unknown reasons' % (' '.join(prefix)),
                koji.util.parseStatus(0, prefix))

    def test_isSuccess(self):
        """Test isSuccess function"""
        with mock.patch('os.WIFEXITED') as m_exit:
            with mock.patch('os.WEXITSTATUS') as m_exitst:
                # True case
                m_exit.return_value, m_exitst.return_value = True, 0
                self.assertTrue(koji.util.isSuccess(0))

                # False cases
                m_exit.return_value, m_exitst.return_value = True, 1
                self.assertFalse(koji.util.isSuccess(0))
                m_exit.return_value, m_exitst.return_value = False, 255
                self.assertFalse(koji.util.isSuccess(0))

    def test_call_with_argcheck(self):
        """Test call_wit_argcheck function"""
        func = lambda *args, **kargs: True
        self.assertTrue(
            koji.util.call_with_argcheck(
                func, [1, 2, 3], {'para1': 1, 'para2': 2}))

        # exception tests
        func = lambda *args, **kargs: \
            (_ for _ in ()).throw(TypeError('fake-type-error'))
        six.assertRaisesRegex(self, TypeError, 'fake-type-error',
                              koji.util.call_with_argcheck,
                              func, [1, 2, 3], {'para1': 1, 'para2': 2})

        with mock.patch('sys.exc_info') as m_info:
            m_info.side_effect = lambda: \
                [None, None, mock.MagicMock(tb_next=None)]
            six.assertRaisesRegex(self, koji.ParameterError, 'fake-type-error',
                                  koji.util.call_with_argcheck,
                                  func, [1, 2, 3])

    def test_dslice(self):
        """Test dslice function"""
        distro = {'fedora': 1, 'rhel': 2, 'centos': 3}
        self.assertEqual({'fedora': 1}, koji.util.dslice(distro, ['fedora']))

        # slice with non exist key,
        # if strict bit is not set, empty dict should be returned.
        self.assertEqual({},  koji.util.dslice(distro, ['debian'], False))
        # if strict bit is set, KeyError should be raised
        self.assertRaises(KeyError, koji.util.dslice, distro, ['debian'])

    def test_dslice_ex(self):
        """Test dslice_ex function"""
        distro = {'fedora': 1, 'rhel': 2, 'centos': 3}
        self.assertEqual({'rhel': 2, 'centos': 3},
                         koji.util.dslice_ex(distro, ['fedora']))

        # slice with non exist key,
        # if strict bit is not set, original dict should be returned
        self.assertEqual(distro, koji.util.dslice_ex(distro, ['debian'], False))
        # if strict bit is set, KeyError should be raised
        self.assertRaises(KeyError, koji.util.dslice_ex, distro, ['debian'])

    def test_checkForBuilds(self):
        """Test checkForBuilds function"""
        builds = [koji.parse_NVR("pkg-1-r1"),
                  koji.parse_NVR("pkg-1-r2"),
                  koji.parse_NVR("pkg-1.1-r1")]
        latest_builds = [koji.parse_NVR("pkg-1.1-r1")]

        session = mock.MagicMock()
        session.getLatestBuilds = mock.Mock(return_value=latest_builds)
        session.listTagged = mock.Mock(return_value=builds)
        event = mock.MagicMock()

        # latest bit check
        self.assertTrue(koji.util.checkForBuilds(
                            session, 'fedora', (koji.parse_NVR('pkg-1.1-r1'),),
                            event, latest=True))
        self.assertFalse(koji.util.checkForBuilds(
                            session, 'fedora', (koji.parse_NVR('pkg-1.0-r2'),),
                            event, latest=True))

        # all elemnts in builds should exist.
        for b in builds:
            self.assertTrue(
                koji.util.checkForBuilds(session, "pkg-build", (b,), event))

        # non exist build test.
        self.assertEqual(False, koji.util.checkForBuilds(
                                    session, "pkg-build",
                                    (koji.parse_NVR("pkg-1.0-r1"),), event))

    def test_LazyValue(self):
        """Test LazyValue object"""
        init, base, incr = 0, 1, 0
        lv = koji.util.LazyValue(
                lambda x, offset=0: base + x + offset,
                (init,),
                {'offset': incr})
        self.assertEqual(init + base + incr, lv.get())

        base = 2
        self.assertEqual(init + base + incr, lv.get())

        # cache bit test
        init, base, incr = 1, 2, 3
        lv = koji.util.LazyValue(
                lambda x, offset=0: base + x + offset,
                (init,),
                {'offset': incr},
                cache=True)
        self.assertEqual(init + base + incr, lv.get())

        base = 3

        # lv.get should return cached value: 6
        self.assertNotEqual(init + base + incr, lv.get())

    def test_LazyString(self):
        """Test LazyString object"""
        fmt = '[{timestamp}] {greeting} {0}'
        timestamp = int(time.time())

        lstr = koji.util.LazyString(
                lambda fmt, *args, **kwargs:
                fmt.format(*args, timestamp=timestamp, **kwargs),
                (fmt, 'koji'),
                {'greeting': 'hello'})

        self.assertEqual(
            fmt.format('koji', timestamp=timestamp, greeting='hello'),
            str(lstr))

        # non cached string should be different
        prev_str = str(lstr)
        timestamp += 100
        self.assertNotEqual(prev_str, str(lstr))

        # enable caching
        lstr = koji.util.LazyString(
            lambda fmt, *args, **kwargs:
            fmt.format(*args, timestamp=timestamp, **kwargs),
            (fmt, 'koji'),
            {'greeting': 'hello'},
            cache=True)

        prev_str = str(lstr)
        timestamp += 10
        self.assertEqual(prev_str, str(lstr))

    def test_LazyDict(self):
        """Test LazyDict object"""
        name = None
        release = None
        date = None

        # Testing on cache bit enabled.
        ldict = koji.util.LazyDict({})
        ldict.lazyset('name', lambda: name, (), cache=True)

        name = 'fedora'
        self.assertEqual(name, ldict['name'])

        # cached, ldict['name'] should not be changed
        name = 'rhel'
        self.assertNotEqual(name, ldict.get('name'))

        # Testing on cahce bit disabled.
        ldict['name'] = koji.util.LazyValue(lambda: name, ())
        ldict['release'] = koji.util.LazyValue(lambda: release, ())
        ldict['date'] = koji.util.LazyValue(lambda: date, ())

        name, release, date = 'fedora', 26, datetime.now().strftime('%Y%m%d')
        data = {'name': name, 'release': release, 'date': date}
        six.assertCountEqual(self, list(data.items()), list(ldict.items()))
        six.assertCountEqual(self, list(data.items()), [v for v in six.iteritems(ldict)])

        name, release, date = 'rhel', 7, '20171012'
        six.assertCountEqual(self, [name, release, date], list(ldict.values()))
        six.assertCountEqual(self, [name, release, date], [v for v in six.itervalues(ldict)])

        data = {'name': name, 'release': release, 'date': date}
        self.assertEqual(name, ldict.pop('name'))
        data.pop('name')
        six.assertCountEqual(self, list(data.items()), list(ldict.items()))

        (key, value) = ldict.popitem()
        data.pop(key)
        six.assertCountEqual(self, list(data.items()), list(ldict.items()))

        ldict_copy = ldict.copy()
        six.assertCountEqual(self, list(data.items()), list(ldict_copy.items()))

    def test_LazyRecord(self):
        """Test LazyRecord object"""
        # create a list object with lazy attribute
        lobj = koji.util.LazyRecord(list)
        six.assertRaisesRegex(
            self, TypeError, 'object does not support lazy attributes',
            koji.util.lazysetattr, self, 'value', lambda x: x, (100,))

        base, init, inc = 10, 1, 0
        koji.util.lazysetattr(
            lobj, 'lz_value',
            lambda x, offset=0: base + x + inc,
            (init, ),
            {'offset': inc},
            cache=True)

        self.assertEqual(base + init + inc, lobj.lz_value)

        # try to access non exist attribute data, AttributeError should raise
        self.assertRaises(AttributeError, getattr, lobj, 'data')

    def test_HiddenValue(self):
        """Test Hidd object"""
        hv = koji.util.HiddenValue('the plain text message')
        self.assertEqual('[value hidden]', str(hv))
        self.assertEqual('HiddenValue()', repr(hv))

        hv2 = koji.util.HiddenValue(hv)
        self.assertEqual(hv2.value, hv.value)
        self.assertEqual('[value hidden]', str(hv2))
        self.assertEqual('HiddenValue()', repr(hv2))

    def test_eventFromOpts(self):
        """Test eventFromOpts function"""
        timestamp = datetime.now().strftime('%s')
        session = mock.MagicMock()
        event = mock.MagicMock(event=20171010, ts=timestamp, repo=1)

        repo_info = {'create_event': 20171010,
                     'create_ts': timestamp}

        session.getEvent = lambda *args, **kwargs: event if args[0] == 20171010 else None
        session.getLastEvent = lambda *args, **kwargs: event
        session.repoInfo = lambda *args, **kwargs: repo_info if args[0] == 1 else None

        # opts.event = 20171010
        opts = mock.MagicMock(event=20171010)
        self.assertEqual(event, koji.util.eventFromOpts(session, opts))

        # opts.event = 12345678, non exist event
        opts = mock.MagicMock(event=12345678)
        self.assertEqual(None, koji.util.eventFromOpts(session, opts))

        # opts.ts = timestamp
        opts = mock.MagicMock(event='', ts=timestamp)
        self.assertEqual(event, koji.util.eventFromOpts(session, opts))

        # opts.repo = '1'
        opts = mock.MagicMock(event='', ts='', repo=1)
        expect = {'id': repo_info['create_event'],
                  'ts': repo_info['create_ts']}

        actual = koji.util.eventFromOpts(session, opts)
        self.assertNotEqual(None, actual)
        six.assertCountEqual(self, list(expect.items()), list(actual.items()))

        # no event is matched case
        opts = mock.MagicMock(event=0, ts=0, repo=0)
        self.assertEqual(None, koji.util.eventFromOpts(session, opts))

    def test_setup_rlimits(self):
        """Test test_setup_rlimits function"""
        logger = mock.MagicMock()
        options = {
                'RLIMIT_AS':      '',
                'RLIMIT_CORE':    '0',
                'RLIMIT_CPU':     '',
                'RLIMIT_DATA':    '4194304',
                'RLIMIT_FSIZE':   '0',
                'RLIMIT_MEMLOCK': '',
                'RLIMIT_NOFILE':  '768',
                'RLIMIT_NPROC':   '3',
                'RLIMIT_OFILE':   '',
                'RLIMIT_RSS':     '',
                'RLIMIT_STACK':   '4194304'
               }

        # create a resource token <--> id lookup table
        rlimit_lookup = dict([(getattr(resource, k), k) for k in options])

        def _getrlimit(res):
            return (options.get(rlimit_lookup[res], None), 0)

        def _setrlimit(res, limits):
            results[rlimit_lookup[res]] = str(limits[0])

        results = dict([(k, '') for k in options])
        with mock.patch('resource.setrlimit') as m_set:
            with mock.patch('resource.getrlimit') as m_get:
                m_get.side_effect = ValueError('resource.getrlimit-value-error')
                six.assertRaisesRegex(self, ValueError, 'resource.getrlimit-value-error',
                                      koji.util.setup_rlimits, options, logger)

                m_get.side_effect = _getrlimit

                # logger.error test
                koji.util.setup_rlimits({'RLIMIT_AS': 'abcde'}, logger)
                logger.error.assert_called_with('Invalid resource limit: %s=%s',
                                                'RLIMIT_AS',
                                                'abcde')

                koji.util.setup_rlimits({'RLIMIT_AS': '1 2 3 4 5'}, logger)
                logger.error.assert_called_with('Invalid resource limit: %s=%s',
                                                'RLIMIT_AS',
                                                '1 2 3 4 5')

                # exception and logger.error test
                m_set.side_effect = ValueError('resource.setrlimit-value-error')
                koji.util.setup_rlimits({'RLIMIT_AS': '0'}, logger)
                logger.error.assert_called_with('Unable to set %s: %s',
                                                'RLIMIT_AS',
                                                m_set.side_effect)

                # run setrlimit test, the results should be equal to options
                m_set.side_effect = _setrlimit

                # make some noise in options
                test_opt = dict(options)
                test_opt.update({
                    'RLIMIT_CUSTOM':  'fake_rlimit_key',
                    'DBName':         'koji',
                    'DBUser':         'koji',
                    'KojiDir':        '/mnt/koji',
                    'KojiDebug':      True})

                koji.util.setup_rlimits(test_opt, logger)
                six.assertCountEqual(self, results, options)

    def test_adler32_constructor(self):
        """Test adler32_constructor function"""
        chksum = koji.util.adler32_constructor('Wikipedia')  # checksum is 300286872
        self.assertEqual(300286872, chksum.digest())
        self.assertEqual('%08x' % (300286872), chksum.hexdigest())

        copy = chksum.copy()
        self.assertEqual(copy.digest(), chksum.digest())
        self.assertNotEqual(copy, chksum)

        chksum.update('test')       # checksum is equal to adler32(b'test', 300286872)
        self.assertNotEqual(300286872, chksum.digest())
        self.assertNotEqual(copy.digest(), chksum.digest())
        self.assertEqual(614401368, chksum.digest())

    def test_to_list(self):
        l = [1, 2, 3]

        r = koji.util.to_list(l)
        self.assertEqual(l, r)

        it = iter(l)
        r = koji.util.to_list(it)
        self.assertEqual(l, r)

        with self.assertRaises(TypeError):
            koji.util.to_list(1)


class TestRmtree(unittest.TestCase):
    @patch('koji.util._rmtree')
    @patch('os.rmdir')
    @patch('os.chdir')
    @patch('os.getcwd')
    @patch('stat.S_ISDIR')
    @patch('os.lstat')
    def test_rmtree_file(self, lstat, isdir, getcwd, chdir, rmdir, _rmtree):
        """ Tests that the koji.util.rmtree function raises error when the
        path parameter is not a directory.
        """
        stat = mock.MagicMock()
        stat.st_dev = 'dev'
        lstat.return_value = stat
        isdir.return_value = False
        getcwd.return_value = 'cwd'

        with self.assertRaises(koji.GenericError):
            koji.util.rmtree('/mnt/folder/some_file')
        _rmtree.assert_not_called()
        rmdir.assert_not_called()

    @patch('koji.util._rmtree')
    @patch('os.rmdir')
    @patch('os.chdir')
    @patch('os.getcwd')
    @patch('stat.S_ISDIR')
    @patch('os.lstat')
    def test_rmtree_directory(self, lstat, isdir, getcwd, chdir, rmdir, _rmtree):
        """ Tests that the koji.util.rmtree function returns nothing when the path is a directory.
        """
        stat = mock.MagicMock()
        stat.st_dev = 'dev'
        lstat.return_value = stat
        isdir.return_value = True
        getcwd.return_value = 'cwd'
        path = '/mnt/folder'

        self.assertEquals(koji.util.rmtree(path), None)
        chdir.assert_called_with('cwd')
        _rmtree.assert_called_once_with('dev')
        rmdir.assert_called_once_with(path)

    @patch('koji.util._rmtree')
    @patch('os.rmdir')
    @patch('os.chdir')
    @patch('os.getcwd')
    @patch('stat.S_ISDIR')
    @patch('os.lstat')
    def test_rmtree_directory_scrub_failure(self, lstat, isdir, getcwd, chdir, rmdir, _rmtree):
        """ Tests that the koji.util.rmtree function returns a GeneralException
        when the scrub of the files in the directory fails.
        """
        stat = mock.MagicMock()
        stat.st_dev = 'dev'
        lstat.return_value = stat
        isdir.return_value = True
        getcwd.return_value = 'cwd'
        path = '/mnt/folder'
        _rmtree.side_effect = OSError('xyz')

        with self.assertRaises(OSError):
            koji.util.rmtree(path)

    @patch('os.chdir')
    @patch('os.rmdir')
    @patch('koji.util._stripcwd')
    def test_rmtree_internal_empty(self, stripcwd, rmdir, chdir):
        dev = 'dev'
        stripcwd.return_value = []

        koji.util._rmtree(dev)

        stripcwd.assert_called_once_with(dev)
        rmdir.assert_not_called()
        chdir.assert_not_called()

    @patch('os.chdir')
    @patch('os.rmdir')
    @patch('koji.util._stripcwd')
    def test_rmtree_internal_dirs(self, stripcwd, rmdir, chdir):
        dev = 'dev'
        stripcwd.side_effect = (['a', 'b'], [], [])

        koji.util._rmtree(dev)

        stripcwd.assert_has_calls([call(dev), call(dev), call(dev)])
        rmdir.assert_has_calls([call('b'), call('a')])
        chdir.assert_has_calls([call('b'), call('..'), call('a'), call('..')])

    @patch('os.chdir')
    @patch('os.rmdir')
    @patch('koji.util._stripcwd')
    def test_rmtree_internal_fail(self, stripcwd, rmdir, chdir):
        dev = 'dev'
        stripcwd.side_effect = (['a', 'b'], [], [])
        rmdir.side_effect = OSError()

        # don't fail on anything
        koji.util._rmtree(dev)

        stripcwd.assert_has_calls([call(dev), call(dev), call(dev)])
        rmdir.assert_has_calls([call('b'), call('a')])
        chdir.assert_has_calls([call('b'), call('..'), call('a'), call('..')])

    @patch('os.listdir')
    @patch('os.lstat')
    @patch('stat.S_ISDIR')
    @patch('os.unlink')
    def test_stripcwd_empty(dev, unlink, isdir, lstat, listdir):
        # simple empty directory
        dev = 'dev'
        listdir.return_value = []

        koji.util._stripcwd(dev)

        listdir.assert_called_once_with('.')
        unlink.assert_not_called()
        isdir.assert_not_called()
        lstat.assert_not_called()

    @patch('os.listdir')
    @patch('os.lstat')
    @patch('stat.S_ISDIR')
    @patch('os.unlink')
    def test_stripcwd_all(dev, unlink, isdir, lstat, listdir):
        # test valid file + dir
        dev = 'dev'
        listdir.return_value = ['a', 'b']
        st = mock.MagicMock()
        st.st_dev = dev
        st.st_mode = 'mode'
        lstat.return_value = st
        isdir.side_effect = [True, False]

        koji.util._stripcwd(dev)

        listdir.assert_called_once_with('.')
        unlink.assert_called_once_with('b')
        isdir.assert_has_calls([call('mode'), call('mode')])
        lstat.assert_has_calls([call('a'), call('b')])

    @patch('os.listdir')
    @patch('os.lstat')
    @patch('stat.S_ISDIR')
    @patch('os.unlink')
    def test_stripcwd_diffdev(dev, unlink, isdir, lstat, listdir):
        # ignore files on different devices
        dev = 'dev'
        listdir.return_value = ['a', 'b']
        st1 = mock.MagicMock()
        st1.st_dev = dev
        st1.st_mode = 'mode'
        st2 = mock.MagicMock()
        st2.st_dev = 'other_dev'
        st2.st_mode = 'mode'
        lstat.side_effect = [st1, st2]
        isdir.side_effect = [True, False]

        koji.util._stripcwd(dev)

        listdir.assert_called_once_with('.')
        unlink.assert_not_called()
        isdir.assert_called_once_with('mode')
        lstat.assert_has_calls([call('a'), call('b')])

    @patch('os.listdir')
    @patch('os.lstat')
    @patch('stat.S_ISDIR')
    @patch('os.unlink')
    def test_stripcwd_fails(dev, unlink, isdir, lstat, listdir):
        # ignore all unlink errors
        dev = 'dev'
        listdir.return_value = ['a', 'b']
        st = mock.MagicMock()
        st.st_dev = dev
        st.st_mode = 'mode'
        lstat.return_value = st
        isdir.side_effect = [True, False]
        unlink.side_effect = OSError()

        koji.util._stripcwd(dev)

        listdir.assert_called_once_with('.')
        unlink.assert_called_once_with('b')
        isdir.assert_has_calls([call('mode'), call('mode')])
        lstat.assert_has_calls([call('a'), call('b')])

class TestMoveAndSymlink(unittest.TestCase):
    @mock.patch('koji.ensuredir')
    @mock.patch('koji.util.safer_move')
    @mock.patch('os.symlink')
    def test_valid(self, symlink, safer_move, ensuredir):
        koji.util.move_and_symlink('/dir_a/src', '/dir_b/dst', relative=False, create_dir=False)

        ensuredir.assert_not_called()
        safer_move.assert_called_once_with('/dir_a/src', '/dir_b/dst')
        symlink.assert_called_once_with('/dir_b/dst', '/dir_a/src')

    @mock.patch('koji.ensuredir')
    @mock.patch('koji.util.safer_move')
    @mock.patch('os.symlink')
    def test_valid_relative(self, symlink, safer_move, ensuredir):
        koji.util.move_and_symlink('/a/src', '/b/dst', relative=True, create_dir=False)

        safer_move.assert_called_once_with('/a/src', '/b/dst')
        symlink.assert_called_once_with('../b/dst', '/a/src')
        ensuredir.assert_not_called()

    @mock.patch('koji.ensuredir')
    @mock.patch('koji.util.safer_move')
    @mock.patch('os.symlink')
    def test_valid_create_dir(self, symlink, safer_move, ensuredir):
        koji.util.move_and_symlink('a/src', 'b/dst', relative=True, create_dir=True)

        safer_move.assert_called_once_with('a/src', 'b/dst')
        symlink.assert_called_once_with('../b/dst', 'a/src')
        ensuredir.assert_called_once_with('b')

if __name__ == '__main__':
    unittest.main()
