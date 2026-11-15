"""Port selection: precedence of --port / env var / default, and holding the port."""

from __future__ import annotations

import socket
import threading
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

import pytest

import pdomain_ocr_simple_gui.__main__ as main_mod
from pdomain_ocr_simple_gui.ports import (
    PORT_ENV_VAR,
    PREFERRED_PORT,
    bind_listening_socket,
    resolve_start_port,
    url_host,
)

if TYPE_CHECKING:
    from collections.abc import Iterator

    import uvicorn


@pytest.fixture
def occupied_port() -> Iterator[int]:
    """A port held by a live listener for the length of the test."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as holder:
        holder.bind(("127.0.0.1", 0))
        holder.listen()
        yield int(holder.getsockname()[1])


class TestPrecedence:
    def test_default_when_nothing_given(self) -> None:
        assert resolve_start_port(None, {}) == PREFERRED_PORT == 8004

    def test_env_beats_default(self) -> None:
        assert resolve_start_port(None, {PORT_ENV_VAR: "9100"}) == 9100

    def test_explicit_flag_beats_env(self) -> None:
        assert resolve_start_port(8010, {PORT_ENV_VAR: "9100"}) == 8010

    def test_explicit_flag_equal_to_default_still_beats_env(self) -> None:
        """The case the old code could not tell apart: --port 8004 with env set."""
        assert resolve_start_port(8004, {PORT_ENV_VAR: "9100"}) == 8004

    def test_invalid_env_falls_back_to_default(self, caplog: pytest.LogCaptureFixture) -> None:
        assert resolve_start_port(None, {PORT_ENV_VAR: "nope"}) == PREFERRED_PORT
        assert PORT_ENV_VAR in caplog.text

    def test_help_states_precedence(self, capsys: pytest.CaptureFixture[str]) -> None:
        with pytest.raises(SystemExit):
            main_mod._parse_args(["--help"])
        text = " ".join(capsys.readouterr().out.split())
        assert f"this flag, then the {PORT_ENV_VAR} env var, then 8004" in text

    @pytest.mark.parametrize(
        ("argv", "env", "expected"),
        [
            ([], {}, 8004),
            ([], {PORT_ENV_VAR: "9100"}, 9100),
            (["--port", "8010"], {PORT_ENV_VAR: "9100"}, 8010),
            (["--port", "8004"], {PORT_ENV_VAR: "9100"}, 8004),
        ],
    )
    def test_main_binds_from_resolved_start_port(
        self,
        monkeypatch: pytest.MonkeyPatch,
        argv: list[str],
        env: dict[str, str],
        expected: int,
    ) -> None:
        monkeypatch.delenv(PORT_ENV_VAR, raising=False)
        for key, value in env.items():
            monkeypatch.setenv(key, value)
        fake_sock = MagicMock()
        fake_sock.getsockname.return_value = ("127.0.0.1", expected)
        bind = MagicMock(return_value=fake_sock)
        with (
            patch.object(main_mod, "bind_listening_socket", bind),
            patch.object(main_mod, "_serve"),
            patch.object(main_mod, "register_self"),
        ):
            main_mod.main([*argv, "--no-browser"])
        assert bind.call_args.args == ("127.0.0.1", expected)


class TestHoldingThePort:
    def test_walks_past_an_occupied_port(self, occupied_port: int) -> None:
        sock = bind_listening_socket("127.0.0.1", occupied_port)
        try:
            assert int(sock.getsockname()[1]) > occupied_port
        finally:
            sock.close()

    def test_raises_when_window_is_exhausted(self, occupied_port: int) -> None:
        with pytest.raises(RuntimeError, match="free port"):
            bind_listening_socket("127.0.0.1", occupied_port, max_attempts=1)

    def test_returned_socket_excludes_other_binders(self) -> None:
        """The race fix: once returned, nobody else can take the port."""
        sock = bind_listening_socket("127.0.0.1", 0)
        try:
            port = int(sock.getsockname()[1])
            for reuse in (0, 1):
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as rival:
                    rival.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, reuse)
                    with pytest.raises(OSError):  # errno differs by OS
                        rival.bind(("127.0.0.1", port))
        finally:
            sock.close()

    def test_main_hands_uvicorn_the_held_socket_and_real_port(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Registry, printed URL and browser all use the port of the socket given to uvicorn."""
        seen: dict[str, object] = {}

        def fake_serve(sock: socket.socket, config: uvicorn.Config) -> None:
            port = config.port
            seen["fileno_open"] = sock.fileno() != -1
            seen["sock_port"] = int(sock.getsockname()[1])
            seen["port"] = port
            seen["host"] = config.host
            seen["reload"] = config.reload
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as rival:
                try:
                    rival.bind(("127.0.0.1", port))
                except OSError:
                    seen["rival_blocked"] = True
                else:
                    seen["rival_blocked"] = False

        register = MagicMock()
        with (
            # Start at 0 so the kernel picks a free port; --port rejects 0.
            patch.object(
                main_mod,
                "bind_listening_socket",
                lambda host, _start: bind_listening_socket(host, 0),
            ),
            patch.object(main_mod, "_serve", fake_serve),
            patch.object(main_mod, "register_self", register),
            patch.object(main_mod, "_open_browser_when_ready"),
            patch("threading.Thread.start") as thread_start,
        ):
            main_mod.main([])

        port = seen["port"]
        assert isinstance(port, int)
        assert port > 0
        assert seen["fileno_open"] is True
        assert seen["sock_port"] == port
        assert seen["rival_blocked"] is True
        assert register.call_args.kwargs["actual_port"] == port
        assert f"at http://127.0.0.1:{port}/" in capsys.readouterr().out
        thread_start.assert_called_once()


def _ipv6_available() -> bool:
    if not socket.has_ipv6:
        return False
    try:
        with socket.socket(socket.AF_INET6, socket.SOCK_STREAM) as probe:
            probe.bind(("::1", 0))
    except OSError:
        return False
    return True


class TestRangesAndHosts:
    def test_env_out_of_range_falls_back(self, caplog: pytest.LogCaptureFixture) -> None:
        for raw in ("0", "70000", "-5"):
            assert resolve_start_port(None, {PORT_ENV_VAR: raw}) == PREFERRED_PORT
        assert PORT_ENV_VAR in caplog.text

    @pytest.mark.parametrize("bad", ["0", "65536", "70000", "-1", "x"])
    def test_cli_rejects_bad_port(self, bad: str, capsys: pytest.CaptureFixture[str]) -> None:
        with pytest.raises(SystemExit) as exc:
            main_mod._parse_args(["--port", bad])
        assert exc.value.code == 2
        assert "port" in capsys.readouterr().err

    def test_walk_stops_at_65535(self) -> None:
        """No OverflowError when the window would run past the last port."""
        sock = None
        try:
            try:
                sock = bind_listening_socket("127.0.0.1", 65535, max_attempts=100)
            except RuntimeError:
                return  # 65535 busy on this host: the walk ended cleanly
            assert int(sock.getsockname()[1]) == 65535
        finally:
            if sock is not None:
                sock.close()

    def test_failed_binds_close_their_sockets(self, occupied_port: int) -> None:
        created: list[socket.socket] = []
        real_socket = socket.socket

        def tracking(*args: int, **kwargs: int) -> socket.socket:
            s = real_socket(*args, **kwargs)
            created.append(s)
            return s

        with (
            patch("pdomain_ocr_simple_gui.ports.socket.socket", tracking),
            pytest.raises(RuntimeError),
        ):
            bind_listening_socket("127.0.0.1", occupied_port, max_attempts=1)
        assert len(created) == 1
        assert created[0].fileno() == -1

    def test_socket_is_inheritable(self) -> None:
        sock = bind_listening_socket("127.0.0.1", 0)
        try:
            assert sock.get_inheritable()
        finally:
            sock.close()

    def test_binds_the_requested_host(self) -> None:
        sock = bind_listening_socket("127.0.0.1", 0)
        try:
            assert sock.getsockname()[0] == "127.0.0.1"
        finally:
            sock.close()

    @pytest.mark.skipif(not _ipv6_available(), reason="no IPv6 loopback")
    @pytest.mark.parametrize("host", ["::1", "[::1]"])
    def test_binds_ipv6_loopback(self, host: str) -> None:
        sock = bind_listening_socket(host, 0)
        try:
            assert sock.family == socket.AF_INET6
            assert sock.getsockname()[0] == "::1"
        finally:
            sock.close()

    def test_url_host_brackets_ipv6(self) -> None:
        assert url_host("::1") == "[::1]"
        assert url_host("[::1]") == "[::1]"
        assert url_host("127.0.0.1") == "127.0.0.1"
        assert main_mod._browser_url("::1", 8004) == "http://[::1]:8004"
        assert main_mod._browser_url("[::]", 8004) == "http://127.0.0.1:8004"

    def test_main_passes_host_to_bind_and_brackets_url(self, capsys: pytest.CaptureFixture[str]) -> None:
        fake_sock = MagicMock()
        fake_sock.getsockname.return_value = ("::1", 8123, 0, 0)
        bind = MagicMock(return_value=fake_sock)
        with (
            patch.object(main_mod, "bind_listening_socket", bind),
            patch.object(main_mod, "_serve") as serve,
            patch.object(main_mod, "register_self"),
        ):
            main_mod.main(["--host", "[::1]", "--no-browser"])
        assert bind.call_args.args[0] == "::1"
        assert "at http://[::1]:8123/" in capsys.readouterr().out
        assert serve.call_args.args[1].host == "::1"


async def _hello_app(scope: dict[str, object], receive: object, send: object) -> None:
    if scope["type"] == "lifespan":
        msg = await receive()  # type: ignore[operator]
        if msg["type"] == "lifespan.startup":
            await send({"type": "lifespan.startup.complete"})  # type: ignore[operator]
            await receive()  # type: ignore[operator]
            await send({"type": "lifespan.shutdown.complete"})  # type: ignore[operator]
        return
    await send({"type": "http.response.start", "status": 200, "headers": []})  # type: ignore[operator]
    await send({"type": "http.response.body", "body": b"hello"})  # type: ignore[operator]


class TestServe:
    def _config(self, **kwargs: object) -> uvicorn.Config:
        import uvicorn

        return uvicorn.Config(_hello_app, host="127.0.0.1", port=1, **kwargs)  # type: ignore[arg-type]

    def test_hands_socket_to_server_run(self) -> None:
        sock = MagicMock()
        with patch("uvicorn.Server") as server_cls:
            server_cls.return_value.started = True
            main_mod._serve(sock, self._config())
        server_cls.return_value.run.assert_called_once_with(sockets=[sock])

    def test_startup_failure_exits_with_uvicorn_code(self) -> None:
        from uvicorn.config import STARTUP_FAILURE

        with patch("uvicorn.Server") as server_cls:
            server_cls.return_value.started = False
            with pytest.raises(SystemExit) as exc:
                main_mod._serve(MagicMock(), self._config())
        assert exc.value.code == STARTUP_FAILURE

    def test_keyboard_interrupt_is_a_clean_exit(self) -> None:
        with patch("uvicorn.Server") as server_cls:
            server_cls.return_value.run.side_effect = KeyboardInterrupt
            main_mod._serve(MagicMock(), self._config())

    def test_reload_uses_change_reload_with_the_socket(self) -> None:
        import uvicorn

        sock = MagicMock()
        config = uvicorn.Config("pdomain_ocr_simple_gui.app:app", reload=True)
        with (
            patch("uvicorn.Server") as server_cls,
            patch("uvicorn.supervisors.ChangeReload") as reloader,
        ):
            main_mod._serve(sock, config)
        reloader.assert_called_once_with(config, target=server_cls.return_value.run, sockets=[sock])
        reloader.return_value.run.assert_called_once_with()
        server_cls.return_value.run.assert_not_called()

    def test_real_server_serves_on_the_held_socket(self) -> None:
        import http.client

        import uvicorn

        sock = bind_listening_socket("127.0.0.1", 0)
        port = int(sock.getsockname()[1])
        config = uvicorn.Config(_hello_app, host="127.0.0.1", port=port, log_level="warning")
        servers: list[uvicorn.Server] = []

        class RecordingServer(uvicorn.Server):
            def __init__(self, config: uvicorn.Config) -> None:
                super().__init__(config)
                servers.append(self)

        with patch("uvicorn.Server", RecordingServer):
            thread = threading.Thread(target=main_mod._serve, args=(sock, config))
            thread.start()
            try:
                # The socket already listens, so the connection queues until the
                # server accepts it; the timeout bounds a hung server.
                conn = http.client.HTTPConnection("127.0.0.1", port, timeout=30)
                conn.request("GET", "/")
                resp = conn.getresponse()
                assert resp.status == 200
                assert resp.read() == b"hello"
                conn.close()
            finally:
                servers[0].should_exit = True
                thread.join(timeout=30)
                sock.close()
        assert not thread.is_alive()
