import socket

import pytest


def test_the_guard_blocks_connections_outside_localhost():
    with socket.socket() as sock, pytest.raises(RuntimeError, match="network"):
        sock.settimeout(0.5)
        sock.connect(("192.0.2.1", 80))  # TEST-NET-1: a reserved address that is never a real host


def test_the_guard_allows_localhost():
    with socket.socket() as server:
        server.bind(("127.0.0.1", 0))
        server.listen(1)
        with socket.socket() as client:
            client.connect(server.getsockname())
