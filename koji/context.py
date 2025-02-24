# Copyright (c) 2005-2014 Red Hat, Inc.
#
#    Koji is free software; you can redistribute it and/or
#    modify it under the terms of the GNU Lesser General Public
#    License as published by the Free Software Foundation;
#    version 2.1 of the License.
#
#    This software is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
#    Lesser General Public License for more details.
#
#    You should have received a copy of the GNU Lesser General Public
#    License along with this software; if not, write to the Free Software
#    Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301  USA
#
# Authors:
#       Mike McLean <mikem@redhat.com>

# This module provides a threadlocal instance that kojihub uses to store
# request context.
# In the past, we had a custom ThreadLocal implementation, but now this is
# just a thin wrapper around threading.local

from __future__ import absolute_import

import threading


class ThreadLocal(threading.local):
    """A small compatibility wrapper around threading.local"""

    def _threadclear(self):
        self.__dict__.clear()


context = ThreadLocal()
