"""Shared test setup. The guard makes a forgotten mock fail loudly instead of calling a real service."""
import socket

import pytest

_real_connect = socket.socket.connect
_real_getaddrinfo = socket.getaddrinfo
_LOCAL = ("127.0.0.1", "::1", "localhost")


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def guarded_connect(self, address, *args, **kwargs):
        host = address[0] if isinstance(address, tuple) else address
        if host not in _LOCAL:
            raise RuntimeError(f"test tried to open a network connection to {host!r}")
        return _real_connect(self, address, *args, **kwargs)

    def guarded_lookup(host, *args, **kwargs):
        if host is not None and host not in _LOCAL:
            raise RuntimeError(f"test tried to look up {host!r} on the network")
        return _real_getaddrinfo(host, *args, **kwargs)

    monkeypatch.setattr(socket.socket, "connect", guarded_connect)
    monkeypatch.setattr(socket, "getaddrinfo", guarded_lookup)
