#!/usr/bin/python

#This is a wrapper around mod_python.publisher so that we can trap some exceptions
import koji
import mod_python.publisher
import sys
import traceback
import util
from  util import _initValues
from  util import _genHTML

old_publish_object = mod_python.publisher.publish_object

def publish_object(req, object):
    try:
        return old_publish_object(req, object)
    #except koji.ServerOffline:
    #    values = _initValues(req, 'Outage', 'outage')
    #    return old_publish_object(req, _genHTML(req, 'outage.chtml'))
    except Exception:
        etype, e = sys.exc_info()[:2]
        if isinstance(e, koji.ServerOffline):
            values = _initValues(req, 'Outage', 'outage')
        else:
            values = _initValues(req, 'Error', 'error')
        values['etype'] = etype
        values['exception'] = e
        values['explanation'], values['debug_level'] = util.explainError(e)
        values['tb_short'] = ''.join(traceback.format_exception_only(etype, e))
        if int(req.get_config().get("PythonDebug", 0)):
            values['tb_long'] = ''.join(traceback.format_exception(*sys.exc_info()))
        else:
            values['tb_long'] = "Full tracebacks disabled"
        return old_publish_object(req, _genHTML(req, 'error.chtml'))

mod_python.publisher.publish_object = publish_object

def handler(req):
    return mod_python.publisher.handler(req)
