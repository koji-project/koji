from __future__ import absolute_import
import mock
import tempfile
try:
    import unittest2 as unittest
except ImportError:
    import unittest
from .loadkojid import kojid
import logging

logger = logging.getLogger(__name__)


class TestVolumeID(unittest.TestCase):
    version = '1'
    release = 'f27'

    test_cases = {
        't1': {
            'name': 'Beta-Atomic-Fedora',
            'expected-id': 'B-AH-Fedora-' + version + '-' + release
        },
        't2': {
            'name': 'Beta-Fedora-Beta',
            'expected-id': 'B-Fedora-B-' + version + '-' + release
        },
        't3': {
            'name': 'Rawhide-Fedora-Astronomy_KDE-Cinnamon',
            'expected-id': 'rawh-Fedora-AstK-Cinn-' + version + '-' + release
        },
        't4': {
            'name': 'Cloud-Design_suite-Fedora-Electronic_Lab',
            'expected-id': 'C-Dsgn-Fedora-Elec-' + version + '-' + release
        },
        't5': {
            'name': 'Everything-Games-Images-Fedora',
            'expected-id': 'E-Game-img-Fedora-' + version + '-' + release
        },
        't6': {
            'name': 'Fedora-Jam_KDE-MATE_Compiz-Python-Classroom',
            'expected-id': 'Fedora-Jam-MATE-Clss-' + version + '-' + release
        },
        't7': {
            'name': 'MATE_Compiz-Python_Classroom-Python-Classroom',
            'expected-id': 'MATE-Clss-Clss-' + version + '-' + release
        },
        't8': {
            'name': 'Robotics-Scientific_KDE-Fedora-Security',
            'expected-id': 'Robo-SciK-Fedora-Sec-' + version + '-' + release
        },
        't9': {
            'name': 'Robotics-Workstation-Fedora',
            'expected-id': 'Robo-WS-Fedora-' + version + '-' + release
        },
        't10': {
            'name': 'Server-Fedora-Everything-Server',
            'expected-id': 'S-Fedora-E-S-' + version + '-' + release
        },
        't11': {
            'name': 'Fedora-WorkstationOstree-Images',
            'expected-id': 'Fedora-WS-img-' + version + '-' + release
        },
        't12': {
            'name': 'Workstation-Cloud-Beta-Cloud-Games-Cloud-MATE_Compiz-Cloud',
            'expected-id': 'WS-C-B-C-Game-C-MATE-C-' + version + '-' + release
        },
        't13': {
            'name': 'Astronomy_KDE-Python-Classroom-Robotics-Robotics-Games',
            'expected-id': 'AstK-Clss-Robo-Robo-Game-' + version + '-' + release
        }
    }

    def setUp(self):
        # set up task handler
        task_id = 99
        method = 'createLiveCD'
        params = []
        self.session = mock.MagicMock()
        self.options = mock.MagicMock()
        self.options.literal_task_arches = ''
        workdir = tempfile.mkdtemp()
        self.handler = kojid.LiveCDTask(task_id, method, params, self.session,
                                        self.options, workdir)

    def test_volume_id_substitutions(self):
        """Check that volume ID is shorten corect by shortenVolID method."""
        for test_name, values in self.test_cases.items():
            name = values['name']
            expected_vol_id = values['expected-id']
            result_vol_id = self.handler._shortenVolID(name, self.version, self.release)
            logger.info("name '%s' expected vol id %s.", name, expected_vol_id)
            self.assertEqual(expected_vol_id, result_vol_id,
                             'Expected shortened volume id %s is not same as result of shortenVolID %s.'
                             %(expected_vol_id, result_vol_id))
