from __future__ import absolute_import
import mock
import rpm
import tempfile
try:
    import unittest2 as unittest
except ImportError:
    import unittest
import koji
from .loadkojid import kojid
from six.moves import range


class FakeHeader(dict):

    def __init__(self, **kwargs):
        for key in kwargs:
            kname = "RPMTAG_%s" % key.upper()
            hkey = getattr(rpm, kname)
            self.__setitem__(hkey, kwargs[key])


class TestChooseTaskarch(unittest.TestCase):

    def setUp(self):
        # set up task handler
        task_id = 99
        method = 'build'
        params = []
        self.session = mock.MagicMock()
        self.options = mock.MagicMock()
        self.options.literal_task_arches = ''
        workdir = tempfile.mkdtemp()
        self.handler = kojid.BuildTask(task_id, method, params, self.session,
                self.options, workdir)

        # mock some more things
        self.handler.event_id = 42
        self.readSRPMHeader = mock.MagicMock()
        self.handler.readSRPMHeader = self.readSRPMHeader
        self.getBuildConfig = mock.MagicMock()
        self.session.getBuildConfig = self.getBuildConfig
        self.getBuildConfig.return_value = {'arches': 'armv7hl i686 x86_64 ppc64'}

    def test_binary_arches(self):
        for arch in ['i386', 'i686', 'x86_64', 'ppc', 'ppc64le', 's390',
                    's390x']:
            result = self.handler.choose_taskarch(arch, 'srpm', 'build_tag')
            self.assertEqual(result, koji.canonArch(arch))

    def test_basic_noarch(self):
        self.readSRPMHeader.return_value = FakeHeader(
                buildarchs=['noarch'], exclusivearch=[], excludearch=[])
        result = self.handler.choose_taskarch('noarch', 'srpm', 'build_tag')
        self.assertEqual(result, 'noarch')

    def test_excluded_arch(self):
        tag_arches = [koji.canonArch(a) for a in self.getBuildConfig()['arches'].split()]
        # random choice involved, so we repeat this a few times
        for i in range(20):
            self.readSRPMHeader.return_value = FakeHeader(
                    buildarchs=['noarch'], exclusivearch=[], excludearch=['ppc64'])
            result = self.handler.choose_taskarch('noarch', 'srpm', 'build_tag')
            self.assertNotEqual(result, 'noarch')
            self.assertNotEqual(result, 'ppc64')
            self.assertIn(result, tag_arches)

    def test_exclusive_arch(self):
        tag_arches = [koji.canonArch(a) for a in self.getBuildConfig()['arches'].split()]
        # random choice involved, so we repeat this a few times
        for i in range(20):
            self.readSRPMHeader.return_value = FakeHeader(
                    buildarchs=['noarch'], exclusivearch=['noarch', 'armv7hl'], excludearch=[])
            result = self.handler.choose_taskarch('noarch', 'srpm', 'build_tag')
            self.assertNotEqual(result, 'noarch')
            self.assertEqual(result, koji.canonArch('armv7hl'))
            self.assertIn(result, tag_arches)

    def test_excluded_irrelevant(self):
        tag_arches = [koji.canonArch(a) for a in self.getBuildConfig()['arches'].split()]
        self.readSRPMHeader.return_value = FakeHeader(
                buildarchs=['noarch'], exclusivearch=[], excludearch=['nosucharch'])
        result = self.handler.choose_taskarch('noarch', 'srpm', 'build_tag')
        self.assertEqual(result, 'noarch')

    def test_literal_arch(self):
        self.options.literal_task_arches = 'ARCH'
        tag_arches = [koji.canonArch(a) for a in self.getBuildConfig()['arches'].split()]
        result = self.handler.choose_taskarch('ARCH', 'srpm', 'build_tag')
        self.assertEqual(result, 'ARCH')

    def test_all_excluded(self):
        tag_arches = [koji.canonArch(a) for a in self.getBuildConfig()['arches'].split()]
        # random choice involved, so we repeat this a few times
        for i in range(20):
            self.readSRPMHeader.return_value = FakeHeader(
                    buildarchs=['noarch'], exclusivearch=[], excludearch=tag_arches)
            with self.assertRaises(koji.BuildError):
                result = self.handler.choose_taskarch('noarch', 'srpm', 'build_tag')

    def test_too_exclusive(self):
        tag_arches = [koji.canonArch(a) for a in self.getBuildConfig()['arches'].split()]
        # random choice involved, so we repeat this a few times
        for i in range(20):
            self.readSRPMHeader.return_value = FakeHeader(
                    buildarchs=['noarch'], exclusivearch=['missing_arch'], excludearch=[])
            with self.assertRaises(koji.BuildError):
                result = self.handler.choose_taskarch('noarch', 'srpm', 'build_tag')
