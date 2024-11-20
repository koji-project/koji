import locale
from functools import wraps


class mylocale:
    """Locale context manager. Resets to user default at exit."""

    def __init__(self, value=None):
        self.value = value

    def __enter__(self):
        locale.setlocale(locale.LC_ALL, locale=self.value)

    def __exit__(self, _type, value, traceback):
        # This resets to user default. Implementing a proper save and restore
        # for locale is quite tricky, and this serves our testing needs.
        locale.setlocale(locale.LC_ALL, "")
        # return false so we don't eat exceptions
        return False

    def __call__(self, func):
        """When called, act as a decorator"""

        @wraps(func)
        def wrapped(*args, **kwargs):
            with self:
                return func(*args, **kwargs)

        return wrapped


# the end
