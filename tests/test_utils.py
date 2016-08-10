import mock
import unittest

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


    @mock.patch('urllib2.urlopen')
    @mock.patch('tempfile.TemporaryFile')
    @mock.patch('shutil.copyfileobj')
    @mock.patch('__builtin__.open')
    def test_openRemoteFile(self, m_open, m_copyfileobj, m_TemporaryFile,
                            m_urlopen):
        """Test openRemoteFile function"""

        mocks = [m_open, m_copyfileobj, m_TemporaryFile, m_urlopen]

        topurl = 'http://example.com/koji'
        path = 'relative/file/path'
        url = 'http://example.com/koji/relative/file/path'

        #using topurl, no tempfile
        fo = koji.openRemoteFile(path, topurl)
        m_urlopen.assert_called_once_with(url)
        m_urlopen.return_value.close.assert_called_once()
        m_TemporaryFile.assert_called_once_with(dir=None)
        m_copyfileobj.assert_called_once()
        m_open.assert_not_called()
        assert fo is m_TemporaryFile.return_value

        for m in mocks:
            m.reset_mock()

        #using topurl + tempfile
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

        #using topdir
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
