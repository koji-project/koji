from __future__ import absolute_import
import os
import sys

def load_plugin(plugin_type, plugin_name):
    # We have to do this craziness because 'import koji' is ambiguous.  Is it the
    # koji module, or the koji cli module.  Jump through hoops accordingly.
    # https://stackoverflow.com/questions/67631/how-to-import-a-module-given-the-full-path
    mod_name = "%s_%s" % (plugin_name, plugin_type)
    CLI_FILENAME = os.path.join(
        os.path.dirname(__file__),
        "../../plugins",
        plugin_type,
        "%s.py" % plugin_name)
    sys.path = [os.path.dirname(CLI_FILENAME),
                os.path.join(os.path.dirname(__file__), "../..", plugin_type)] + \
               sys.path
    if sys.version_info[0] >= 3:
        import importlib.machinery
        loader = importlib.machinery.SourceFileLoader(mod_name, CLI_FILENAME)
        spec = importlib.util.spec_from_loader(loader.name, loader)
        plugin = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(plugin)
        loader.exec_module(plugin)
        sys.modules[mod_name] = plugin
    else:
        import imp
        plugin = imp.load_source(mod_name, CLI_FILENAME)
    return plugin
