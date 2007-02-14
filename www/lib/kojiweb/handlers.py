def cleanup(req):
    """Perform any cleanup actions required at the end of a request.
    At the moment, this logs out the webserver <-> koji session."""
    if hasattr(req, '_session') and req._session.logged_in:
        req._session.logout()

    return 0
