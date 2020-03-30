from __future__ import absolute_import
import six
import protonmsg
import tempfile
try:
    import unittest2 as unittest
except ImportError:
    import unittest

from mock import patch, MagicMock
from koji.context import context
from six.moves.configparser import ConfigParser, SafeConfigParser

class TestProtonMsg(unittest.TestCase):
    def setUp(self):
        self.conf = tempfile.NamedTemporaryFile()
        self.conf.write(six.b("""[broker]
urls = amqps://broker1.example.com:5671 amqps://broker2.example.com:5671
cert = /etc/koji-hub/plugins/client.pem
cacert = /etc/koji-hub/plugins/ca.pem
topic_prefix = koji
connect_timeout = 10
send_timeout = 60

[message]
extra_limit = 2048
"""))
        self.conf.flush()
        protonmsg.CONFIG_FILE = self.conf.name
        protonmsg.CONFIG = None
        protonmsg.LOG = MagicMock()

    def tearDown(self):
        if hasattr(context, 'protonmsg_msgs'):
            del context.protonmsg_msgs
        del self.conf

    def assertMsg(self, topic, body=None, **kws):
        self.assertTrue(hasattr(context, 'protonmsg_msgs'))
        self.assertEqual(len(context.protonmsg_msgs), 1)
        msg = context.protonmsg_msgs[0]
        self.assertEqual(msg[0], topic)
        for kw in kws:
            self.assertTrue(kw in msg[1])
            self.assertEqual(msg[1][kw], kws[kw])
        self.assertEqual(len(msg[1]), len(kws))
        if body:
            self.assertEqual(msg[2], body)

    def test_queue_msg(self):
        protonmsg.queue_msg('test.msg', {'testheader': 1}, 'test body')
        self.assertMsg('test.msg', body='"test body"', testheader=1)

    def test_queue_msg_not_serializable(self):
        # mostly just testing that encoder does not error on data that cannot
        # be json encoded
        protonmsg.queue_msg('koji@example.com', {'testheader': 1}, object())
        self.assertMsg('koji@example.com', body=None, testheader=1)

    def test_prep_package_list_change_add(self):
        protonmsg.prep_package_list_change('postPackageListChange',
                                           action='add', tag={'name': 'test-tag'},
                                           package={'name': 'test-pkg'},
                                           owner=1,
                                           block=False, extra_arches='i386 x86_64',
                                           force=False, update=False,
                                           user={'name': 'username'})
        self.assertMsg('package.add', type='PackageListChange', tag='test-tag',
                       package='test-pkg', action='add', user='username')

    def test_prep_package_list_change_update(self):
        protonmsg.prep_package_list_change('postPackageListChange',
                                           action='update', tag={'name': 'test-tag'},
                                           package={'name': 'test-pkg'},
                                           owner=1,
                                           block=False, extra_arches='i386 x86_64',
                                           force=False, update=False,
                                           user={'name': 'username'})
        self.assertMsg('package.update', type='PackageListChange', tag='test-tag',
                       package='test-pkg', action='update', user='username')

    def test_prep_package_list_change_block(self):
        protonmsg.prep_package_list_change('postPackageListChange',
                                           action='block', tag={'name': 'test-tag'},
                                           package={'name': 'test-pkg'},
                                           owner=1,
                                           block=False, extra_arches='i386 x86_64',
                                           force=False, update=False,
                                           user={'name': 'username'})
        self.assertMsg('package.block', type='PackageListChange', tag='test-tag',
                       package='test-pkg', action='block', user='username')

    def test_prep_package_list_change_unblock(self):
        protonmsg.prep_package_list_change('postPackageListChange',
                                           action='unblock', tag={'name': 'test-tag'},
                                           package={'name': 'test-pkg'},
                                           user={'name': 'username'})
        self.assertMsg('package.unblock', type='PackageListChange', tag='test-tag',
                       package='test-pkg', action='unblock', user='username')

    def test_prep_package_list_change_remove(self):
        protonmsg.prep_package_list_change('postPackageListChange',
                                           action='remove', tag={'name': 'test-tag'},
                                           package={'name': 'test-pkg'},
                                           user={'name': 'username'})
        self.assertMsg('package.remove', type='PackageListChange', tag='test-tag',
                       package='test-pkg', action='remove', user='username')

    def test_prep_task_state_change(self):
        info = {'id': 5678,
                'parent': 1234,
                'method': 'build'}
        protonmsg.prep_task_state_change('postTaskStateChange',
                                         info=info, attribute='weight',
                                         old=2.0, new=3.5)
        # no messages should be created for callbacks where attribute != state
        self.assertFalse(hasattr(context, 'protonmsg_msgs'))
        protonmsg.prep_task_state_change('postTaskStateChange',
                                         info=info, attribute='state',
                                         old='FREE', new='OPEN')
        self.assertMsg('task.open', type='TaskStateChange',
                       attribute='state', old='FREE', new='OPEN',
                       **info)

    def test_prep_build_state_change(self):
        info = {'name': 'test-pkg',
                'version': '1.0',
                'release': '1'}
        protonmsg.prep_build_state_change('postBuildStateChange',
                                          info=info, attribute='volume_id',
                                          old=0, new=1)
        # no messages should be created for callbacks where attribute != state
        self.assertFalse(hasattr(context, 'protonmsg_msgs'))
        protonmsg.prep_build_state_change('postBuildStateChange',
                                          info=info, attribute='state',
                                          old=0, new=1)
        self.assertMsg('build.complete', type='BuildStateChange',
                       attribute='state', old='BUILDING', new='COMPLETE',
                       **info)

    def test_prep_import(self):
        build = {'name': 'test-pkg', 'version': '1.0', 'release': '1'}
        protonmsg.prep_import('postImport', type='build', build=build)
        self.assertMsg('import.build', type='Import', importType='build',
                       **build)

    def test_prep_rpm_sign(self):
        build = {'name': 'test-pkg',
                 'version': '1.0',
                 'release': '1'}
        rpm = {'name': 'test-pkg-subpkg',
               'version': '2.0',
               'release': '2',
               'arch': 'x86_64'}
        sigkey = 'a1b2c3d4'
        protonmsg.prep_rpm_sign('postRPMSign', sigkey=sigkey, sighash='fedcba9876543210',
                                build=build, rpm=rpm)
        self.assertMsg('sign.rpm', type='RPMSign', sigkey=sigkey, rpm_name=rpm['name'],
                       rpm_version=rpm['version'], rpm_release=rpm['release'],
                       rpm_arch='x86_64',
                       **build)

    def test_prep_rpm_sign_no_sigkey(self):
        build = {'name': 'test-pkg',
                 'version': '1.0',
                 'release': '1'}
        rpm = {'name': 'test-pkg-subpkg',
               'version': '2.0',
               'release': '2',
               'arch': 'x86_64'}
        sigkey = ''
        protonmsg.prep_rpm_sign('postRPMSign', sigkey=sigkey, sighash='fedcba9876543210',
                                build=build, rpm=rpm)
        self.assertFalse(hasattr(context, 'protonmsg_msgs'))

    def test_prep_tag(self):
        build = {'name': 'test-pkg', 'version': '1.0', 'release': '1'}
        protonmsg.prep_tag('postTag', tag={'name': 'test-tag'},
                           build=build, user={'name': 'test-user'})
        self.assertMsg('build.tag', type='Tag', tag='test-tag',
                       user='test-user', **build)

    def test_prep_untag(self):
        build = {'name': 'test-pkg', 'version': '1.0', 'release': '1'}
        protonmsg.prep_untag('postUntag', tag={'name': 'test-tag'},
                             build=build, user={'name': 'test-user'})
        self.assertMsg('build.untag', type='Untag', tag='test-tag',
                       user='test-user', **build)

    def test_prep_repo_init(self):
        protonmsg.prep_repo_init('postRepoInit', tag={'name': 'test-tag',
            'arches': set(['x86_64', 'i386'])}, repo_id=1234)
        self.assertMsg('repo.init', type='RepoInit', tag='test-tag', repo_id=1234)

    def test_prep_repo_done(self):
        protonmsg.prep_repo_done('postRepoDone', repo={'tag_name': 'test-tag', 'id': 1234},
                                 expire=False)
        self.assertMsg('repo.done', type='RepoDone', tag='test-tag', repo_id=1234, expire=False)

    @patch('protonmsg.Container')
    def test_send_queued_msgs_none(self, Container):
        self.assertFalse(hasattr(context, 'protonmsg_msgs'))
        protonmsg.send_queued_msgs('postCommit')
        self.assertEqual(Container.call_count, 0)
        context.protonmsg_msgs = []
        protonmsg.send_queued_msgs('postCommit')
        self.assertEqual(Container.call_count, 0)

    @patch('protonmsg.Container')
    def test_send_queued_msgs_fail(self, Container):
        context.protonmsg_msgs = [('test.topic', {'testheader': 1}, 'test body')]
        protonmsg.send_queued_msgs('postCommit')

        log = protonmsg.LOG
        self.assertEqual(log.debug.call_count, 2)
        for args in log.debug.call_args_list:
            self.assertTrue(args[0][0].startswith('could not send'))
        self.assertEqual(log.error.call_count, 1)
        self.assertTrue(log.error.call_args[0][0].startswith('could not send'))

    @patch('protonmsg.Container')
    def test_send_queued_msgs_success(self, Container):
        context.protonmsg_msgs = [('test.topic', {'testheader': 1}, 'test body')]
        def clear_msgs():
            del context.protonmsg_msgs[:]
        Container.return_value.run.side_effect = clear_msgs
        protonmsg.send_queued_msgs('postCommit')
        log = protonmsg.LOG
        self.assertEqual(log.debug.call_count, 1)
        self.assertTrue(log.debug.args[0][0].startswith('all msgs sent'))
        self.assertEqual(log.error.call_count, 0)

    @patch('protonmsg.Container')
    def test_send_queued_msgs_test_mode(self, Container):
        context.protonmsg_msgs = [('test.topic', {'testheader': 1}, 'test body')]
        conf = tempfile.NamedTemporaryFile()
        conf.write(six.b("""[broker]
urls = amqps://broker1.example.com:5671 amqps://broker2.example.com:5671
cert = /etc/koji-hub/plugins/client.pem
cacert = /etc/koji-hub/plugins/ca.pem
topic_prefix = koji
connect_timeout = 10
send_timeout = 60
test_mode = on
"""))
        conf.flush()
        protonmsg.CONFIG_FILE = conf.name
        protonmsg.CONFIG = None
        def clear_msgs():
            del context.protonmsg_msgs[:]
        Container.return_value.run.side_effect = clear_msgs
        protonmsg.send_queued_msgs('postCommit')
        Container.assert_not_called()
        log = protonmsg.LOG
        self.assertEqual(log.debug.call_count, len(context.protonmsg_msgs) + 1)
        self.assertTrue(log.debug.args[0][0].startswith('all msgs sent'))
        self.assertEqual(log.error.call_count, 0)


class TestTimeoutHandler(unittest.TestCase):
    def setUp(self):
        confdata = six.StringIO("""[broker]
urls = amqps://broker1.example.com:5671 amqps://broker2.example.com:5671
cert = /etc/koji-hub/plugins/client.pem
cacert = /etc/koji-hub/plugins/ca.pem
topic_prefix = koji
connect_timeout = 10
send_timeout = 60
""")
        if six.PY2:
            conf = SafeConfigParser()
            conf.readfp(confdata)
        else:
            conf = ConfigParser()
            conf.read_file(confdata)
        self.handler = protonmsg.TimeoutHandler('amqps://broker1.example.com:5671', [], conf)

    @patch('protonmsg.SSLDomain')
    def test_on_start(self, SSLDomain):
        event = MagicMock()
        self.handler.on_start(event)
        event.container.connect.assert_called_once_with(url='amqps://broker1.example.com:5671',
                                                        reconnect=False,
                                                        ssl_domain=SSLDomain.return_value)
        self.assertEqual(event.container.schedule.call_count, 2)

    @patch('protonmsg.SSLDomain')
    def test_on_start_no_ssl(self, SSLDomain):
        confdata = six.StringIO("""[broker]
urls = amqp://broker1.example.com:5672 amqp://broker2.example.com:5672
topic_prefix = koji
connect_timeout = 10
send_timeout = 60
""")
        if six.PY2:
            conf = SafeConfigParser()
            conf.readfp(confdata)
        else:
            conf = ConfigParser()
            conf.read_file(confdata)
        handler = protonmsg.TimeoutHandler('amqp://broker1.example.com:5672', [], conf)
        event = MagicMock()
        handler.on_start(event)
        event.container.connect.assert_called_once_with(url='amqp://broker1.example.com:5672',
                                                        reconnect=False,
                                                        ssl_domain=None)
        self.assertEqual(SSLDomain.call_count, 0)

    @patch('protonmsg.SSLDomain')
    def test_on_timer_task(self, SSLDomain):
        event = MagicMock()
        self.handler.on_start(event)
        self.assertTrue(self.handler.timeout_task is not None)
        self.handler.on_timer_task(event)
        event.container.schedule.return_value.cancel.assert_called_once_with()
        self.assertTrue(self.handler.timeout_task is None)
        event.container.stop.assert_called_once_with()
        event.container.stop.reset_mock()
        self.handler.log = MagicMock()
        event.container.connected = True
        self.handler.on_timer_task(event)
        event.container.stop.assert_called_once_with()
        self.assertTrue(self.handler.log.error.call_args[0][0].startswith('send timeout expired'))

    @patch('protonmsg.SSLDomain')
    def test_on_connection_opened(self, SSLDomain):
        event = MagicMock()
        self.handler.on_start(event)
        self.assertTrue(self.handler.connect_task is not None)
        self.handler.on_connection_opened(event)
        self.assertTrue(event.container.connected)
        event.container.schedule.return_value.cancel.assert_called_once_with()
        self.assertTrue(self.handler.connect_task is None)

    @patch('protonmsg.Message')
    @patch('protonmsg.SSLDomain')
    def test_send_msgs(self, SSLDomain, Message):
        event = MagicMock()
        self.handler.on_start(event)
        self.handler.msgs = [('testtopic', {'testheader': 1}, '"test body"')]
        self.handler.on_connection_opened(event)
        event.container.create_sender.assert_called_once_with(event.connection,
                                                              target='topic://koji.testtopic')
        Message.assert_called_once_with(properties={'testheader': 1}, body='"test body"')
        sender = event.container.create_sender.return_value
        sender.send.assert_called_once_with(Message.return_value)

    @patch('protonmsg.Message')
    @patch('protonmsg.SSLDomain')
    def test_update_pending(self, SSLDomain, Message):
        event = MagicMock()
        self.handler.on_start(event)
        self.handler.msgs = [('testtopic', {'testheader': 1}, '"test body"'),
                             ('testtopic', {'testheader': 2}, '"test body"')]
        delivery0 = MagicMock()
        delivery1 = MagicMock()
        sender = event.container.create_sender.return_value
        sender.send.side_effect = [delivery0, delivery1]
        log = MagicMock()
        self.handler.log = log
        self.handler.on_connection_opened(event)
        self.assertEqual(len(self.handler.pending), 2)
        event.delivery = delivery0
        self.handler.update_pending(event)
        self.assertEqual(len(self.handler.pending), 1)
        self.assertTrue(delivery0 not in self.handler.pending)
        log.debug.call_args[0][0].startswith('removed msg')
        event.delivery = delivery1
        self.handler.update_pending(event)
        self.assertEqual(len(self.handler.pending), 0)
        self.assertTrue(delivery0 not in self.handler.pending)
        log.error.call_args[0][0].startswith('2 messages unsent')
        sender.close.assert_called_once_with()
        self.assertEqual(event.container.schedule.return_value.cancel.call_count, 2)
        event.connection.close.assert_called_once_with()

    @patch('protonmsg.Message')
    @patch('protonmsg.SSLDomain')
    def test_on_settled(self, SSLDomain, Message):
        event = MagicMock()
        self.handler.on_start(event)
        self.handler.msgs = [('testtopic', {'testheader': 1}, '"test body"')]
        self.handler.on_connection_opened(event)
        delivery = event.container.create_sender.return_value.send.return_value
        self.assertTrue(delivery in self.handler.pending)
        event.delivery = delivery
        self.handler.on_settled(event)
        self.assertEqual(len(self.handler.msgs), 0)
        self.assertEqual(len(self.handler.pending), 0)

    @patch('protonmsg.Message')
    @patch('protonmsg.SSLDomain')
    def test_on_rejected(self, SSLDomain, Message):
        event = MagicMock()
        self.handler.on_start(event)
        self.handler.msgs = [('testtopic', {'testheader': 1}, '"test body"')]
        self.handler.on_connection_opened(event)
        delivery = event.container.create_sender.return_value.send.return_value
        self.assertTrue(delivery in self.handler.pending)
        event.delivery = delivery
        self.handler.on_rejected(event)
        self.assertEqual(len(self.handler.msgs), 1)
        self.assertEqual(len(self.handler.pending), 0)

    @patch('protonmsg.Message')
    @patch('protonmsg.SSLDomain')
    def test_on_released(self, SSLDomain, Message):
        event = MagicMock()
        self.handler.on_start(event)
        self.handler.msgs = [('testtopic', {'testheader': 1}, '"test body"')]
        self.handler.on_connection_opened(event)
        delivery = event.container.create_sender.return_value.send.return_value
        self.assertTrue(delivery in self.handler.pending)
        event.delivery = delivery
        self.handler.on_released(event)
        self.assertEqual(len(self.handler.msgs), 1)
        self.assertEqual(len(self.handler.pending), 0)

    @patch('protonmsg.SSLDomain')
    def test_on_transport_tail_closed(self, SSLDomain):
        event = MagicMock()
        self.handler.on_start(event)
        self.assertTrue(self.handler.connect_task is not None)
        self.assertTrue(self.handler.timeout_task is not None)
        self.handler.on_transport_tail_closed(event)
        self.assertEqual(event.container.schedule.return_value.cancel.call_count, 2)
        self.assertTrue(self.handler.connect_task is None)
        self.assertTrue(self.handler.timeout_task is None)
