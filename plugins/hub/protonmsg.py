# Koji callback for sending notifications about events using the
# qpid proton library.
# Copyright (c) 2016 Red Hat, Inc.
#
# Authors:
#     Mike Bonnet <mikeb@redhat.com>

import json
import logging
import random

from proton import Message, SSLDomain
from proton.handlers import MessagingHandler
from proton.reactor import Container

import koji
from koji.context import context
from koji.plugin import callback, convert_datetime, ignore_error
from kojihub import get_build_type
from kojihub.db import QueryProcessor, InsertProcessor, DeleteProcessor, db_lock

CONFIG_FILE = '/etc/koji-hub/plugins/protonmsg.conf'
CONFIG = None
LOG = logging.getLogger('koji.plugin.protonmsg')


class TimeoutHandler(MessagingHandler):
    def __init__(self, url, msgs, conf, *args, **kws):
        super(TimeoutHandler, self).__init__(*args, **kws)
        self.url = url
        self.msgs = msgs
        self.conf = conf
        self.pending = {}
        self.senders = {}
        self.connect_task = None
        self.timeout_task = None
        self.log = logging.getLogger('koji.plugin.protonmsg.TimeoutHandler')

    def on_start(self, event):
        self.log.debug('Container starting')
        event.container.connected = False
        if self.conf.has_option('broker', 'cert') and self.conf.has_option('broker', 'cacert'):
            ssl = SSLDomain(SSLDomain.MODE_CLIENT)
            cert = self.conf.get('broker', 'cert')
            ssl.set_credentials(cert, cert, None)
            ssl.set_trusted_ca_db(self.conf.get('broker', 'cacert'))
            ssl.set_peer_authentication(SSLDomain.VERIFY_PEER)
        else:
            ssl = None
        self.log.debug('connecting to %s', self.url)
        event.container.connect(url=self.url, reconnect=False, ssl_domain=ssl)
        connect_timeout = self.conf.getint('broker', 'connect_timeout')
        self.connect_task = event.container.schedule(connect_timeout, self)
        send_timeout = self.conf.getint('broker', 'send_timeout')
        self.timeout_task = event.container.schedule(send_timeout, self)

    def on_timer_task(self, event):
        if not event.container.connected:
            self.log.error('not connected, stopping container')
            if self.timeout_task:
                self.timeout_task.cancel()
                self.timeout_task = None
            event.container.stop()
        else:
            # This should only run when called from the timeout task
            self.log.error('send timeout expired with %s messages unsent, stopping container',
                           len(self.msgs))
            event.container.stop()

    def on_connection_opened(self, event):
        event.container.connected = True
        self.connect_task.cancel()
        self.connect_task = None
        self.log.debug('connection to %s opened successfully', event.connection.hostname)
        self.send_msgs(event)

    @property
    def topic_prefix(self):
        """Normalize topic_prefix value that the user configured.

        RabbitMQ brokers require that topics start with "/topic/"
        ActiveMQ brokers require that topics start with "topic://"

        If the user specified a prefix that begins with one or the other, use
        that. For backwards compatibility, if the user chose neither, prepend
        "topic://".
        """
        koji_topic_prefix = self.conf.get('broker', 'topic_prefix')
        if koji_topic_prefix.startswith('/topic/'):
            return koji_topic_prefix
        if koji_topic_prefix.startswith('topic://'):
            return koji_topic_prefix
        return 'topic://' + koji_topic_prefix

    def send_msgs(self, event):
        ttl = self.conf.getfloat('message', 'ttl', fallback=None)
        for msg in self.msgs:
            # address is like "topic://koji.package.add"
            address = self.topic_prefix + '.' + msg['address']
            if address in self.senders:
                sender = self.senders[address]
                self.log.debug('retrieved cached sender for %s', address)
            else:
                sender = event.container.create_sender(event.connection, target=address)
                self.log.debug('created new sender for %s', address)
                self.senders[address] = sender
            pmsg = Message(properties=msg['props'], body=msg['body'])
            if ttl:
                # The message class expects seconds, even though the c api uses milliseconds
                pmsg.ttl = ttl
            delivery = sender.send(pmsg)
            self.log.debug('sent message: %s', msg['props'])
            self.pending[delivery] = msg

    def update_pending(self, event):
        msg = self.pending[event.delivery]
        del self.pending[event.delivery]
        self.log.debug('removed message from self.pending: %s', msg['props'])
        if not self.pending:
            if self.msgs:
                self.log.error('%s messages unsent (rejected or released)', len(self.msgs))
            else:
                self.log.debug('all messages sent successfully')
            for sender in self.senders.values():
                self.log.debug('closing sender for %s', sender.target.address)
                sender.close()
            if self.timeout_task:
                self.log.debug('canceling timeout task')
                self.timeout_task.cancel()
                self.timeout_task = None
            self.log.debug('closing connection to %s', event.connection.hostname)
            event.connection.close()

    def on_settled(self, event):
        msg = self.pending[event.delivery]
        self.msgs.remove(msg)
        self.log.debug('removed message from self.msgs: %s', msg['props'])
        self.update_pending(event)

    def on_rejected(self, event):
        msg = self.pending[event.delivery]
        self.log.error('message was rejected: %s', msg['props'])
        self.update_pending(event)

    def on_released(self, event):
        msg = self.pending[event.delivery]
        self.log.error('message was released: %s', msg['props'])
        self.update_pending(event)

    def on_transport_tail_closed(self, event):
        if self.connect_task:
            self.log.debug('canceling connect timer')
            self.connect_task.cancel()
            self.connect_task = None
        if self.timeout_task:
            self.log.debug('canceling send timer')
            self.timeout_task.cancel()
            self.timeout_task = None


def _strip_extra(buildinfo):
    """If extra_limit is configured, compare extra's size and drop it,
    if it is over"""
    global CONFIG
    if not CONFIG:
        CONFIG = koji.read_config_files([(CONFIG_FILE, True)])
    if CONFIG.has_option('message', 'extra_limit'):
        extra_limit = abs(CONFIG.getint('message', 'extra_limit'))
        if extra_limit == 0:
            return buildinfo
        extra_size = len(json.dumps(buildinfo.get('extra', {}), default=json_serialize))
        if extra_limit and extra_size > extra_limit:
            LOG.debug("Dropping 'extra' from build %s (length: %d > %d)" %
                      (buildinfo['nvr'], extra_size, extra_limit))
            buildinfo = buildinfo.copy()
            del buildinfo['extra']
    return buildinfo


def json_serialize(o):
    """JSON helper to encode otherwise unserializable data types"""
    if isinstance(o, set):
        return list(o)
    LOG.error("Not JSON serializable data: %s" % repr(o))
    return {"error": "Can't serialize", "type": str(type(o))}


def queue_msg(address, props, data):
    msgs = getattr(context, 'protonmsg_msgs', None)
    if msgs is None:
        msgs = []
        context.protonmsg_msgs = msgs
    body = json.dumps(data, default=json_serialize)
    msgs.append({'address': address, 'props': props, 'body': body})


@convert_datetime
@callback('postPackageListChange')
def prep_package_list_change(cbtype, *args, **kws):
    address = 'package.' + kws['action']
    props = {'type': cbtype[4:],
             'tag': kws['tag']['name'],
             'package': kws['package']['name'],
             'action': kws['action'],
             'user': kws['user']['name']}
    queue_msg(address, props, kws)


@convert_datetime
@callback('postTaskStateChange')
def prep_task_state_change(cbtype, *args, **kws):
    if kws['attribute'] != 'state':
        return
    address = 'task.' + kws['new'].lower()
    props = {'type': cbtype[4:],
             'id': kws['info']['id'],
             'parent': kws['info']['parent'],
             'method': kws['info']['method'],
             'attribute': kws['attribute'],
             'old': kws['old'],
             'new': kws['new']}
    queue_msg(address, props, kws)


@convert_datetime
@callback('postBuildStateChange')
def prep_build_state_change(cbtype, *args, **kws):
    if kws['attribute'] != 'state':
        return
    old = kws['old']
    if old is not None:
        old = koji.BUILD_STATES[old]
    new = koji.BUILD_STATES[kws['new']]
    address = 'build.' + new.lower()
    kws['info'] = _strip_extra(kws['info'])
    kws['btypes'] = get_build_type(kws['info'])
    props = {'type': cbtype[4:],
             'name': kws['info']['name'],
             'version': kws['info']['version'],
             'release': kws['info']['release'],
             'attribute': kws['attribute'],
             'old': old,
             'new': new}
    queue_msg(address, props, kws)


@convert_datetime
@callback('postImport')
def prep_import(cbtype, *args, **kws):
    kws['build'] = _strip_extra(kws['build'])
    address = 'import.' + kws['type']
    props = {'type': cbtype[4:],
             'importType': kws['type'],
             'name': kws['build']['name'],
             'version': kws['build']['version'],
             'release': kws['build']['release']}
    queue_msg(address, props, kws)


@convert_datetime
@callback('postRPMSign')
def prep_rpm_sign(cbtype, *args, **kws):
    if not kws['sigkey']:
        return
    kws['build'] = _strip_extra(kws['build'])
    address = 'sign.rpm'
    props = {'type': cbtype[4:],
             'sigkey': kws['sigkey'],
             'name': kws['build']['name'],
             'version': kws['build']['version'],
             'release': kws['build']['release'],
             'rpm_name': kws['rpm']['name'],
             'rpm_version': kws['rpm']['version'],
             'rpm_release': kws['rpm']['release'],
             'rpm_arch': kws['rpm']['arch']}
    queue_msg(address, props, kws)


def _prep_tag_msg(address, cbtype, kws):
    kws['build'] = _strip_extra(kws['build'])
    props = {'type': cbtype[4:],
             'tag': kws['tag']['name'],
             'name': kws['build']['name'],
             'version': kws['build']['version'],
             'release': kws['build']['release'],
             'user': kws['user']['name']}
    queue_msg(address, props, kws)


@convert_datetime
@callback('postTag')
def prep_tag(cbtype, *args, **kws):
    _prep_tag_msg('build.tag', cbtype, kws)


@convert_datetime
@callback('postUntag')
def prep_untag(cbtype, *args, **kws):
    _prep_tag_msg('build.untag', cbtype, kws)


@convert_datetime
@callback('postRepoInit')
def prep_repo_init(cbtype, *args, **kws):
    kws['task_id'] = kws.get('task_id')
    address = 'repo.init'
    props = {'type': cbtype[4:],
             'tag': kws['tag']['name'],
             'repo_id': kws['repo_id'],
             'task_id': kws['task_id']}
    queue_msg(address, props, kws)


@convert_datetime
@callback('postRepoDone')
def prep_repo_done(cbtype, *args, **kws):
    kws['task_id'] = kws.get('task_id')
    address = 'repo.done'
    props = {'type': cbtype[4:],
             'tag': kws['repo']['tag_name'],
             'repo_id': kws['repo']['id'],
             'task_id': kws['repo']['task_id'],
             'expire': kws['expire']}
    queue_msg(address, props, kws)


@convert_datetime
@callback('postBuildPromote')
def prep_build_promote(cbtype, *args, **kws):
    kws['build'] = _strip_extra(kws['build'])
    address = 'build.promote'
    props = {'type': cbtype[4:],
             'build_id': kws['build']['id'],
             'name': kws['build']['name'],
             'version': kws['build']['version'],
             'release': kws['build']['release'],
             'draft_release': kws['draft_release'],
             'target_release': kws['target_release'],
             'user': kws['user']['name']}
    queue_msg(address, props, kws)


def _send_msgs(urls, msgs, CONFIG):
    random.shuffle(urls)
    for url in urls:
        try:
            container = Container(TimeoutHandler(url, msgs, CONFIG))
            container.run()
        except Exception as ex:
            # It's ok if we don't send messages for any reason. We'll try again later.
            LOG.debug(f'container setup error ({url}): {ex}')

        if msgs:
            LOG.debug('could not send to %s, %s messages remaining',
                      url, len(msgs))
        else:
            LOG.debug('all messages sent to %s successfully', url)
            break
    else:
        LOG.error('could not send messages to any destinations')
    return msgs


def store_to_db(msgs):
    c = context.cnx.cursor()
    # we're running in postCommit, so we need to handle new transaction
    c.execute('BEGIN')
    for msg in msgs:
        address = msg['address']
        body = msg['body']
        props = json.dumps(msg['props'])
        insert = InsertProcessor(table='proton_queue')
        insert.set(address=address, props=props, body=body)
        insert.execute()
    c.execute('COMMIT')


def handle_db_msgs(urls, CONFIG):
    limit = CONFIG.getint('queue', 'batch_size', fallback=100)
    c = context.cnx.cursor()
    # we're running in postCommit, so we need to handle new transaction
    c.execute('BEGIN')
    if not db_lock('protonmsg-plugin', wait=False):
        LOG.debug('skipping db queue due to lock')
        return
    try:
        max_age = CONFIG.getint('queue', 'max_age', fallback=None)
        if not max_age:
            # age in config file is deprecated
            max_age = CONFIG.getint('queue', 'age', fallback=24)
        delete = DeleteProcessor(table='proton_queue',
                                 clauses=[f"created_ts < NOW() -'{max_age:d} hours'::interval"])
        delete.execute()
        query = QueryProcessor(tables=('proton_queue',),
                               columns=('id', 'address', 'props', 'body::TEXT'),
                               aliases=('id', 'address', 'props', 'body'),
                               opts={'order': 'id', 'limit': limit})
        msgs = list(query.execute())
        if not msgs:
            return
        if CONFIG.getboolean('broker', 'test_mode', fallback=False):
            LOG.debug('test mode: skipping send for %i messages from db', len(msgs))
            unsent = []
        else:
            # we pass a copy of msgs because _send_msgs modifies it
            unsent = {m['id'] for m in _send_msgs(urls, list(msgs), CONFIG)}
        sent = [m for m in msgs if m['id'] not in unsent]
        if sent:
            ids = [msg['id'] for msg in sent]
            delete = DeleteProcessor(table='proton_queue', clauses=['id IN %(ids)s'],
                                     values={'ids': ids})
            delete.execute()
    finally:
        # make sure we free the lock
        try:
            c.execute('COMMIT')
        except Exception:
            c.execute('ROLLBACK')


@ignore_error
@convert_datetime
@callback('postCommit')
def send_queued_msgs(cbtype, *args, **kws):
    global CONFIG
    msgs = getattr(context, 'protonmsg_msgs', None)
    if not msgs:
        return
    if not CONFIG:
        CONFIG = koji.read_config_files([(CONFIG_FILE, True)])
    urls = CONFIG.get('broker', 'urls').split()
    test_mode = False
    if CONFIG.has_option('broker', 'test_mode'):
        test_mode = CONFIG.getboolean('broker', 'test_mode')
    db_enabled = False
    if CONFIG.has_option('queue', 'enabled'):
        db_enabled = CONFIG.getboolean('queue', 'enabled')

    if test_mode:
        LOG.debug('test mode: skipping send to urls: %r', urls)
        fail_chance = CONFIG.getint('broker', 'test_mode_fail', fallback=0)
        if fail_chance:
            # simulate unsent messages in test mode
            sent = []
            unsent = []
            for m in msgs:
                if random.randint(1, 100) <= fail_chance:
                    unsent.append(m)
                else:
                    sent.append(m)
            if unsent:
                LOG.info('simulating %i unsent messages' % len(unsent))
        else:
            sent = msgs
            unsent = []
        for msg in sent:
            LOG.debug('test mode: skipped msg: %r', msg)
    else:
        unsent = _send_msgs(urls, msgs, CONFIG)

    if db_enabled:
        if unsent:
            # if we still have some messages, store them and leave for another call to pick them up
            store_to_db(msgs)
        else:
            # otherwise we are another call - look to db if there remains something to send
            handle_db_msgs(urls, CONFIG)
    elif unsent:
        LOG.error('could not send %i messages. db queue disabled' % len(msgs))
