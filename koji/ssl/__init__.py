# identify this as the ssl module

# our own ssl submodule masks python's in the main lib, so we import this here
try:
    import ssl      # python's ssl module
except ImportError:
    # ssl module added in 2.6
    pass
