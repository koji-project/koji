from koji.plugin import export_cli, export_as


@export_as('foo6')
@export_cli
def foo():
    pass
