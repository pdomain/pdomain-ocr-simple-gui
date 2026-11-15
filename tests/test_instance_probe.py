"""Challenge the server before reusing a discovered desktop instance."""

from __future__ import annotations

import json
import threading
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import TYPE_CHECKING

import pytest
from typing_extensions import override

from pdomain_ocr_simple_gui.instance import InstanceRecord, new_instance_record, request_instance

if TYPE_CHECKING:
    from collections.abc import Generator


@contextmanager
def responder(*, wrong_challenge: bool = False, wrong_instance: bool = False) -> Generator[InstanceRecord]:
    record: InstanceRecord | None = None

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            assert record is not None
            assert self.path == "/api/lifecycle/instance"
            assert self.headers["Authorization"] == f"Bearer {record.capability.get_secret_value()}"
            challenge = self.headers["X-Pdomain-Challenge"]
            assert challenge
            payload = {
                "app_id": record.app_id,
                "instance_id": "0" * 32 if wrong_instance else record.instance_id,
                "challenge": "wrong" if wrong_challenge else challenge,
                "accepted": True,
            }
            body = json.dumps(payload).encode()
            self.send_response(200)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            _ = self.wfile.write(body)

        @override
        def log_message(self, format: str, *args: object) -> None:
            _ = format, args

    server = HTTPServer(("127.0.0.1", 0), Handler)
    record = new_instance_record(f"http://127.0.0.1:{server.server_port}")
    thread = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.01}, daemon=True)
    thread.start()
    try:
        yield record
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def test_probe_authenticates_and_echoes_challenge() -> None:
    with responder() as record:
        reply = request_instance(record, "status")
    assert reply.instance_id == record.instance_id
    assert reply.accepted


@pytest.mark.parametrize("wrong", ["challenge", "instance"])
def test_probe_rejects_wrong_instance_or_replayed_reply(wrong: str) -> None:
    with (
        responder(wrong_challenge=wrong == "challenge", wrong_instance=wrong == "instance") as record,
        pytest.raises(ValueError, match=r"identity|challenge"),
    ):
        _ = request_instance(record, "status")
