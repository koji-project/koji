# prints site-packages path for use in Makefiles

try:
    from distutils.sysconfig import get_python_lib
    print(get_python_lib())
except ImportError:
    import sysconfig
    print(sysconfig.get_path('purelib', 'rpm_prefix'))
