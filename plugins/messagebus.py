# Koji callback for sending notifications about events to a messagebus (amqp broker)
# Copyright (c) 2009 Red Hat, Inc.
#
# Authors:
#     Mike Bonnet <mikeb@redhat.com>

from koji.plugin import callbacks, callback, ignore_error
import ConfigParser
import logging
import qpid
import qpid.util
import qpid.connection
import qpid.datatypes
try:
    import json
except ImportError:
    import simplejson as json

MAX_KEY_LENGTH = 255
CONFIG_FILE = '/etc/koji-hub/plugins/messagebus.conf'

config = None
connection = None

def get_session():
    global connection, config
    if connection:
        try:
            return connection.session('koji-' + str(qpid.datatypes.uuid4()))
        except:
            logging.getLogger('koji.plugin.messagebus').warning('Error getting session, will retry', exc_info=True)
            connection = None

    config = ConfigParser.SafeConfigParser()
    config.read(CONFIG_FILE)

    sock = qpid.util.connect(config.get('broker', 'host'),
                             int(config.get('broker', 'port')))
    if config.getboolean('broker', 'ssl'):
        sock = qpid.util.ssl(sock)
    conn_opts = {'sock': sock, 'mechanism': config.get('broker', 'auth')}
    if conn_opts['mechanism'] == 'PLAIN':
        conn_opts['username'] = config.get('broker', 'username')
        conn_opts['password'] = config.get('broker', 'password')
    conn = qpid.connection.Connection(**conn_opts)
    conn.start()
    session = conn.session('koji-' + str(qpid.datatypes.uuid4()))

    session.exchange_declare(exchange=config.get('exchange', 'name'),
                             type=config.get('exchange', 'type'),
                             durable=config.getboolean('exchange', 'durable'))

    connection = conn

    return session

def _token_append(tokenlist, val):
    # Replace any periods with underscores so we have a deterministic number of tokens
    val = val.replace('.', '_')
    tokenlist.append(val)

def get_routing_key(cbtype, *args, **kws):
    global config
    # We're only registering for post callbacks, so strip
    # off the redundant "post" prefix
    key = [config.get('topic', 'prefix'), cbtype[4:]]

    if cbtype in ('prePackageListChange', 'postPackageListChange'):
        _token_append(key, kws['tag']['name'])
        _token_append(key, kws['package']['name'])
    elif cbtype in ('preTaskStateChange', 'postTaskStateChange'):
        _token_append(key, kws['attribute'])
    elif cbtype in ('preBuildStateChange', 'postBuildStateChange'):
        info = kws['info']
        _token_append(key, kws['attribute'])
        _token_append(key, info['name'])
    elif cbtype in ('preImport', 'postImport'):
        _token_append(key, kws['type'])
    elif cbtype in ('preTag', 'postTag', 'preUntag', 'postUntag'):
        _token_append(key, kws['tag']['name'])
        build = kws['build']
        _token_append(key, build['name'])
        _token_append(key, kws['user']['name'])
    elif cbtype in ('preRepoInit', 'postRepoInit'):
        _token_append(key, kws['tag']['name'])
    elif cbtype in ('preRepoDone', 'postRepoDone'):
        _token_append(key, kws['repo']['tag_name'])

    # ensure the routing key is an ascii string with a maximum
    # length of 255 characters
    key = '.'.join(key)
    key = key.encode('ascii', 'xmlcharrefreplace')
    key = key[:MAX_KEY_LENGTH]
    return key

def get_message_headers(cbtype, *args, **kws):
    # We're only registering for post callbacks, so strip
    # off the redundant "post" prefix
    headers = {'type': cbtype[4:]}

    if cbtype in ('prePackageListChange', 'postPackageListChange'):
        headers['tag'] = kws['tag']['name']
        headers['package'] = kws['package']['name']
    elif cbtype in ('preTaskStateChange', 'postTaskStateChange'):
        headers['attribute'] = kws['attribute']
        headers['old'] = kws['old']
        headers['new'] = kws['new']
    elif cbtype in ('preBuildStateChange', 'postBuildStateChange'):
        info = kws['info']
        headers['name'] = info['name']
        headers['version'] = info['version']
        headers['release'] = info['release']
        headers['attribute'] = kws['attribute']
        headers['old'] = kws['old']
        headers['new'] = kws['new']
    elif cbtype in ('preImport', 'postImport'):
        headers['importType'] = kws['type']
    elif cbtype in ('preTag', 'postTag', 'preUntag', 'postUntag'):
        headers['tag'] = kws['tag']['name']
        build = kws['build']
        headers['name'] = build['name']
        headers['version'] = build['version']
        headers['release'] = build['release']
        headers['user'] = kws['user']['name']
    elif cbtype in ('preRepoInit', 'postRepoInit'):
        headers['tag'] = kws['tag']['name']
    elif cbtype in ('preRepoDone', 'postRepoDone'):
        headers['tag'] = kws['repo']['tag_name']

    return headers

def encode_data(data):
    global config
    format = config.get('format', 'encoding')
    if format == 'json':
        return json.dumps(data)
    else:
        raise koji.PluginError, 'unsupported encoding: %s' % format

@callback(*[c for c in callbacks.keys() if c.startswith('post')])
@ignore_error
def send_message(cbtype, *args, **kws):
    global config
    session = get_session()
    exchange_type = config.get('exchange', 'type')

    if exchange_type == 'topic':
        routing_key = get_routing_key(cbtype, *args, **kws)
        props = session.delivery_properties(routing_key=routing_key)
    elif exchange_type == 'headers':
        headers = get_message_headers(cbtype, *args, **kws)
        props = session.message_properties(application_headers=headers)
    else:
        raise koji.PluginError, 'unsupported exchange type: %s' % exchange_type

    data = kws.copy()
    if args:
        data['args'] = list(args)
    payload = encode_data(data)
    message = qpid.datatypes.Message(props, payload)
    session.message_transfer(destination=config.get('exchange', 'name'), message=message)
    session.close()
