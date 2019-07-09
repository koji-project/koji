from __future__ import absolute_import
from koji.plugin import export_cli, export_as


@export_as('foobar')
@export_cli
def foo():
    pass


@export_cli
def foo2():
    pass


def foo3():
    pass


foo4 = 'foo4'


class bar():
    pass
