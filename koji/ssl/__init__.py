# identify this as the ssl module

# our own ssl submodule masks python's in the main lib, so we import this here
from __future__ import absolute_import
try:
    import ssl      # python's ssl module
except ImportError:  # pragma: no cover
    # ssl module added in 2.6
    pass
