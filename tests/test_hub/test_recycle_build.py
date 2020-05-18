import mock

import koji
import kojihub

QP = kojihub.QueryProcessor
UP = kojihub.UpdateProcessor

class TestRecycleBuild():
    # NOT a subclass of unittest.TestCase so that we can use generator
    # methods

    def setUp(self):
        self.QueryProcessor = mock.patch('kojihub.QueryProcessor').start()
        self.UpdateProcessor = mock.patch('kojihub.UpdateProcessor',
                                side_effect=self.getUpdate).start()
        self._dml = mock.patch('kojihub._dml').start()
        self.run_callbacks = mock.patch('koji.plugin.run_callbacks').start()
        self.rmtree = mock.patch('koji.util.rmtree').start()
        self.exists = mock.patch('os.path.exists').start()
        self.updates = []

    def tearDown(self):
        mock.patch.stopall()

    def getUpdate(self, *args, **kwargs):
        update = UP(*args, **kwargs)
        update.execute = mock.MagicMock()
        self.updates.append(update)
        return update

    # Basic old and new build infos
    old = {'id': 2,
           'state': 0,
           'task_id': None,
           'epoch': None,
           'name': 'GConf2',
           'nvr': 'GConf2-3.2.6-15.fc23',
           'package_id': 2,
           'package_name': 'GConf2',
           'release': '15.fc23',
           'version': '3.2.6',
           'source': None,
           'extra': None,
           'cg_id': None,
           'volume_id': 0,
           'volume_name': 'DEFAULT'}
    new = {'state': 0,
           'name': 'GConf2',
           'version': '3.2.6',
           'release': '15.fc23',
           'epoch': None,
           'nvr': 'GConf2-3.2.6-15.fc23',
           'completion_time': '2016-09-16',
           'start_time': '2016-09-16',
           'owner': 2,
           'source': None,
           'extra': None,
           'cg_id': None,
           'volume_id': 0}

    def test_recycle_building(self):
        new = self.new.copy()
        old = self.old.copy()
        old['state'] = new['state'] = koji.BUILD_STATES['BUILDING']
        old['task_id'] = new['task_id'] = 137
        kojihub.recycle_build(old, new)
        self.UpdateProcessor.assert_not_called()
        self.QueryProcessor.assert_not_called()
        self._dml.assert_not_called()
        self.run_callbacks.assert_not_called()

    def test_recycle_building_bad(self):
        new = self.new.copy()
        old = self.old.copy()
        old['state'] = new['state'] = koji.BUILD_STATES['BUILDING']
        old['task_id'] = 137
        new['task_id'] = 200
        self.run_fail(old, new)
        self.QueryProcessor.assert_not_called()

    def test_recycle_states_good(self):
        for state in 'FAILED', 'CANCELED':
            yield self.check_recycle_states_good, koji.BUILD_STATES[state]

    def check_recycle_states_good(self, state):
        new = self.new.copy()
        old = self.old.copy()
        old['state'] = state
        new['state'] = koji.BUILD_STATES['BUILDING']
        old['task_id'] = 99
        new['task_id'] = 137
        query = self.QueryProcessor.return_value
        # for all checks
        query.execute.return_value = []
        # for getBuild
        query.executeOne.return_value = old
        self.run_pass(old, new)

    def run_pass(self, old, new):
        kojihub.recycle_build(old, new)
        self.UpdateProcessor.assert_called_once()
        update = self.updates[0]
        assert update.table == 'build'
        for key in ['state', 'task_id', 'owner', 'start_time',
                    'completion_time', 'epoch']:
            assert update.data[key] == new[key]
        assert update.rawdata == {'create_event': 'get_event()'}
        assert update.clauses == ['id=%(id)s']
        assert update.values['id'] == old['id']

    def run_fail(self, old, new):
        try:
            kojihub.recycle_build(old, new)
        except koji.GenericError:
            pass
        else:
            raise Exception("expected koji.GenericError")
        self.UpdateProcessor.assert_not_called()
        self._dml.assert_not_called()
        self.run_callbacks.assert_not_called()

    def test_recycle_states_bad(self):
        for state in 'BUILDING', 'COMPLETE', 'DELETED':
            yield self.check_recycle_states_bad, koji.BUILD_STATES[state]

    def check_recycle_states_bad(self, state):
        new = self.new.copy()
        old = self.old.copy()
        old['state'] = state
        new['state'] = koji.BUILD_STATES['BUILDING']
        old['task_id'] = 99
        new['task_id'] = 137
        self.run_fail(old, new)
        self.QueryProcessor.assert_not_called()

    def test_recycle_query_bad(self):
        vlists = [
            [[], [], True],
            [True, [], []],
            [[], True, []],
            ]
        for values in vlists:
            yield self.check_recycle_query_bad, values

    def check_recycle_query_bad(self, values):
        new = self.new.copy()
        old = self.old.copy()
        old['state'] = koji.BUILD_STATES['FAILED']
        new['state'] = koji.BUILD_STATES['BUILDING']
        old['task_id'] = 99
        new['task_id'] = 137
        query = self.QueryProcessor.return_value
        query.execute.side_effect = values
        self.run_fail(old, new)

