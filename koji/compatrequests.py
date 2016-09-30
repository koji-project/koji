"""
koji.compatrequests
~~~~~~~~~~~~~~~~~~~

This module contains a *very limited* partial implemention of the requests
module that is based on the older codepaths in koji. It only provides
the bits that koji needs.
"""


class Session(object):

    def post(self, **kwargs):
        pass


class Response(object):

    def __init__(self, session):
        self.session = session

    def iter_content(self, blocksize=8192):
        pass
