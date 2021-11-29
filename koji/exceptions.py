# Exceptions
PythonImportError = ImportError  # will be masked by koji's one


class GenericError(Exception):
    """Base class for our custom exceptions"""
    faultCode = 1000
    fromFault = False

    def __str__(self):
        try:
            return str(self.args[0]['args'][0])
        except Exception:
            try:
                return str(self.args[0])
            except Exception:
                return str(self.__dict__)


class LockError(GenericError):
    """Raised when there is a lock conflict"""
    faultCode = 1001


class AuthError(GenericError):
    """Raised when there is an error in authentication"""
    faultCode = 1002


class TagError(GenericError):
    """Raised when a tagging operation fails"""
    faultCode = 1003


class ActionNotAllowed(GenericError):
    """Raised when the session does not have permission to take some action"""
    faultCode = 1004


class BuildError(GenericError):
    """Raised when a build fails"""
    faultCode = 1005


class AuthLockError(AuthError):
    """Raised when a lock prevents authentication"""
    faultCode = 1006


class AuthExpired(AuthError):
    """Raised when a session has expired"""
    faultCode = 1007


class SequenceError(AuthError):
    """Raised when requests are received out of sequence"""
    faultCode = 1008


class RetryError(AuthError):
    """Raised when a request is received twice and cannot be rerun"""
    faultCode = 1009


class PreBuildError(BuildError):
    """Raised when a build fails during pre-checks"""
    faultCode = 1010


class PostBuildError(BuildError):
    """Raised when a build fails during post-checks"""
    faultCode = 1011


class BuildrootError(BuildError):
    """Raised when there is an error with the buildroot"""
    faultCode = 1012


class FunctionDeprecated(GenericError):
    """Raised by a deprecated function"""
    faultCode = 1013


class ServerOffline(GenericError):
    """Raised when the server is offline"""
    faultCode = 1014


class LiveCDError(GenericError):
    """Raised when LiveCD Image creation fails"""
    faultCode = 1015


class PluginError(GenericError):
    """Raised when there is an error with a plugin"""
    faultCode = 1016


class CallbackError(PluginError):
    """Raised when there is an error executing a callback"""
    faultCode = 1017


class ApplianceError(GenericError):
    """Raised when Appliance Image creation fails"""
    faultCode = 1018


class ParameterError(GenericError):
    """Raised when an rpc call receives incorrect arguments"""
    faultCode = 1019


class ImportError(GenericError):
    """Raised when an import fails"""
    faultCode = 1020


class ConfigurationError(GenericError):
    """Raised when load of koji configuration fails"""
    faultCode = 1021


class LiveMediaError(GenericError):
    """Raised when LiveMedia Image creation fails"""
    faultCode = 1022


class GSSAPIAuthError(AuthError):
    """Raised when GSSAPI issue in authentication"""
    faultCode = 1023


class NoSuchArchive(object):
    faultCode = 1024


class NoSuchBuild(object):
    faultCode = 1025


class NoSuchChannel(object):
    faultCode = 1026


class NoSuchContentGenerator(object):
    faultCode = 1027


class NoSuchPackage(object):
    faultCode = 1028


class NoSuchPermission(object):
    faultCode = 1029


class NoSuchRPM(object):
    faultCode = 1030


class NoSuchRepo(object):
    faultCode = 1031


class NoSuchTag(object):
    faultCode = 1032


class NoSuchTarget(object):
    faultCode = 1033


class NoSuchTask(object):
    faultCode = 1034


class NoSuchUser(object):
    faultCode = 1035
