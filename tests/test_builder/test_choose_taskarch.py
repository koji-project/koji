import unittest
import os
import sys
import mock
import rpm
import tempfile

from loadkojid import kojid


class FakeHeader(dict):

    def __init__(self, **kwargs):
        for key in kwargs:
            kname = "RPMTAG_%s" % key.upper()
            hkey = getattr(rpm, kname)
            self.__setitem__(hkey, kwargs[key])


class TestChooseTaskarch(unittest.TestCase):

    def setUp(self):
        task_id = 99
        method = 'build'
        params = []
        self.session = mock.MagicMock()
        self.options = mock.MagicMock()
        workdir = tempfile.mkdtemp()
        self.handler = kojid.BuildTask(task_id, method, params, self.session,
                self.options, workdir)
        self.readSRPMHeader = mock.MagicMock()
        self.handler.readSRPMHeader = self.readSRPMHeader

    def test_noarch(self):
        self.readSRPMHeader.return_value = FakeHeader(buildarchs=['noarch'],
                exclusivearch=[], excludearch=[])
        self.handler.choose_taskarch('noarch', 'srpm', 'build_tag')



 
