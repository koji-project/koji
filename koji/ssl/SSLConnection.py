#!/usr/bin/python
#
# Higher-level SSL objects used by rpclib
#
# Copyright (c) 2002 Red Hat, Inc.
#
# Author: Mihai Ibanescu <misa@redhat.com>
# Modifications by Dan Williams <dcbw@redhat.com>


from OpenSSL import SSL, crypto
import os, string, time, socket, select


class SSLConnection:
    """
    This whole class exists just to filter out a parameter
    passed in to the shutdown() method in SimpleXMLRPC.doPOST()
    """

    DEFAULT_TIMEOUT = 20

    def __init__(self, conn):
        """
        Connection is not yet a new-style class,
        so I'm making a proxy instead of subclassing.
        """
        self.__dict__["conn"] = conn
        self.__dict__["close_refcount"] = 1
        self.__dict__["closed"] = False
        self.__dict__["timeout"] = self.DEFAULT_TIMEOUT

    def __del__(self):
        self.__dict__["conn"].close()

    def __getattr__(self,name):
        return getattr(self.__dict__["conn"], name)

    def __setattr__(self,name, value):
        setattr(self.__dict__["conn"], name, value)

    def settimeout(self, timeout):
        if timeout == None:
            self.__dict__["timeout"] = self.DEFAULT_TIMEOUT
        else:
            self.__dict__["timeout"] = timeout
        self.__dict__["conn"].settimeout(timeout)

    def shutdown(self, how=1):
        """
        SimpleXMLRpcServer.doPOST calls shutdown(1),
        and Connection.shutdown() doesn't take
        an argument. So we just discard the argument.
        """
        self.__dict__["conn"].shutdown()

    def accept(self):
        """
        This is the other part of the shutdown() workaround.
        Since servers create new sockets, we have to infect
        them with our magic. :)
        """
        c, a = self.__dict__["conn"].accept()
        return (SSLConnection(c), a)

    def makefile(self,  mode='r', bufsize=-1):
        """
        We need to use socket._fileobject Because SSL.Connection
        doesn't have a 'dup'. Not exactly sure WHY this is, but
        this is backed up by comments in socket.py and SSL/connection.c

        Since httplib.HTTPSResponse/HTTPConnection depend on the
        socket being duplicated when they close it, we refcount the
        socket object and don't actually close until its count is 0.
        """
        self.__dict__["close_refcount"] = self.__dict__["close_refcount"] + 1
        return PlgFileObject(self, mode, bufsize)

    def close(self):
        if self.__dict__["closed"]:
            return
        self.__dict__["close_refcount"] = self.__dict__["close_refcount"] - 1
        if self.__dict__["close_refcount"] == 0:
            self.shutdown()
            self.__dict__["conn"].close()
            self.__dict__["closed"] = True

    def sendall(self, data, flags=0):
        """
        - Use select() to simulate a socket timeout without setting the socket
            to non-blocking mode.
        - Don't use pyOpenSSL's sendall() either, since it just loops on WantRead
            or WantWrite, consuming 100% CPU, and never times out.
        """
        timeout = self.__dict__["timeout"]
        con = self.__dict__["conn"]
        (read, write, excpt) = select.select([], [con], [], timeout)
        if not con in write:
            raise socket.timeout((110, "Operation timed out."))

        starttime = time.time()
        origlen = len(data)
        sent = -1
        while len(data):
            curtime = time.time()
            if curtime - starttime > timeout:
                raise socket.timeout((110, "Operation timed out."))

            try:
                sent = con.send(data, flags)
            except SSL.SysCallError, e:
                if e[0] == 32:      # Broken Pipe
                    self.close()
                    sent = 0
                else:
                    raise socket.error(e)
            except (SSL.WantWriteError, SSL.WantReadError):
                time.sleep(0.2)
                continue

            data = data[sent:]
        return origlen - len(data)

    def recv(self, bufsize, flags=0):
        """
        Use select() to simulate a socket timeout without setting the socket
        to non-blocking mode
        """
        timeout = self.__dict__["timeout"]
        con = self.__dict__["conn"]
        (read, write, excpt) = select.select([con], [], [], timeout)
        if not con in read:
            raise socket.timeout((110, "Operation timed out."))

        starttime = time.time()
        while True:
            curtime = time.time()
            if curtime - starttime > timeout:
                raise socket.timeout((110, "Operation timed out."))

            try:
                return con.recv(bufsize, flags)
            except SSL.ZeroReturnError:
                return None
            except SSL.WantReadError:
                time.sleep(0.2)
        return None

class PlgFileObject(socket._fileobject):
    def close(self):
        """
        socket._fileobject doesn't actually _close_ the socket,
        which we want it to do, so we have to override.
        """
        try:
            if self._sock:
                self.flush()
                self._sock.close()
        finally:
            self._sock = None

