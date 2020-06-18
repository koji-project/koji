# Example Koji callback
# Copyright (c) 2009-2014 Red Hat, Inc.
# This callback simply logs all of its args using the logging module
#
# Authors:
#     Mike Bonnet <mikeb@redhat.com>

import logging

from koji.plugin import callback, callbacks, ignore_error
from koji.util import to_list


@callback(*to_list(callbacks.keys()))
@ignore_error
def echo(cbtype, *args, **kws):
    logging.getLogger('koji.plugin.echo').info('Called the %s callback, args: %s; kws: %s',
                                               cbtype, str(args), str(kws))
