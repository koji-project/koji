# Example Koji callback
# Copyright (c) 2009-2014 Red Hat, Inc.
# This callback simply logs all of its args using the logging module
#
# Authors:
#     Mike Bonnet <mikeb@redhat.com>

from __future__ import absolute_import
from koji.plugin import callbacks, callback, ignore_error
import logging

@callback(*list(callbacks.keys()))
@ignore_error
def echo(cbtype, *args, **kws):
    logging.getLogger('koji.plugin.echo').info('Called the %s callback, args: %s; kws: %s',
                                               cbtype, str(args), str(kws))
