from __future__ import absolute_import
import mock
import tempfile
try:
    import unittest2 as unittest
except ImportError:
    import unittest
from .loadkojid import kojid


class TestChooseTaskarch(unittest.TestCase):
    version = '1'
    release = 'f27'

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

    def test_beta_atomic(self):
        """Check that volume ID Beta-Atomic-Fedora
        is shorten to B-AH-Fedora."""
        name = 'Beta-Atomic-Fedora'
        expected_vol_id = 'B-AH-Fedora-' + self.version + '-' + self.release
        result_vol_id = self.handler._shortenVolID(
            name, self.version, self.release)
        self.assertEqual(expected_vol_id, result_vol_id)

    def test_beta_beta(self):
        """Check that volume ID Beta-Fedora-Beta
        is shorten to B-Fedora-B."""
        name = 'Beta-Fedora-Beta'
        expected_vol_id = 'B-Fedora-B-' + self.version + '-' + self.release
        result_vol_id = self.handler._shortenVolID(
            name, self.version, self.release)
        self.assertEqual(expected_vol_id, result_vol_id)

    def test_rawhide_astronomy_cinnamon(self):
        """Check that volume ID Rawhide-Fedora-Astronomy_KDE-Cinnamon
        is shorten to rawh-Fedora-AstK-Cinn."""
        name = 'Rawhide-Fedora-Astronomy_KDE-Cinnamon'
        expected_vol_id = ('rawh-Fedora-AstK-Cinn-' + self.version + '-' +
                           self.release)
        result_vol_id = self.handler._shortenVolID(
            name, self.version, self.release)
        self.assertEqual(expected_vol_id, result_vol_id)

    def test_cloud_designsuite_electroniclab(self):
        """Check that volume ID Cloud-Design_suite-Fedora-Electronic_Lab
        is shorten to C-Dsgn-Fedora-Elec."""
        name = 'Cloud-Design_suite-Fedora-Electronic_Lab'
        expected_vol_id = ('C-Dsgn-Fedora-Elec-' + self.version + '-' +
                           self.release)
        result_vol_id = self.handler._shortenVolID(
            name, self.version, self.release)
        self.assertEqual(expected_vol_id, result_vol_id)

    def test_everything_games_images(self):
        """Check that volume ID Everything-Games-Images-Fedora
        is shorten to E-Game-img-Fedora."""
        name = 'Everything-Games-Images-Fedora'
        expected_vol_id = ('E-Game-img-Fedora-' + self.version + '-' +
                           self.release)
        result_vol_id = self.handler._shortenVolID(
            name, self.version, self.release)
        self.assertEqual(expected_vol_id, result_vol_id)

    def test_jamkde_matecompiz_pythonclassroom(self):
        """Check that volume ID Fedora-Jam_KDE-MATE_Compiz-Python-Classroom
        is shorten to Fedora-Jam-MATE-Clss."""
        name = 'Fedora-Jam_KDE-MATE_Compiz-Python-Classroom'
        expected_vol_id = ('Fedora-Jam-MATE-Clss-' + self.version + '-' +
                           self.release)
        result_vol_id = self.handler._shortenVolID(
            name, self.version, self.release)
        self.assertEqual(expected_vol_id, result_vol_id)

    def test_matecompiz_pythonclassroom_pythonclassroom(self):
        """Check that volume ID MATE_Compiz-Python_Classroom-Python-Classroom
        is shorten to MATE-Clss-Clss."""
        name = 'MATE_Compiz-Python_Classroom-Python-Classroom'
        expected_vol_id = 'MATE-Clss-Clss-' + self.version + '-' + self.release
        result_vol_id = self.handler._shortenVolID(
            name, self.version, self.release)
        self.assertEqual(expected_vol_id, result_vol_id)

    def test_robotics_scientifickde_security(self):
        """Check that volume ID Robotics-Scientific_KDE-Fedora-Security
        is shorten to Robo-SciK-Fedora-Sec."""
        name = 'Robotics-Scientific_KDE-Fedora-Security'
        expected_vol_id = ('Robo-SciK-Fedora-Sec-' + self.version + '-' +
                           self.release)
        result_vol_id = self.handler._shortenVolID(
            name, self.version, self.release)
        self.assertEqual(expected_vol_id, result_vol_id)

    def test_robotics_workstation(self):
        """Check that volume ID Robotics-Workstation-Fedora
        is shorten to Robo-WS-Fedora."""
        name = 'Robotics-Workstation-Fedora'
        expected_vol_id = 'Robo-WS-Fedora-' + self.version + '-' + self.release
        result_vol_id = self.handler._shortenVolID(
            name, self.version, self.release)
        self.assertEqual(expected_vol_id, result_vol_id)

    def test_everything_server(self):
        """Check that volume ID Server-Fedora-Everything-Server
        is shorten to S-Fedora-E-S."""
        name = 'Server-Fedora-Everything-Server'
        expected_vol_id = 'S-Fedora-E-S-' + self.version + '-' + self.release
        result_vol_id = self.handler._shortenVolID(
            name, self.version, self.release)
        self.assertEqual(expected_vol_id, result_vol_id)

    def test_images_workstationostree(self):
        """Check that volume ID Fedora-WorkstationOstree-Images
        is shorten to Fedora-WS-img."""
        name = 'Fedora-WorkstationOstree-Images'
        expected_vol_id = 'Fedora-WS-img-' + self.version + '-' + self.release
        result_vol_id = self.handler._shortenVolID(
            name, self.version, self.release)
        self.assertEqual(expected_vol_id, result_vol_id)

    def test_workstation_cloud_beta_cloud_games_cloud_matecompiz_cloud(self):
        """Check that volume ID Workstation-Cloud-Beta-Cloud-Games-Cloud-MATE_Compiz-Cloud
        is shorten to WS-C-B-C-Game-C-MATE-C."""
        name = 'Workstation-Cloud-Beta-Cloud-Games-Cloud-MATE_Compiz-Cloud'
        expected_vol_id = ('WS-C-B-C-Game-C-MATE-C-' + self.version + '-' +
                           self.release)
        result_vol_id = self.handler._shortenVolID(
            name, self.version, self.release)
        self.assertEqual(expected_vol_id, result_vol_id)

    def test_astronomykde_pythonclassroom_robotics_robotics_robotics_games(self):
        """Check that volume ID Astronomy_KDE-Python-Classroom-Robotics-Robotics-Games
        is shorten to AstK-Clss-Robo-Robo-Game."""
        name = 'Astronomy_KDE-Python-Classroom-Robotics-Robotics-Games'
        expected_vol_id = ('AstK-Clss-Robo-Robo-Game-' + self.version + '-' +
                           self.release)
        result_vol_id = self.handler._shortenVolID(
            name, self.version, self.release)
        self.assertEqual(expected_vol_id, result_vol_id)
