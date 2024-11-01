import unittest
import mock

import scmpolicy
import koji


BRANCHOUT1 = '''\
  origin/HEAD -> origin/rawhide
  origin/el6
  origin/epel7
  origin/epel8
  origin/epel8-playground
  origin/epel9
  origin/f26
  origin/f27
  origin/f28
  origin/f29
  origin/f30
  origin/f31
  origin/f32
  origin/f33
  origin/f34
  origin/f35
  origin/f36
  origin/f37
  origin/f38
  origin/f39
  origin/f40
  origin/f41
  origin/private-user1-never
  origin/private-user2-gonna
  origin/private-user3-give
  origin/private-user4-you
  origin/private-user5-up
  origin/main
  origin/rawhide
'''.encode('utf-8')


class TestCheckTaskMethod(unittest.TestCase):

    def setUp(self):
        self.session = mock.MagicMock()

    def tearDown(self):
        mock.patch.stopall()

    def test_get_task_method_good(self):
        taskinfo = {'method': 'buildSRPMFromSCM'}
        # call it
        ret = scmpolicy.get_task_method(self.session, taskinfo)
        self.assertEqual(ret, 'buildSRPMFromSCM')

    def test_get_task_method_str(self):
        taskinfo = 'badinfo'
        # call it
        with self.assertRaises(koji.GenericError) as cm:
            scmpolicy.get_task_method(self.session, taskinfo)
        self.assertEqual(str(cm.exception), "Invalid taskinfo: badinfo")

    def test_get_task_method_int(self):
        taskinfo = 11233
        self.session.getTaskInfo.return_value = {'method': 'buildSRPMFromSCM'}
        # call it
        ret = scmpolicy.get_task_method(self.session, taskinfo)
        self.assertEqual(ret, 'buildSRPMFromSCM')

    def test_get_task_method_int_error(self):
        taskinfo = 11233
        self.session.getTaskInfo.side_effect = koji.GenericError('hub msg')
        # call it
        with self.assertRaises(koji.GenericError) as cm:
            scmpolicy.get_task_method(self.session, taskinfo)
        self.assertEqual(str(cm.exception), 'hub msg')


class TestGetBranches(unittest.TestCase):

    def setUp(self):
        self.Popen = mock.patch('subprocess.Popen').start()

    def tearDown(self):
        mock.patch.stopall()

    def test_get_branches_good(self):
        proc = self.Popen.return_value
        proc.wait.return_value = 0
        proc.communicate.return_value = (BRANCHOUT1, '')
        scmdir = 'SCMDIR'
        # call it
        ret = scmpolicy.get_branches(scmdir)
        # the code should ignore the first line (HEAD)
        o_lines = BRANCHOUT1.splitlines()
        self.assertEqual(len(ret), len(o_lines) - 1)
        for branch in ('main', 'rawhide', 'f41', 'el6'):
            # not an exhaustive list
            self.assertIn(branch, ret)
        for value in ('HEAD', '', '->'):
            self.assertNotIn(value, ret)

    def test_get_branches_bad(self):
        proc = self.Popen.return_value
        proc.wait.return_value = 1
        proc.communicate.return_value = ('', 'Error text')
        scmdir = 'SCMDIR'
        # call it
        with self.assertRaises(Exception):
            scmpolicy.get_branches(scmdir)


class TestAssertSCMPolicy(unittest.TestCase):

    def setUp(self):
        self.Popen = mock.patch('subprocess.Popen').start()
        self.proc = self.Popen.return_value
        self.proc.wait.return_value = 0
        self.proc.communicate.return_value = (BRANCHOUT1, '')
        self.session = mock.MagicMock()
        self.session.host = mock.MagicMock()
        self.session.host.assertPolicy = mock.MagicMock()
        self.kwargs = {
            'taskinfo': {
                'id': 1,
                'method': 'buildSRPMFromSCM',
                'owner': 5,
            },
            'session': self.session,
            'build_tag': 'rhel-8.0-candidate',
            'scminfo': {
                'scmtype': 'GIT',
                'host': 'pkgs.devel.redhat.com',
            },
            'srcdir': 'SRCDIR',
            'scratch': False,
        }

    def tearDown(self):
        mock.patch.stopall()

    def test_allowed(self):
        ret = scmpolicy.assert_scm_policy('postSCMCheckout', **self.kwargs)
        self.assertEqual(ret, None)

    def test_denied(self):
        self.session.host.assertPolicy.side_effect = koji.ActionNotAllowed
        with self.assertRaises(koji.ActionNotAllowed):
            scmpolicy.assert_scm_policy('postSCMCheckout', **self.kwargs)
