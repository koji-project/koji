from __future__ import print_function
from __future__ import absolute_import
import mock
import os
import six
import sys
from six.moves import map
try:
    import unittest2 as unittest
except ImportError:
    import unittest


PROGNAME = os.path.basename(sys.argv[0]) or 'koji'

"""
  Classes
"""


#
# Dummy Mock class
#
class _dummy_(object):
    def __enter__(self):
        return self

    def __exit__(self, *arg, **kwargs):
        pass

    def assert_called_once(self, *arg, **kwargs):
        pass

    def assert_called_once_with(self, *arg, **kwargs):
        pass


#
# CLI TestCase
#
class CliTestCase(unittest.TestCase):

    # public attribute
    progname = PROGNAME
    error_format = None
    STDOUT = sys.stdout
    STDERR = sys.stderr

    #
    # private methods
    #
    def __assert_callable(self, obj):
        if not callable(obj):
            raise ValueError('%s is not callable' %
                             getattr(obj, "__name__", 'function'))

    #
    # public methods
    #
    def format_error_message(self, error_message, progname=None):
        return self.error_format.format(message=error_message) \
            if self.error_format else error_message

    def print_message(self, *args, **kwargs):
        """Print message on sys.stdout

           This function will not be influenced when sys.stdout is mocked.
        """
        kwargs['file'] = self.STDOUT
        print(" ".join(map(str, args)), **kwargs)

    def assert_function_wrapper(self, callableObj, *args, **kwargs):
        """Wrapper func with anonymous funtion without argument"""
        self.__assert_callable(callableObj)
        return lambda: callableObj(*args, **kwargs)

    def assert_console_message(
            self, device, message, wipe=True, regex=False):

        # don't care condition
        if message is None:
            return

        output = device.getvalue()
        if not regex:
            self.assertMultiLineEqual(output, message)
        else:
            six.assertRegex(self, output, message)

        if wipe:
            device.seek(0)
            device.truncate(0)

    def assert_system_exit(self, callableObj, *args, **kwargs):
        """Test if SystemExit exception is issued

        Arguments:
            callableObj: the test function
            *args: Vaiable length arguments that will be passed to callableObj
            **kwargs: keyword arguments (see below)

        Keyword arguments: (reseverd for assert_system_exit)
            activate_session (string):
                Mock koji_cli.commands.activate_session and test if it is
                called.
                Default is on, use None to stop mocking.

            stdout:
            stderr: Arguments for messages comparison on stdout/stderr. These
                arguments allows different data types.

                ``None`` type will skip message comparison.
                ``string`` type will do multiple line comparison.
                ``dict`` type is an advanced type to allow regular expression
                 format. the format is::
                    {
                        'message': 'message string or regular expression',
                        'wipe': 'wipe the output device, default is True',
                        'regex': 'True if message format is regular expression'
                    }

            assert_func:
                Callable object with no arguments for customized tests.

            exit_code:
                The exit code when SystemExit is raised

            Important! all the other keyword arguments that are not listed
            above will be passed to callableObj
        """

        # check callableObj callable
        self.__assert_callable(callableObj)

        # these arguments are reseverd and used in assert_system_exit
        reserved = [
            'activate_session', 'stdout', 'stderr',
            'assert_func', 'exit_code'
        ]

        activate = kwargs.get(
            'activate_session', 'koji_cli.commands.activate_session')

        # stdout/stderr message comparison, None means don't care
        # message/error allows many different data types, None, string and dict
        message = {}
        for key in ['stdout', 'stderr']:
            data = kwargs.get(key, None)
            message[key] = {'message': None, 'wipe': True, 'regex': False}

            if data is None or isinstance(data, six.string_types):
                message[key]['message'] = data

            elif isinstance(data, dict):
                message[key] = {
                    'message': data.get('message', None),
                    'wipe': data.get('wipe', True),
                    'regex': data.get('regex', False),
                }

            else:
                raise ValueError('Invalid data type for %s' % key)

        assert_function = kwargs.get(
            'assert_func', lambda *args, **kwargs: True)

        exit_code = kwargs.get('exit_code', 2)

        # args for testee
        test_args = args

        # kwargs for testee, excludes those that are used in assert_system_exit
        test_kwargs = dict((k, v) for k, v in kwargs.items()
                           if k not in reserved)

        # check activate_session must be type of None or string
        if activate and not isinstance(activate, six.string_types):
            raise ValueError('activate_session is not a string')

        session_patch = mock.patch(activate) if activate else _dummy_()
        stdout_patch = mock.patch('sys.stdout', new_callable=six.StringIO)
        stderr_patch = mock.patch('sys.stderr', new_callable=six.StringIO)

        with session_patch as session:
            with stdout_patch as stdout:
                with stderr_patch as stderr:
                    with self.assertRaises(SystemExit) as ex:
                        callableObj(*test_args, **test_kwargs)
                    self.assertExitCode(ex, exit_code)
        session.assert_called_once()
        self.assert_console_message(stdout, **message['stdout'])
        self.assert_console_message(stderr, **message['stderr'])
        assert_function()

    @mock.patch('koji_cli.commands.activate_session')
    def assert_help(self, callableObj, message, activate_session_mock):
        # optarse uses gettext directly and it is driven by LANGUAGE
        # we need engligsh to get comparable strings
        os.environ['LANGUAGE'] = 'en_GB'
        self.assert_system_exit(
            callableObj,
            mock.MagicMock(),
            mock.MagicMock(),
            ['--help'],
            stdout=message,
            stderr='',
            activate_session=None,
            exit_code=0)
        activate_session_mock.assert_not_called()

    def assertExitCode(self, ex, code):
        if isinstance(ex.exception, int):
            self.assertEqual(ex.exception, code)
        else:
            self.assertEqual(ex.exception.code, code)


def get_builtin_open():
    if six.PY2:
        return '__builtin__.open'
    else:
        return 'builtins.open'
