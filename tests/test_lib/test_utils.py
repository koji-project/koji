# coding=utf-8
from __future__ import absolute_import
import calendar
import errno
import locale
import logging
from unittest.case import TestCase
import mock
import multiprocessing
import optparse
import os
import resource
import time
import six
import shutil
import tempfile
import threading
import unittest

import requests_mock
from mock import call, patch
from datetime import datetime
import koji
import koji.util

from koji.util import format_shell_cmd


class EnumTestCase(unittest.TestCase):

    def test_enum_create_alpha(self):
        """ Test that we can create an Enum with alphabet names """
        koji.Enum(('one', 'two', 'three'))

    def test_enum_bracket_access(self):
        """ Test bracket access. """
        test = koji.Enum(('one', 'two', 'three'))
        self.assertEqual(test['one'], 0)
        self.assertEqual(test['two'], 1)
        self.assertEqual(test['three'], 2)

        with self.assertRaises(KeyError):
            test['does not exist']

    def test_enum_getter_access(self):
        """ Test getter access. """
        test = koji.Enum(('one', 'two', 'three'))
        self.assertEqual(test.get('one'), 0)
        self.assertEqual(test.get('two'), 1)
        self.assertEqual(test.get('three'), 2)
        self.assertEqual(test.get('does not exist'), None)

    def test_enum_slice_access(self):
        """ Test slice access. """
        test = koji.Enum(('one', 'two', 'three'))
        self.assertEqual(test[1:], ('two', 'three'))


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

        mocks = [m_open, m_TemporaryFile]

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
            m_open.assert_called_once_with(filename, 'rb')
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
            m_requests.register_uri('GET', url, text=text, headers={'Content-Length': "3"})
            m_TemporaryFile.return_value.tell.return_value = len(text)
            with self.assertRaises(koji.GenericError):
                koji.openRemoteFile(path, topurl=topurl)
            m_TemporaryFile.assert_called_once()
            m_TemporaryFile.return_value.tell.assert_called()

        for m in mocks:
            m.reset_mock()

        # downloaded size is shorter than content-length
        with requests_mock.Mocker() as m_requests:
            text = 'random content'
            m_requests.register_uri('GET', url, text=text, headers={'Content-Length': "100"})
            m_TemporaryFile.return_value.tell.return_value = len(text)
            with self.assertRaises(koji.GenericError):
                koji.openRemoteFile(path, topurl=topurl)
            m_TemporaryFile.assert_called_once()
            m_TemporaryFile.return_value.tell.assert_called()

    def test_openRemoteFile_valid_rpm(self):
        # downloaded file is correct rpm
        with requests_mock.Mocker() as m_requests:
            topurl = 'http://example.com/koji'
            path = 'tests/test_lib/data/rpms/test-src-1-1.fc24.src.rpm'
            url = os.path.join(topurl, path)
            m_requests.register_uri('GET', url, body=open(path, 'rb'))
            # with self.assertRaises(koji.GenericError):
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
        self.assertEqual(p, '/foo/bar')

        p = koji.util.joinpath('/foo', 'bar/../baz')
        self.assertEqual(p, '/foo/baz')

        p = koji.util.joinpath('/foo', 'a/b/c/../../../z')
        self.assertEqual(p, '/foo/z')


class ConfigFileTestCase(unittest.TestCase):
    """Test config file reading functions"""

    def setUp(self):
        self.manager = mock.MagicMock()
        self.manager.logging = mock.patch('koji.logging').start()
        self.manager.isdir = mock.patch("os.path.isdir").start()
        self.manager.isfile = mock.patch("os.path.isfile").start()
        self.manager.access = mock.patch("os.access", return_value=True).start()
        if six.PY2:
            self.manager.scp_clz = mock.patch("ConfigParser.SafeConfigParser",
                                              spec=True).start()
        else:
            self.manager.cp_clz = mock.patch("configparser.ConfigParser",
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
                      [tuple()],
                      ]:
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
        self.assertEqual(cm.exception.args[0], 'noexistsattr')
        self.assertEqual(conf.mock_calls, [call.has_option(section, 'goals'),
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
        with open(path + cfile, 'rt', encoding='utf-8') as conf_file:
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
        expect = ('''* Wed Oct 25 2017 Happy Koji User <user1@example.com> - 1.1-1
- Line 1
- Line 2

* Mon Aug 28 2017 Happy ĸōji Ŭsəŕ <user2@example.com>
- some changelog entry

* Tue Oct 10 2017 Koji Admin <admin@example.com> - 1.49-6
- mass rebuild

''')
        result = koji.util.formatChangelog(data)
        self.assertMultiLineEqual(expect, result)

        locale.setlocale(locale.LC_ALL, "")

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
        self.assertEqual({}, koji.util.dslice(distro, ['debian'], False))
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
            session, 'fedora', (koji.parse_NVR('pkg-1.1-r1'),), event, latest=True))
        self.assertFalse(koji.util.checkForBuilds(
            session, 'fedora', (koji.parse_NVR('pkg-1.0-r2'),), event, latest=True))

        # all elemnts in builds should exist.
        for b in builds:
            self.assertTrue(
                koji.util.checkForBuilds(session, "pkg-build", (b,), event))

        # non exist build test.
        self.assertEqual(False, koji.util.checkForBuilds(
            session, "pkg-build", (koji.parse_NVR("pkg-1.0-r1"),), event))

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
        opts = mock.MagicMock(event=None, ts=timestamp)
        self.assertEqual(event, koji.util.eventFromOpts(session, opts))

        # opts.repo = '1'
        opts = mock.MagicMock(event=None, ts=None, repo=1)
        expect = {'id': repo_info['create_event'],
                  'ts': repo_info['create_ts']}

        actual = koji.util.eventFromOpts(session, opts)
        self.assertNotEqual(None, actual)
        six.assertCountEqual(self, list(expect.items()), list(actual.items()))

        # no event is matched case
        opts = mock.MagicMock(event=None, ts=None, repo=None)
        self.assertEqual(None, koji.util.eventFromOpts(session, opts))

        # special case for ts 0
        opts = mock.MagicMock(event=None, ts=0, repo=None)
        self.assertEqual(event, koji.util.eventFromOpts(session, opts))

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

    def setUp(self):
        # none of these tests should actually do anything with the fs
        # however, just in case, we set up a tempdir and restore cwd
        self.tempdir = tempfile.mkdtemp()
        self.dirname = '%s/some-dir' % self.tempdir
        os.mkdir(self.dirname)
        self.savecwd = os.getcwd()

        self.chdir = mock.patch('os.chdir').start()
        self.rmdir = mock.patch('os.rmdir').start()
        self.unlink = mock.patch('os.unlink').start()
        self.lstat = mock.patch('os.lstat').start()
        self.listdir = mock.patch('os.listdir').start()
        self.getcwd = mock.patch('os.getcwd').start()
        self.isdir = mock.patch('stat.S_ISDIR').start()
        self.samefile = mock.patch('os.path.samefile').start()
        self._assert_cwd = mock.patch('koji.util._assert_cwd').start()

    def tearDown(self):
        mock.patch.stopall()
        os.chdir(self.savecwd)
        shutil.rmtree(self.tempdir)

    @patch('koji.util._rmtree')
    def test_rmtree_file(self, _rmtree):
        """ Tests that the koji.util._rmtree_nofork function raises error when the
        path parameter is not a directory.
        """
        stat = mock.MagicMock()
        stat.st_dev = 'dev'
        self.lstat.return_value = stat
        self.isdir.return_value = False
        self.getcwd.return_value = 'cwd'

        with self.assertRaises(koji.GenericError):
            koji.util._rmtree_nofork(self.dirname)
        _rmtree.assert_not_called()
        self.rmdir.assert_not_called()

    @patch('koji.util._rmtree')
    def test_rmtree_directory(self, _rmtree):
        """ Tests that the koji.util._rmtree_nofork function returns nothing when the path is a directory.
        """
        stat = mock.MagicMock()
        stat.st_dev = 'dev'
        self.lstat.return_value = stat
        self.isdir.return_value = True
        path = self.dirname
        self.getcwd.return_value = path
        logger = mock.MagicMock()

        result = koji.util._rmtree_nofork(path, logger)
        self.assertEqual(result, None)
        self.chdir.assert_called_with(path)
        _rmtree.assert_called_once_with('dev', path, logger)
        self.rmdir.assert_called_once_with(path)

    @patch('koji.util._stripcwd')
    def test_rmtree_directory_stripcwd_failure(self, stripcwd):
        """ Tests that the koji.util._rmtree_nofork function returns a GeneralException
        when the scrub of the files in the directory fails.
        """
        stat = mock.MagicMock()
        stat.st_dev = 'dev'
        self.lstat.return_value = stat
        self.isdir.return_value = True
        self.getcwd.return_value = 'cwd'
        stripcwd.side_effect = OSError('xyz')
        logger = mock.MagicMock()

        with self.assertRaises(OSError):
            koji.util._rmtree('dev', 'cwd', logger)

    @patch('koji.util._rmtree')
    def test_rmtree_call_failure(self, _rmtree):
        """ Tests that the koji.util._rmtree_nofork function returns a GeneralException
        when the underlying _rmtree call fails
        """
        stat = mock.MagicMock()
        stat.st_dev = 'dev'
        self.lstat.return_value = stat
        self.isdir.return_value = True
        self.getcwd.return_value = 'cwd'
        path = self.dirname
        _rmtree.side_effect = OSError('xyz')

        with self.assertRaises(OSError):
            koji.util._rmtree_nofork(path)

    @patch('koji.util._rmtree')
    def test_rmtree_getcwd_mismatch(self, _rmtree):
        """ Tests that the koji.util._rmtree_nofork function returns a GeneralException
        when getcwd disagrees with initial chdir
        """
        stat = mock.MagicMock()
        stat.st_dev = 'dev'
        self.lstat.return_value = stat
        self.isdir.return_value = True
        self.getcwd.return_value = 'cwd'
        path = self.dirname
        self.samefile.return_value = False

        with self.assertRaises(koji.GenericError):
            koji.util._rmtree_nofork(path)

    @patch('koji.util._stripcwd')
    def test_rmtree_internal_empty(self, stripcwd):
        dev = 'dev'
        stripcwd.return_value = []
        logger = mock.MagicMock()

        koji.util._rmtree(dev, self.dirname, logger)

        stripcwd.assert_called_once_with(dev, self.dirname, logger)
        self.rmdir.assert_not_called()
        self.chdir.assert_not_called()

    @patch('koji.util._stripcwd')
    def test_rmtree_internal_dirs(self, stripcwd):
        dev = 'dev'
        stripcwd.side_effect = (['a', 'b'], [], [])
        logger = mock.MagicMock()
        path = self.dirname

        koji.util._rmtree(dev, path, logger)

        stripcwd.assert_has_calls([call(dev, path, logger),
                                   call(dev, path + '/b', logger),
                                   call(dev, path + '/a', logger)])
        self.rmdir.assert_has_calls([call('b'), call('a')])
        self.chdir.assert_has_calls([call('b'), call('..'), call('a'), call('..')])

    @patch('koji.util._stripcwd')
    def test_rmtree_internal_fail(self, stripcwd):
        dev = 'dev'
        stripcwd.side_effect = (['a', 'b'], [], [])
        self.rmdir.side_effect = OSError()
        logger = mock.MagicMock()
        path = self.dirname

        # don't fail on anything
        koji.util._rmtree(dev, path, logger)

        stripcwd.assert_has_calls([call(dev, path, logger),
                                   call(dev, path + '/b', logger),
                                   call(dev, path + '/a', logger)])
        self.rmdir.assert_has_calls([call('b'), call('a')])
        self.chdir.assert_has_calls([call('b'), call('..'), call('a'), call('..')])

    def test_stripcwd_empty(self):
        # simple empty directory
        dev = 'dev'
        self.listdir.return_value = []
        logger = mock.MagicMock()

        koji.util._stripcwd(dev, self.dirname, logger)

        self.listdir.assert_called_once_with('.')
        self.unlink.assert_not_called()
        self.isdir.assert_not_called()
        self.lstat.assert_not_called()

    def test_stripcwd_all(self):
        # test valid file + dir
        dev = 'dev'
        self.listdir.return_value = ['a', 'b']
        st = mock.MagicMock()
        st.st_dev = dev
        st.st_mode = 'mode'
        self.lstat.return_value = st
        self.isdir.side_effect = [True, False]
        logger = mock.MagicMock()

        koji.util._stripcwd(dev, self.dirname, logger)

        self.listdir.assert_called_once_with('.')
        self.unlink.assert_called_once_with('b')
        self.isdir.assert_has_calls([call('mode'), call('mode')])
        self.lstat.assert_has_calls([call('a'), call('b')])

    def test_stripcwd_diffdev(self):
        # ignore files on different devices
        dev = 'dev'
        self.listdir.return_value = ['a', 'b']
        st1 = mock.MagicMock()
        st1.st_dev = dev
        st1.st_mode = 'mode'
        st2 = mock.MagicMock()
        st2.st_dev = 'other_dev'
        st2.st_mode = 'mode'
        self.lstat.side_effect = [st1, st2]
        self.isdir.side_effect = [True, False]
        logger = mock.MagicMock()

        koji.util._stripcwd(dev, self.dirname, logger)

        self.listdir.assert_called_once_with('.')
        self.unlink.assert_not_called()
        self.isdir.assert_called_once_with('mode')
        self.lstat.assert_has_calls([call('a'), call('b')])

    def test_stripcwd_fails(self):
        # ignore all unlink errors
        dev = 'dev'
        self.listdir.return_value = ['a', 'b']
        st = mock.MagicMock()
        st.st_dev = dev
        st.st_mode = 'mode'
        self.lstat.return_value = st
        self.isdir.side_effect = [True, False]
        self.unlink.side_effect = OSError()
        logger = mock.MagicMock()

        koji.util._stripcwd(dev, self.dirname, logger)

        self.listdir.assert_called_once_with('.')
        self.unlink.assert_called_once_with('b')
        self.isdir.assert_has_calls([call('mode'), call('mode')])
        self.lstat.assert_has_calls([call('a'), call('b')])

    def test_stripcwd_stat_fail(self):
        # something else deletes a file in the middle of _stripcwd()
        dev = 'dev'
        self.listdir.return_value = ['will-not-exist.txt']
        self.lstat.side_effect = OSError(errno.ENOENT, 'No such file or directory')
        logger = mock.MagicMock()

        koji.util._stripcwd(dev, self.dirname, logger)

        self.listdir.assert_called_once_with('.')
        self.lstat.assert_called_once_with('will-not-exist.txt')
        self.unlink.assert_not_called()
        self.isdir.assert_not_called()

    @mock.patch('koji.util._rmtree_nofork')
    @mock.patch('os.fork')
    @mock.patch('os._exit')
    def test_rmtree_child(self, _exit, fork, rmtree_nofork):
        fork.return_value = 0
        path = "/SOME_PATH"
        logger = "LOGGER"

        class Exited(Exception):
            pass

        _exit.side_effect = Exited
        # using exception to simulate os._exit in the test
        with self.assertRaises(Exited):
            koji.util.rmtree(path, logger)
        fork.assert_called_once()
        rmtree_nofork.assert_called_once()
        self.assertEqual(rmtree_nofork.mock_calls[0].args[0], path)
        _exit.assert_called_once()

    @mock.patch('koji.util._rmtree_nofork')
    @mock.patch('os.fork')
    @mock.patch('os.waitpid')
    @mock.patch('os._exit')
    def test_rmtree_child_fails(self, _exit, waitpid, fork, rmtree_nofork):
        fork.return_value = 0
        path = "/SOME_PATH"
        logger = "LOGGER"

        class Failed(Exception):
            pass

        rmtree_nofork.side_effect = Failed()
        # the exception should be re-raised
        with self.assertRaises(Failed):
            koji.util.rmtree(path, logger)
        fork.assert_called_once()
        rmtree_nofork.assert_called_once()
        self.assertEqual(rmtree_nofork.mock_calls[0].args[0], path)
        _exit.assert_called_once()
        waitpid.assert_not_called

    @mock.patch('koji.util._rmtree_nofork')
    @mock.patch('os.fork')
    @mock.patch('os.waitpid')
    @mock.patch('os._exit')
    def test_rmtree_parent(self, _exit, waitpid, fork, rmtree_nofork):
        pid = 137
        fork.return_value = pid
        waitpid.return_value = pid, 0
        path = "/SOME_PATH"
        logger = "LOGGER"
        koji.util.rmtree(path, logger)
        fork.assert_called_once()
        rmtree_nofork.assert_not_called()
        _exit.assert_not_called()

    @mock.patch('koji.util.SimpleProxyLogger.send')
    @mock.patch('koji.util._rmtree_nofork')
    @mock.patch('os.fork')
    @mock.patch('os.unlink')
    @mock.patch('os.waitpid')
    @mock.patch('os._exit')
    def test_rmtree_parent_logfail(self, _exit, waitpid, unlink, fork, rmtree_nofork, logsend):
        pid = 137
        fork.return_value = pid
        waitpid.return_value = pid, 0
        path = "/SOME_PATH"
        logger = mock.MagicMock()

        class Failed(Exception):
            pass

        logsend.side_effect = Failed('hello')
        koji.util.rmtree(path, logger)
        logsend.assert_called_once()
        logger.error.assert_called_once()
        if not logger.error.mock_calls[0].args[0].startswith('Failed to get rmtree logs'):
            raise Exception('Wrong log message')
        fork.assert_called_once()
        rmtree_nofork.assert_not_called()
        _exit.assert_not_called()


class TestAssertCWD(unittest.TestCase):

    def setUp(self):
        self.getcwd = mock.patch('os.getcwd').start()

    def tearDown(self):
        mock.patch.stopall()

    def test_assert_cwd(self):
        self.getcwd.return_value = '/mydir'
        koji.util._assert_cwd('/mydir')
        with self.assertRaises(koji.GenericError):
            koji.util._assert_cwd('/wrongdir')

    @mock.patch('os.getcwd')
    def test_assert_cwd_call_fails(self, getcwd):
        exc = Exception('hello')
        getcwd.side_effect = exc
        with self.assertRaises(Exception) as e:
            koji.util._assert_cwd('/test')
            # should re-raise same exception
            self.assertEqual(e, exc)

        exc = OSError()
        exc.errno = errno.ENOENT
        getcwd.side_effect = exc
        # should ignore
        koji.util._assert_cwd('/test')


class TestRmtree2(unittest.TestCase):

    def setUp(self):
        self.tempdir = tempfile.mkdtemp()
        self.savecwd = os.getcwd()
        # rmtree calls chdir, so save and restore cwd in case of a bug

    def tearDown(self):
        shutil.rmtree(self.tempdir)
        os.chdir(self.savecwd)

    def test_rmtree_missing(self):
        # should not error if already removed
        dirname = '%s/NOSUCHDIR' % self.tempdir
        koji.util.rmtree(dirname)

        dirname = '%s/NOSUCHDIR/NOSUCHDIR' % self.tempdir
        koji.util.rmtree(dirname)

    def test_rmtree_notadir(self):
        # should not error if already removed
        fname = '%s/hello.txt' % self.tempdir
        with open(fname, 'wt') as fo:
            fo.write('hello\n')
        with self.assertRaises(koji.GenericError):
            koji.util.rmtree(fname)

        if not os.path.exists(fname):
            raise Exception('deleted: %s', fname)

    def test_rmtree_parallel_chdir_down_failure(self):
        dirname = '%s/some-dir/' % self.tempdir
        os.makedirs('%s/a/b/c/d/e/f/g/h/i/j/k' % dirname)
        mock_data = {'n': 0, 'removed': False}
        os_chdir = os.chdir

        def my_chdir(*a, **kw):
            # after 4 calls, remove the tree
            # this should happen during the descent
            # rmtree should gracefully handle this
            mock_data['n'] += 1
            if mock_data['n'] == 4:
                shutil.rmtree(dirname)
                mock_data['removed'] = True
            return os_chdir(*a, **kw)
        with mock.patch('os.chdir', new=my_chdir):
            koji.util._rmtree_nofork(dirname)
        if not mock_data['removed']:
            raise Exception('mocked call not working')
        if os.path.exists(dirname):
            raise Exception('test directory not removed')

    def test_rmtree_relative(self):
        dirname = 'some-dir-95628'  # relative
        os.makedirs('%s/%s/a/b/c/d/e/f/g/h/i/j/k' % (self.tempdir, dirname))

        oldcwd = os.getcwd()
        os.chdir(self.tempdir)
        try:
            koji.util._rmtree_nofork(dirname)
        finally:
            os.chdir(oldcwd)

        if not os.path.exists(dirname):
            raise Exception('test directory not removed')

    def test_rmtree_dev_change(self):
        dirname = '%s/some-dir/' % self.tempdir
        os.makedirs('%s/a/b/c/d/e/f/g/h/i/j/k' % dirname)
        doomed = [
            '%s/a/b/c/d/e/f/DOOMED' % dirname,
            '%s/a/b/c/d/e/DOOMED' % dirname,
            '%s/a/b/DOOMED' % dirname,
        ]
        safe = [
            '%s/a/b/c/d/e/f/g/SAFE' % dirname,
            '%s/a/b/c/d/e/f/g/h/SAFE' % dirname,
            '%s/a/b/c/d/e/f/g/h/i/SAFE' % dirname,
            '%s/a/b/c/d/e/f/g/h/i/j/SAFE' % dirname,
        ]
        for fn in doomed + safe:
            with open(fn, 'wt') as fo:
                fo.write('hello')

        os_lstat = os.lstat
        pingfile = self.tempdir + '/ping'

        def my_lstat(path, **kw):
            # report different dev mid-tree
            ret = os_lstat(path, **kw)
            if path.endswith('g'):
                # path might be absolute or relative
                with open(pingfile, 'wt') as fo:
                    fo.write('ping')
                ret = mock.MagicMock(wraps=ret)
                ret.st_dev = "NEWDEV"
            return ret

        with mock.patch('os.lstat', new=my_lstat):
            with self.assertRaises(koji.GenericError):
                koji.util.rmtree(dirname)
        if not os.path.exists(pingfile):
            raise Exception('mocked call not working')
        for fn in doomed:
            if os.path.exists(fn):
                raise Exception('not deleted: %s', fn)
        for fn in safe:
            if not os.path.exists(fn):
                raise Exception('deleted: %s', fn)
        if not os.path.exists(dirname):
            raise Exception('deleted: %s', dirname)

    def test_rmtree_complex(self):
        dirname = '%s/some-dir/' % self.tempdir
        # For this test, we make a complex tree to remove
        for i in range(8):
            for j in range(8):
                for k in range(8):
                    os.makedirs('%s/a/%s/c/d/%s/e/f/%s/g/h' % (dirname, i, j, k))

        koji.util.rmtree(dirname)
        if os.path.exists(dirname):
            raise Exception('test directory not removed')

    def test_rmtree_parallel_chdir_down_complex(self):
        dirname = '%s/some-dir/' % self.tempdir
        # For this test, we make a complex tree to remove
        # We remove a subtree partway through to verify that the error is
        # ignored without breaking the remaining traversal
        for i in range(8):
            for j in range(8):
                for k in range(8):
                    os.makedirs('%s/a/%s/c/d/%s/e/f/%s/g/h' % (dirname, i, j, k))
        mock_data = {'n': 0, 'removed': False}
        os_chdir = os.chdir

        def my_chdir(path):
            mock_data['n'] += 1
            if path == 'f':
                # when we hit the first f, remove the subtree
                shutil.rmtree(os.path.abspath(path))
                mock_data['removed'] = True
            return os_chdir(path)
        with mock.patch('os.chdir', new=my_chdir):
            koji.util._rmtree_nofork(dirname)
        if not mock_data['removed']:
            raise Exception('mocked call not working')
        if os.path.exists(dirname):
            raise Exception('test directory not removed')

    def test_rmtree_parallel_chdir_up_failure(self):
        dirname = '%s/some-dir/' % self.tempdir
        os.makedirs('%s/a/b/c/d/e/f/g/h/i/j/k' % dirname)
        mock_data = {'n': 0, 'removed': False}
        os_chdir = os.chdir

        def my_chdir(path):
            # remove the tree when we start ascending
            # rmtree should gracefully handle this
            mock_data['n'] += 1
            if path == '..' and not mock_data['removed']:
                shutil.rmtree(dirname)
                mock_data['removed'] = True
                # os.chdir('..') might not error on normal filesystems
                # we'll raise ESTALE to simulate the nfs case
                e = OSError()
                e.errno = errno.ESTALE
                raise e
            return os_chdir(path)
        with mock.patch('os.chdir', new=my_chdir):
            koji.util._rmtree_nofork(dirname)
        if not mock_data['removed']:
            raise Exception('mocked call not working')
        if os.path.exists(dirname):
            raise Exception('test directory not removed')

    def test_rmtree_parallel_listdir_fails(self):
        dirname = '%s/some-dir/' % self.tempdir
        os.makedirs('%s/a/b/c/d/e/f/g/h/i/j/k' % dirname)
        mock_data = {'n': 0, 'removed': False}
        os_listdir = os.listdir

        def my_listdir(*a, **kw):
            # after 4 calls, remove the tree
            # rmtree should gracefully handle this
            mock_data['n'] += 1
            if mock_data['n'] == 4:
                shutil.rmtree(dirname)
                mock_data['removed'] = True
                # os.listdir('.') might not error on normal filesystems
                # we'll raise ESTALE to simulate the nfs case
                e = OSError()
                e.errno = errno.ESTALE
                raise e
            return os_listdir(*a, **kw)
        with mock.patch('os.listdir', new=my_listdir):
            koji.util._rmtree_nofork(dirname)
        if not mock_data['removed']:
            raise Exception('mocked call not working')
        if os.path.exists(dirname):
            raise Exception('test directory not removed')

    def test_rmtree_parallel_new_file(self):
        """Testing case where a separate process adds new files during after
        # we have stripped a directory.
        # This should cause rmtree to fail.
        """
        dirname = '%s/some-dir/' % self.tempdir
        os.makedirs('%s/a/b/c/d/e/f/g/h/i/j/k' % dirname)
        os_listdir = os.listdir
        mock_data = {}

        def my_listdir(path):
            ret = os_listdir(path)
            if 'b' in ret:
                mock_data['ping'] = 1
                with open('extra_file', 'w') as fo:
                    fo.write('hello world\n')
            return ret  # does not contain extra_file
        with mock.patch('os.listdir', new=my_listdir):
            with self.assertRaises(OSError):
                koji.util._rmtree_nofork(dirname)
        if not mock_data.get('ping'):
            raise Exception('mocked call not working')

    def test_rmtree_threading(self):
        # multiple complex trees to be deleted in parallel threads
        dirs = []
        for n in range(10):
            dirname = '%s/some-dir-%s/' % (self.tempdir, n)
            dirs.append(dirname)
            for i in range(8):
                for j in range(8):
                    for k in range(8):
                        os.makedirs('%s/a/%s/c/d/%s/e/f/%s/g/h' % (dirname, i, j, k))

        sync = threading.Event()
        def do_rmtree(dirname):
            sync.wait()
            koji.util.rmtree(dirname)

        threads = []
        for d in dirs:
            thread = threading.Thread(target=do_rmtree, args=(d,))
            thread.start()
            threads.append(thread)
        sync.set()
        for thread in threads:
            thread.join()

        for dirname in dirs:
            if os.path.exists(dirname):
                raise Exception('test directory not removed')

    def test_rmtree_race_thread(self):
        # parallel threads deleting the same complex tree
        dirname = '%s/some-dir/' % (self.tempdir)
        for i in range(8):
            for j in range(8):
                for k in range(8):
                    os.makedirs('%s/a/%s/c/d/%s/e/f/%s/g/h' % (dirname, i, j, k))

        sync = threading.Event()
        def do_rmtree(dirname):
            sync.wait()
            koji.util.rmtree(dirname)

        threads = []
        for n in range(3):
            thread = threading.Thread(target=do_rmtree, args=(dirname,))
            thread.start()
            threads.append(thread)
        sync.set()
        for thread in threads:
            thread.join()

        if os.path.exists(dirname):
            raise Exception('test directory not removed')

    def test_rmtree_race_process(self):
        # parallel threads deleting the same complex tree
        dirname = '%s/some-dir/' % (self.tempdir)
        for i in range(8):
            for j in range(8):
                for k in range(8):
                    os.makedirs('%s/a/%s/c/d/%s/e/f/%s/g/h' % (dirname, i, j, k))

        sync = multiprocessing.Event()
        def do_rmtree(dirname):
            sync.wait()
            koji.util.rmtree(dirname)

        procs = []
        for n in range(3):
            proc = multiprocessing.Process(target=do_rmtree, args=(dirname,))
            proc.start()
            procs.append(proc)
        sync.set()
        for proc in procs:
            proc.join()

        if os.path.exists(dirname):
            raise Exception('test directory not removed')

    def test_rmtree_deep_subdir(self):
        # create a deep subdir
        dirname = '%s/some-dir/' % (self.tempdir)
        MAX_PATH = os.pathconf(dirname, 'PC_PATH_MAX')
        subname = "deep_path_directory_%05i_______________________________________________________"
        limit = MAX_PATH // (len(subname % 123) + 1)
        # two segments each 2/3 of the limit, so each below, but together above
        seglen = limit * 2 // 3
        segment = '/'.join([subname % n for n in range(seglen)])
        path1 = os.path.join(dirname, segment)
        os.makedirs(path1)
        cwd = os.getcwd()
        os.chdir(path1)
        os.makedirs(segment)
        os.chdir(cwd)

        koji.util.rmtree(dirname)

        if os.path.exists(dirname):
            raise Exception('test directory not removed')


class TestProxyLogger(unittest.TestCase):

    def setUp(self):
        self.tempdir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tempdir)

    def test_proxy_logger(self):
        logfile = self.tempdir + '/log.jsonl'
        with koji.util.SimpleProxyLogger(logfile) as proxy:
            proxy.info('hello world')
            proxy.warning('hmm -- %s', ['data'])
            proxy.error('We have a problem -- %r', {'a': 1})
            proxy.debug('yadayadayada')

        logger = mock.MagicMock()
        koji.util.SimpleProxyLogger.send(logfile, logger)
        logger.log.assert_has_calls([
            call(20, 'hello world'),
            call(30, 'hmm -- %s', ['data']),
            call(40, 'We have a problem -- %r', {'a': 1}),
            call(10, 'yadayadayada')])

    def test_proxy_logger_bad_data(self):
        logfile = self.tempdir + '/log.jsonl'
        with koji.util.SimpleProxyLogger(logfile) as proxy:
            # non-json-encodable
            proxy.info('bad - %s', Exception())
        logger = mock.MagicMock()
        koji.util.SimpleProxyLogger.send(logfile, logger)
        logger.log.assert_called_once()
        self.assertEqual(logger.log.mock_calls[0].args[0], logging.ERROR)
        if not logger.log.mock_calls[0].args[1].startswith('Unable to log'):
            raise Exception('Wrong error message')

    def test_proxy_logger_bad_line(self):
        logfile = self.tempdir + '/log.jsonl'
        with open(logfile, 'wt') as fo:
            fo.write('INVALID_JSON()')
        logger = mock.MagicMock()
        koji.util.SimpleProxyLogger.send(logfile, logger)
        logger.log.assert_called_once()
        self.assertEqual(logger.log.mock_calls[0].args[0], logging.ERROR)
        if not logger.log.mock_calls[0].args[1].startswith('Bad log data: '):
            raise Exception('Wrong error message')

    def test_proxy_logger_repr_fail(self):
        class BadValue:
            def __repr__(self):
                raise ValueError('no')
        strfail = BadValue()

        logfile = self.tempdir + '/log.jsonl'
        with koji.util.SimpleProxyLogger(logfile) as proxy:
            proxy.info('bad - %s', strfail)
        logger = mock.MagicMock()
        koji.util.SimpleProxyLogger.send(logfile, logger)
        logger.log.assert_called_once_with(logging.ERROR, 'Invalid log data')


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


class TestFormatShellCmd(unittest.TestCase):
    def test_formats(self):
        cases = (
            ([], ''),
            (['random cmd'], 'random cmd'),
            (['aa', 'bb'], 'aa bb'),
            (['long', 'command', 'with', 'many', 'simple', 'options',
              'like', '--option', 'x', '--another-option=x', 'and',
              'many', 'more', 'others'],
             'long command with many simple options \\\n'
             'like --option x --another-option=x and \\\n'
             'many more others'),
            (['one long line which exceeds the text_width by some amount'],
             'one long line which exceeds the text_width by some amount'),
            (['one long line which exceeds the text_width by some amount',
              'second long line which exceeds the text_width by some amount'],
             'one long line which exceeds the text_width by some amount \\\n'
             'second long line which exceeds the text_width by some amount'),
        )
        for inp, out in cases:
            self.assertEqual(koji.util.format_shell_cmd(inp, text_width=40), out)

class TestExtractBuildTask(unittest.TestCase):
    def test_valid_binfos(self):
        binfos = [
            {'id': 1, 'task_id': 123},
            {'id': 1, 'extra': {'container_koji_task_id': 123}},
        ]
        for binfo in binfos:
            res = koji.util.extract_build_task(binfo)
            self.assertEqual(res, 123)


if __name__ == '__main__':
    unittest.main()
