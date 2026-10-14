"""Errors raised by wirekit transports."""


class ConnectionDropped(Exception):
    """Raised by a transport when no reply arrived for an attempt."""
