Koji Developer Tools
--------------------

This directory contains some tools that developers may find useful.

fakehub
-------

This script runs a single hub call in the foreground (no httpd) and
dumps the results. It runs using the code from the checkout.

The call to be executed is specified on the command line, much like
the ``koji call`` command.

For example:
```
[mike@localhost koji]$ devtools/fakehub getTag 1
```

You will see hub logs on the console. The call result is pretty printed
at the end.

This tool makes it possible to run hub code through the debugger or
or profiler with relative ease.

fakehub looks for ``fakehub.conf`` or ``fakehub.conf.d`` in the devtools
directory. If either is present, then 
``koji.hub.ConfigFile`` and ``koji.hub.ConfigDir`` are set to these values.
If neither is, then the code will fall back to the default (system) config.


fakeweb
-------

This tool is similar to the fakehub tool, but instead of a single pass it starts
a web server on port 8000 and starts serving.

As with the fakehub tool, fakeweb runs in the foreground in a single thread, making
it possible to debug web code.

Similar to fakehub, fakeweb looks for ``fakeweb.conf`` or ``fakeweb.conf.d``
in the devtools directory. If either is present, then
``koji.web.ConfigFile`` and ``koji.web.ConfigDir`` are set to these values.
If neither is, then the code will fall back to the default (system) config.
