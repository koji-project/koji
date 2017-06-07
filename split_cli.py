#!/usr/bin/python

import imp
import inspect
import koji
import os.path
import sys

filename = sys.argv[1]
fo = file(filename)
mod = imp.load_module('some_code', fo, fo.name, ('.py', 'U', 1))
fo.close()

destdir = sys.argv[2]
if not os.path.isdir(destdir):
    raise Exception("Not a directory" % destdir)

def get_dest(name, obj):
    dest = None
    if name in ['get_options', 'handle_help', 'list_commands']:
        dest = 'cli/koji'
    elif name in ['handle_runroot', 'handle_save_failed_tree']:
        dest = 'plugins/cli/' + name[7:] + '.py'
    elif name.startswith('handle_') or name.startswith('anon_handle'):
        dest = 'cli/koji_cli/commands.py'
    elif inspect.isclass(obj):
        dest = 'cli/koji_cli/lib.py'
    elif name.startswith('print_group_'):
        dest = 'cli/koji_cli/commands.py'
    elif name.startswith('_import_comps'):
        dest = 'cli/koji_cli/commands.py'
    elif not name.startswith('_'):
        dest = 'cli/koji_cli/lib.py'
    elif name in ['_unique_path', '_format_size', '_format_secs',
            '_progress_callback', '_running_in_bg', '_']:
        dest = 'cli/koji_cli/lib.py'
    elif name.startswith('_'):
        dest = 'cli/koji_cli/commands.py'
    return dest

order = []
modfile = inspect.getsourcefile(mod)
sys.stderr.write("Module file: %r\n" % modfile)
for name in vars(mod):
    obj = getattr(mod, name)
    if inspect.isclass(obj) or inspect.isfunction(obj):
        try:
            objfile = inspect.getsourcefile(obj)
        except TypeError as ex:
            sys.stderr.write("Skipping %s from %s\n" % (name, obj))
            continue
        if objfile != modfile:
            sys.stderr.write("Skipping %s from %s\n" % (name, inspect.getfile(obj)))
            continue
        data = inspect.getsourcelines(obj)
        lineno = data[1]
        order.append((lineno, data[0], name, obj))


dests = set()
for (lineno, source, name, obj) in sorted(order):
    dest = get_dest(name, obj)
    dests.add(dest)
outfiles = {}
for dest in dests:
    if dest:
        fn = os.path.join(destdir, dest)
        outfiles[dest] = file(fn, 'w')

orig = file(filename).readlines()
ofs = 0
last_dest = None
for (lineno, source, name, obj) in sorted(order):
    lineno -= 1   # make 0-indexed
    dest = get_dest(name, obj)
    if dest is None:
        # the _ functions go different places
        # defer (treat as intermediate content)
        continue
    if lineno > ofs:
        # intermediate content
        if last_dest == dest:
            fo = outfiles[dest]
        else:
            fo = outfiles['cli/koji']
        for line in orig[ofs:lineno]:
            fo.write(line)
    fo = outfiles[dest]
    for line in source:
        fo.write(line)
    ofs = lineno + len(source)
    last_dest = dest

sys.stderr.write('Orig: %i lines, ofs: %i\n' % (len(orig), ofs))
if len(orig) > ofs:
    sys.stderr.write('Writing tail\n')
    fo = outfiles['cli/koji']
    for line in orig[ofs:]:
        fo.write(line)

for dest in outfiles:
    outfiles[dest].close()
