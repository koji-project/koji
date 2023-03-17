import koji


def convert_value(value, cast=None, message=None,
                  exc_type=koji.ParameterError, none_allowed=False, check_only=False):
    """Cast to another type with tailored exception

    :param any value: tested object
    :param type cast: To which type value should be cast
    :param type exc_type: Raise this exception
    :param bool none_allowed: Is None valid value?
    :param check_only: Don't convert but raise an exception if type(value) != cast

    :returns any value: returns converted value
    """
    if value is None:
        if not none_allowed:
            raise exc_type(message or f"Invalid type, expected type {cast}")
        else:
            return value
    if check_only:
        if not isinstance(value, cast):
            raise exc_type(message or f"Invalid type for value '{value}': {type(value)}, "
                                      f"expected type {cast}")
    else:
        try:
            value = cast(value)
        except (ValueError, TypeError):
            raise exc_type(message or f"Invalid type for value '{value}': {type(value)}, "
                                      f"expected type {cast}")
    return value


