"""Port selection: pick a start port, then bind and keep a listening socket.

The old flow probed a port, closed the probe and let uvicorn bind later, so
another process could take the port in between. Here the app binds the
socket itself and hands that open socket to uvicorn, so the port it prints,
registers and opens in the browser is one it holds.
"""

from __future__ import annotations

import logging
import socket
import sys
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Mapping

logger = logging.getLogger(__name__)

PREFERRED_PORT = 8004
PORT_ENV_VAR = "PD_OCR_SIMPLE_GUI_PORT"
MAX_PORT_ATTEMPTS = 100
MIN_PORT = 1
MAX_PORT = 65535
_LISTEN_BACKLOG = 2048  # uvicorn's own default backlog


def is_valid_port(port: int) -> bool:
    """Return True when ``port`` is a usable TCP port number (1-65535)."""
    return MIN_PORT <= port <= MAX_PORT


def normalize_host(host: str) -> str:
    """Strip the brackets from an IPv6 literal such as ``[::1]``."""
    if host.startswith("[") and host.endswith("]"):
        return host[1:-1]
    return host


def url_host(host: str) -> str:
    """Return ``host`` as it appears in a URL, with IPv6 literals bracketed."""
    bare = normalize_host(host)
    return f"[{bare}]" if ":" in bare else bare


def resolve_start_port(cli_port: int | None, env: Mapping[str, str]) -> int:
    """Return the first port to try: explicit ``--port``, then the env var, then 8004.

    An env var that is not an integer in 1-65535 is ignored with a warning.

    Args:
        cli_port: Value of ``--port`` (already validated), or None when not given.
        env: Environment mapping (``os.environ``).

    Returns:
        The port to start the search from.
    """
    if cli_port is not None:
        return cli_port
    raw = env.get(PORT_ENV_VAR)
    if raw is not None:
        try:
            value = int(raw)
        except ValueError:
            value = None
        if value is not None and is_valid_port(value):
            return value
        logger.warning(
            "Env var %s=%r is not a port number (1-65535); using port %d.",
            PORT_ENV_VAR,
            raw,
            PREFERRED_PORT,
        )
    return PREFERRED_PORT


def _bind_one(host: str, port: int) -> socket.socket:
    family = socket.AF_INET6 if ":" in host else socket.AF_INET
    sock = socket.socket(family, socket.SOCK_STREAM)
    try:
        if sys.platform == "win32":
            # On Windows SO_REUSEADDR lets another process bind a port that is
            # already in use. SO_EXCLUSIVEADDRUSE is what keeps the port ours.
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        elif sys.platform.startswith("linux"):
            # Same as uvicorn: allows a quick restart past TIME_WAIT. On Linux
            # it still refuses a port with a live listener, wildcard included.
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        # Other platforms (macOS, BSD) set no reuse option. There SO_REUSEADDR
        # would let 127.0.0.1:p bind while a wildcard listener holds p. The cost
        # is that a bind inside TIME_WAIT fails and the walk takes the next port.
        # The Windows and macOS branches are not exercised by the test suite.
        sock.bind((host, port))
        # Listen now. A bound but not listening socket can still be shared by
        # another SO_REUSEADDR socket on Linux. uvicorn calls listen() again.
        sock.listen(_LISTEN_BACKLOG)
        # Like uvicorn's bind_socket: the reload subprocess inherits the socket.
        sock.set_inheritable(True)
    except BaseException:
        sock.close()
        raise
    return sock


def bind_listening_socket(
    host: str,
    start: int,
    *,
    max_attempts: int = MAX_PORT_ATTEMPTS,
) -> socket.socket:
    """Bind and listen on the first free port in ``[start, start + max_attempts)``.

    The returned socket stays open; pass it to uvicorn so no other process can
    take the port before the server starts. Start port 0 asks the kernel for
    any free port. The walk stops at 65535. A bracketed IPv6 host is accepted.

    Args:
        host: Interface address to bind.
        start: First port to try.
        max_attempts: How many consecutive ports to try.

    Returns:
        A bound, listening socket. The caller closes it.

    Raises:
        RuntimeError: No port in the window could be bound.
    """
    bare = normalize_host(host)
    last = min(start + max_attempts - 1, MAX_PORT)
    for port in range(start, last + 1):
        try:
            return _bind_one(bare, port)
        except OSError:
            continue
    msg = f"Could not find a free port in range [{start}, {last}] on {host!r}."
    raise RuntimeError(msg)
