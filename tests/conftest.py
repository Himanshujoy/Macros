"""Shared test setup. The guard makes a forgotten mock fail loudly instead of calling a real service."""
import socket

import pytest

_real_connect = socket.socket.connect
_LOCAL = ("127.0.0.1", "::1", "localhost")


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def guarded(self, address, *args, **kwargs):
        host = address[0] if isinstance(address, tuple) else address
        if host not in _LOCAL:
            raise RuntimeError(f"test tried to open a network connection to {host!r}")
        return _real_connect(self, address, *args, **kwargs)

    monkeypatch.setattr(socket.socket, "connect", guarded)
